import logging
import time
from typing import Any, Optional
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from opentelemetry import context as otel_context
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Span, Status, StatusCode

from src.infra.config import settings

logger = logging.getLogger(__name__)

# 1. Definição do Ambiente e Regras de Sanitização
ENVIRONMENT = settings.APP_ENV
SENSITIVE_KEYS = {"password", "token", "cpf", "credit_card", "secret", "email"}

_provider: Optional[TracerProvider] = None


def _is_sensitive(key: str) -> bool:
    lowered = key.lower()
    return any(s in lowered for s in SENSITIVE_KEYS)


def safe_set_attribute(span: Span, key: str, value: Any):
    """
    Adiciona atributos ao span mascarando dados sensíveis apenas se estiver em produção.
    Valores None são ignorados e tipos não suportados pelo OTel são convertidos em str.
    """
    if value is None:
        return
    if ENVIRONMENT == "production" and _is_sensitive(key):
        span.set_attribute(key, "***REDACTED***")
        return
    if not isinstance(value, (str, bool, int, float)):
        value = str(value)
    span.set_attribute(key, value)


def safe_add_event(span: Span, name: str, attributes: Optional[dict[str, Any]] = None):
    """Adiciona evento ao span aplicando a mesma sanitização de atributos."""
    clean: dict[str, Any] = {}
    for key, value in (attributes or {}).items():
        if value is None:
            continue
        if ENVIRONMENT == "production" and _is_sensitive(key):
            value = "***REDACTED***"
        elif not isinstance(value, (str, bool, int, float)):
            value = str(value)
        clean[key] = value
    span.add_event(name, attributes=clean)


def record_exception(span: Span, exc: BaseException):
    """Registra exceção e marca o span com status de erro."""
    span.record_exception(exc)
    span.set_status(Status(StatusCode.ERROR, str(exc)))


def setup_telemetry(tracer_name: str):
    """
    Configura (uma única vez) o TracerProvider e o OTLP Exporter HTTP (Jaeger, porta 4318).
    O nome do serviço exibido no Jaeger vem de `settings.TELEMETRY_SERVICE_NAME`;
    `tracer_name` identifica apenas o módulo instrumentado (escopo de instrumentação).
    """
    global _provider
    if _provider is None:
        resource = Resource.create({
            "service.name": settings.TELEMETRY_SERVICE_NAME,
            "deployment.environment": ENVIRONMENT,
        })
        provider = TracerProvider(resource=resource)

        # 4318 é a porta OTLP/HTTP (gRPC seria 4317), portanto usamos o exporter HTTP.
        otlp_exporter = OTLPSpanExporter(
            endpoint=f"http://localhost:{settings.TELEMETRY_PORT}/v1/traces"
        )
        # BatchSpanProcessor é focado em performance (envia em lotes); flush a cada 1s
        provider.add_span_processor(BatchSpanProcessor(otlp_exporter, schedule_delay_millis=1000))
        trace.set_tracer_provider(provider)
        _provider = provider

    return trace.get_tracer(tracer_name)


def shutdown_telemetry():
    """Força o envio dos spans pendentes (chamar no shutdown da aplicação)."""
    if _provider is not None:
        _provider.force_flush()
        _provider.shutdown()


class LLMTelemetryCallback(BaseCallbackHandler):
    """
    Callback LangChain que cria um span `llm.call` por chamada ao modelo, com:
    modelo, provedor, tokens de entrada/saída/total, latência e (em streaming) tempo até o 1º token.
    """

    def __init__(self, operation: str, tracer_name: str = "llm", parent: Optional[Span] = None):
        self.operation = operation
        self.tracer = trace.get_tracer(tracer_name)
        # Captura o contexto no momento da criação (dentro do span pai) para garantir o vínculo
        # com a mesma trace, mesmo que o LangChain execute o handler em outra thread/contexto.
        self._parent_ctx = (
            trace.set_span_in_context(parent) if parent is not None else otel_context.get_current()
        )
        self._runs: dict[UUID, dict[str, Any]] = {}

    def _start(self, serialized, run_id: UUID, kwargs: dict):
        params = kwargs.get("invocation_params") or {}
        model = (
            params.get("model")
            or params.get("model_name")
            or ((serialized or {}).get("kwargs") or {}).get("model")
            or "unknown"
        )
        span = self.tracer.start_span("llm.call", context=self._parent_ctx)
        safe_set_attribute(span, "llm.operation", self.operation)
        safe_set_attribute(span, "llm.model", str(model).replace("models/", ""))
        safe_set_attribute(span, "llm.provider", settings.AI_PROVIDER)
        safe_set_attribute(span, "llm.temperature", params.get("temperature"))
        span.add_event("llm.request.start")
        self._runs[run_id] = {"span": span, "t0": time.perf_counter(), "first": False}

    def on_chat_model_start(self, serialized, messages, *, run_id: UUID, **kwargs):
        self._start(serialized, run_id, kwargs)
        n_msgs = sum(len(m) for m in messages)
        safe_set_attribute(self._runs[run_id]["span"], "llm.input.messages", n_msgs)

    def on_llm_start(self, serialized, prompts, *, run_id: UUID, **kwargs):
        self._start(serialized, run_id, kwargs)

    def on_llm_new_token(self, token: str, *, run_id: UUID, **kwargs):
        run = self._runs.get(run_id)
        if run and not run["first"]:
            run["first"] = True
            ttft = round((time.perf_counter() - run["t0"]) * 1000.0, 2)
            safe_set_attribute(run["span"], "llm.time_to_first_token_ms", ttft)
            run["span"].add_event("llm.first_token", {"ttft_ms": ttft})

    def on_llm_end(self, response, *, run_id: UUID, **kwargs):
        run = self._runs.pop(run_id, None)
        if not run:
            return
        span: Span = run["span"]
        latency = round((time.perf_counter() - run["t0"]) * 1000.0, 2)
        usage = None
        resp_model = None
        try:
            msg = response.generations[0][0].message
            usage = getattr(msg, "usage_metadata", None)
            resp_model = (getattr(msg, "response_metadata", None) or {}).get("model_name")
        except Exception:
            pass
        if not usage:
            tu = (getattr(response, "llm_output", None) or {}).get("token_usage") or {}
            if tu:
                usage = {
                    "input_tokens": tu.get("prompt_tokens"),
                    "output_tokens": tu.get("completion_tokens"),
                    "total_tokens": tu.get("total_tokens"),
                }
        if usage:
            safe_set_attribute(span, "llm.usage.input_tokens", usage.get("input_tokens"))
            safe_set_attribute(span, "llm.usage.output_tokens", usage.get("output_tokens"))
            safe_set_attribute(span, "llm.usage.total_tokens", usage.get("total_tokens"))
        else:
            span.add_event("llm.usage.unavailable")
        safe_set_attribute(span, "llm.response.model", resp_model)
        safe_set_attribute(span, "llm.latency_ms", latency)
        span.add_event("llm.request.end", {"latency_ms": latency})
        span.end()

    def on_llm_error(self, error: BaseException, *, run_id: UUID, **kwargs):
        run = self._runs.pop(run_id, None)
        if not run:
            return
        span: Span = run["span"]
        safe_set_attribute(span, "llm.latency_ms", round((time.perf_counter() - run["t0"]) * 1000.0, 2))
        record_exception(span, error)
        span.end()