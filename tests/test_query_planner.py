import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from langchain_core.messages import AIMessage, HumanMessage

from src.schemas.chat import ChatMessage, ChatResponse, QueryPlan, RetrievedChunk
from src.services.query_planner import QueryPlanner


class TestQueryPlanner(unittest.IsolatedAsyncioTestCase):
    def test_query_plan_schema(self):
        plan = QueryPlan(
            intent="Consulta sobre multa rescisória",
            clarified_query="qual a multa por cancelamento do plano TeleTech Fibra 500 Mega antes de 12 meses",
            entities=["TeleTech Fibra 500 Mega", "Multa Rescisória"],
            keywords=["cancelamento", "multa", "fidelidade"],
        )
        self.assertEqual(plan.intent, "Consulta sobre multa rescisória")
        self.assertEqual(len(plan.entities), 2)
        self.assertIn("fidelidade", plan.keywords)

    def test_format_history(self):
        planner = QueryPlanner()
        history = [
            ChatMessage(role="user", content="Quais são os planos de fibra?"),
            ChatMessage(role="assistant", content="Temos os planos de 300, 500 e 1000 Mega."),
        ]
        formatted = planner._format_history(history)
        self.assertEqual(len(formatted), 2)
        self.assertIsInstance(formatted[0], HumanMessage)
        self.assertEqual(formatted[0].content, "Quais são os planos de fibra?")
        self.assertIsInstance(formatted[1], AIMessage)
        self.assertIn("300, 500 e 1000 Mega", formatted[1].content)

    async def test_plan_with_structured_chain(self):
        planner = QueryPlanner()
        expected_plan = QueryPlan(
            intent="Dúvida sobre fidelidade e multa",
            clarified_query="regras de fidelidade e multa rescisória no plano TeleTech Fibra 500 Mega",
            entities=["TeleTech Fibra 500 Mega"],
            keywords=["fidelidade", "multa"],
        )

        mock_structured_chain = MagicMock()
        mock_structured_chain.ainvoke = AsyncMock(return_value=expected_plan)
        planner.structured_chain = mock_structured_chain

        result = await planner.plan("e tem fidelidade?")
        self.assertEqual(result.intent, expected_plan.intent)
        self.assertEqual(result.clarified_query, expected_plan.clarified_query)
        self.assertEqual(result.entities, ["TeleTech Fibra 500 Mega"])

    async def test_plan_fallback_on_exception(self):
        planner = QueryPlanner()
        planner.structured_chain = MagicMock()
        planner.structured_chain.ainvoke = AsyncMock(side_effect=Exception("API Error"))

        planner.raw_chain = MagicMock()
        planner.raw_chain.ainvoke = AsyncMock(side_effect=Exception("Raw API Error"))

        # Verifica se o fallback resiliente mantém o funcionamento da aplicação sem quebrar
        result = await planner.plan("quanto custa a internet fibra?")
        self.assertEqual(result.intent, "Consulta Geral TeleTech")
        self.assertEqual(result.clarified_query, "quanto custa a internet fibra?")

    async def test_answer_query_full_flow(self):
        planner = QueryPlanner()
        mock_plan = QueryPlan(
            intent="Preço Fibra 500",
            clarified_query="valor mensal plano TeleTech Fibra 500 Mega",
            entities=["Fibra 500 Mega"],
            keywords=["valor", "fibra"],
        )
        planner.plan = AsyncMock(return_value=mock_plan)

        mock_rag_response = ChatResponse(
            answer="O plano TeleTech Fibra 500 Mega custa R$ 119,90/mês.",
            sources=[
                RetrievedChunk(
                    content="Plano TeleTech Fibra 500 Mega: R$ 119,90/mês",
                    metadata={"title": "Tabela de Planos"},
                    score=0.92,
                )
            ],
            latency_ms=120.0,
        )

        with patch("src.services.query_planner.rag_service.answer_query", new_callable=AsyncMock) as mock_answer:
            mock_answer.return_value = mock_rag_response

            response = await planner.answer_query("quanto custa o de 500?")

            self.assertEqual(response.answer, mock_rag_response.answer)
            self.assertIsNotNone(response.query_plan)
            self.assertEqual(response.query_plan.intent, "Preço Fibra 500")
            self.assertEqual(response.query_plan.clarified_query, "valor mensal plano TeleTech Fibra 500 Mega")
            mock_answer.assert_awaited_once_with(
                query="valor mensal plano TeleTech Fibra 500 Mega",
                history=None,
                tenant="teletech",
                custom_filter=None,
                top_k=4,
            )


if __name__ == "__main__":
    unittest.main()

