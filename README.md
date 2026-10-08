# 📡 TeleTech Chat Specialist - RAG API

API de atendimento corporativo e suporte especializado para telecomunicações (**TeleTech Brasil**), construída com arquitetura **Retrieval-Augmented Generation (RAG)** de alta performance utilizando **FastAPI**, **LangChain (LCEL)** e **PostgreSQL com pgvector**.

---

## 🛠️ Stack Tecnológica

- **Linguagem & Framework**: Python 3.12+, FastAPI, Uvicorn
- **Orquestração RAG**: LangChain Core, LangChain Google GenAI, LangChain OpenAI (LCEL assíncrono)
- **Banco Vetorial**: PostgreSQL 16 com extensão `pgvector` (`langchain-postgres`)
- **Processamento de Documentos**: `MarkdownHeaderTextSplitter`, `RecursiveCharacterTextSplitter`, `python-frontmatter`
- **Modelos de IA**:
  - **Google Gemini** (Ativo): `gemini-2.5-flash` (Chat) e `gemini-embedding-001` (Embeddings)
  - **OpenAI** (Opcional): `gpt-4.1-mini` e `text-embedding-3-small`
- **Query Planner**: etapa de LLM que identifica a intenção e reescreve a pergunta antes da busca vetorial
- **Observabilidade**: OpenTelemetry (OTLP/HTTP) + Jaeger — traces com modelo, tokens, scores e latências
- **Frontend Web**: Next.js 15, React 19, TypeScript, Tailwind CSS (Design Minimalista Dark)
- **Containerização**: Docker Compose

---

## 📋 Pré-requisitos

1. **Python 3.12 ou superior** instalado.
2. **Node.js 18+ e npm** instalados (para o front-end).
3. **Docker e Docker Compose** instalados e em execução.
4. **Chave de API do Google Gemini** (`GOOGLE_API_KEY`) ou **OpenAI** (`OPENAI_API_KEY`).

---

## 🚀 Instalação e Configuração

### 1. Criar e Ativar o Ambiente Virtual

No terminal PowerShell (Windows):

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

*(No Linux/macOS: `source venv/bin/activate`)*

### 2. Instalar as Dependências

```powershell
pip install -r requirements.txt
```

### 3. Configurar as Variáveis de Ambiente

Crie o arquivo `.env` na raiz do projeto baseado no `.env_example`:

```powershell
Copy-Item .env_example .env
```

Edite o `.env` com suas credenciais:

```ini
DB_HOST=localhost
DB_NAME=rag
DB_PASS=rag
DB_PORT=5432

# Provedor: "google" (padrão) ou "openai"
AI_PROVIDER=google

# Configuração Google Gemini
GOOGLE_API_KEY=sua_chave_gemini_aqui
GOOGLE_CHAT_MODEL=gemini-2.5-flash
GOOGLE_EMBEDDING_MODEL=gemini-embedding-001

# Configuração OpenAI (opcional)
OPENAI_API_KEY=
OPENAI_CHAT_MODEL=gpt-4.1-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

# Telemetria (obrigatórias)
APP_ENV=development          # "production" ativa mascaramento de dados sensíveis nos spans
TELEMETRY_TOOL=jaeger
TELEMETRY_PORT=4318          # Porta OTLP/HTTP do Jaeger
```

---

## 🗄️ Inicialização do Banco de Dados (pgvector)

### 1. Subir o PostgreSQL via Docker Compose

Inicie o contêiner do PostgreSQL com `pgvector`:

```powershell
docker compose --profile jaeger up -d --build
```

Verifique se o contêiner está ativo com `docker ps`.

### 2. Validar Conexão e Habilitar Extensão Vetorial

Execute o script utilitário para testar a conectividade e garantir que a extensão `vector` está criada:

```powershell
python -m src.utils.create_database
```

A saída esperada deverá confirmar:
```text
Conexão com PostgreSQL bem-sucedida! OK: 1
Extensão pgvector ativada com sucesso ou já existente!
```

---

## 🌐 Executando a API

Inicie o servidor Uvicorn com hot-reload habilitado:

```powershell
python .\src\server.py 
```

- **Documentação Interativa (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Documentação Alternativa (Redoc)**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **Health Check**: [http://localhost:8000/health](http://localhost:8000/health)

---

## 🧪 Roteiro de Testes Passo a Passo

Você pode testar a aplicação interativamente pelo Swagger (`/docs`) ou diretamente pelo terminal (PowerShell ou cURL):

### 1. Testar Integridade da Aplicação (Health Check)

Verifica a saúde do serviço e o status do banco vetorial:

**PowerShell:**
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/health" -Method GET
```

**cURL:**
```bash
curl -X GET "http://localhost:8000/health"
```

**Resposta esperada:**
```json
{
  "status": "healthy",
  "database_connected": true,
  "pgvector_ready": true,
  "error": null
}
```

---

### 2. Indexar a Base de Conhecimento (Ingestão em Lote)

Lê todos os documentos da pasta `knowledge_docs/`, fatia em chunks com cabeçalhos semânticos e armazena os embeddings no PostgreSQL:

**PowerShell:**
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/ingest/knowledge-docs" -Method POST
```

**cURL:**
```bash
curl -X POST "http://localhost:8000/api/v1/ingest/knowledge-docs"
```

**Resposta esperada:**
```json
{
  "status": "success",
  "message": "Ingestão concluída com sucesso. 5 arquivos processados.",
  "total_files": 5,
  "total_chunks": 18,
  "details": [
    { "file": "available_plans.md", "title": "Catálogo de Planos e Serviços TeleTech Brasil", "chunks": 4 },
    { "file": "cancellation_policy.md", "title": "Política de Cancelamento e Fidelidade TeleTech Brasil", "chunks": 3 },
    { "file": "commercial_document.md", "title": "Portfólio Comercial e Regras de Contratação", "chunks": 4 },
    { "file": "network_coverage.md", "title": "Diretrizes de Cobertura e Infraestrutura de Rede", "chunks": 3 },
    { "file": "rules_support.md", "title": "Diretrizes de Suporte Técnico e Níveis de Serviço (SLA)", "chunks": 4 }
  ]
}
```

---

### 3. Testar a Busca Semântica Pura (Diagnóstico de Recuperação)

Recupera os chunks mais próximos no espaço vetorial sem invocar o modelo gerador (ideal para benchmarking e calibração de scores):

**PowerShell:**
```powershell
$body = @{
    question = "Quais as opções de planos de fibra óptica e roteador mesh?"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/api/v1/chat/search" -Method POST -ContentType "application/json" -Body $body
```

**cURL:**
```bash
curl -X POST "http://localhost:8000/api/v1/chat/search" \
     -H "Content-Type: application/json" \
     -d '{"question": "Quais as opções de planos de fibra óptica e roteador mesh?"}'
```

---

### 4. Testar o Chat RAG (Pergunta & Resposta com Fontes)

Envie apenas a **pergunta** (com **filtros opcionais** se desejar filtrar metadados específicos):

#### Exemplo A: Consulta Simples (sem filtros)
**PowerShell:**
```powershell
$body = @{
    question = "Como funciona a contratação do combo Multi TeleTech e quais os benefícios?"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/api/v1/chat" -Method POST -ContentType "application/json" -Body $body
```

**cURL:**
```bash
curl -X POST "http://localhost:8000/api/v1/chat" \
     -H "Content-Type: application/json" \
     -d '{"question": "Como funciona a contratação do combo Multi TeleTech e quais os benefícios?"}'
```

#### Exemplo B: Consulta com Filtros Customizados Opcionais
**PowerShell:**
```powershell
$body = @{
    question = "Quais são os planos corporativos?"
    filters = @{
        doc_type = "service_portfolio"
        plan = "all"
    }
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/api/v1/chat" -Method POST -ContentType "application/json" -Body $body
```

**cURL:**
```bash
curl -X POST "http://localhost:8000/api/v1/chat" \
     -H "Content-Type: application/json" \
     -d '{"question": "Quais são os planos corporativos?", "filters": {"doc_type": "service_portfolio"}}'
```

**Resposta esperada:**
```json
{
  "answer": "O combo Multi TeleTech agrupa a fatura do plano móvel individual e da banda larga de fibra óptica residencial sob uma única titularidade bancária. Ao contratar essa modalidade, os dados 5G do pacote de celular são imediatamente dobrados...",
  "sources": [
    {
      "content": "...",
      "metadata": {
        "title": "Catálogo de Planos e Serviços TeleTech Brasil",
        "doc_type": "service_portfolio",
        "tenant": "teletech",
        "plan": "all",
        "version": "3.2"
      },
      "score": 0.1842
    }
  ],
  "latency_ms": 1150.32,
  "query_plan": {
    "intent": "Contratação e benefícios do combo Multi",
    "clarified_query": "benefícios e funcionamento da contratação do combo Multi TeleTech",
    "entities": ["combo Multi TeleTech", "fibra óptica", "móvel 5G"],
    "keywords": ["combo", "benefícios", "contratação"]
  }
}
```

---

### 5. Testar Streaming de Resposta (SSE - Server-Sent Events)


Receba os tokens de resposta em tempo real via streaming com o mesmo formato de payload simplificado:

**cURL:**
```bash
curl -N -X POST "http://localhost:8000/api/v1/chat/stream" \
     -H "Content-Type: application/json" \
     -d '{"question": "Qual é a velocidade dos planos residenciais de fibra?"}'
```

---

## 🔭 Observabilidade (OpenTelemetry + Jaeger)

Cada requisição gera **um único trace** no Jaeger, com spans aninhados e eventos:

```text
http.chat | http.chat_stream | http.chat_search      (raiz)
└── answer_query
    ├── planner.plan
    │   └── llm.call                 # modelo, tokens in/out/total, latência
    ├── rag.search
    │   ├── rag.embed_query          # modelo, dimensões, latência do embedding
    │   └── rag.vector_query         # latência da consulta no pgvector
    └── rag.generate / rag.generate_stream
        └── llm.call                 # modelo, tokens, latência, tempo até o 1º token
```

| Dado | Onde aparece |
|---|---|
| Modelo chamado e tokens de entrada/saída/total | Atributos `llm.model`, `llm.usage.*` em cada `llm.call` |
| Resultados da busca vetorial | Eventos `rag.chunk_retrieved` (rank, score, título, seção) no span `rag.search` |
| Scores resumidos | `rag.score.best`, `rag.score.worst`, `rag.score.avg` |
| Latências | `rag.embedding_latency_ms`, `rag.vector_query_latency_ms`, `llm.latency_ms`, `chat.total_latency_ms`, `chat.time_to_first_token_ms` (stream) |

> **Nota:** o `score` do pgvector é **distância** (quanto menor, mais similar).

**Como usar:**

1. Suba o Jaeger: `docker compose --profile jaeger up -d`
2. Defina no `.env`: `APP_ENV`, `TELEMETRY_TOOL` e `TELEMETRY_PORT=4318` (OTLP/HTTP).
3. Faça uma chamada à API e abra a UI em [http://localhost:16686](http://localhost:16686) (serviço `rag-chat-specialist`, configurável via `TELEMETRY_SERVICE_NAME`).

> Em `APP_ENV=production`, atributos com nomes sensíveis (`password`, `token`, `cpf`, `email`, ...) são mascarados. O armazenamento do Jaeger é em memória: os traces são perdidos ao reiniciar o container.

---

## 💻 Frontend Web (Next.js & Tailwind CSS)

O projeto conta com uma interface web moderna e minimalista para teste, validação e demonstração interativa do chat RAG em tempo real.

### 🎨 Design Minimalista e Otimizações React

- **Estética Monocromática Dark**: Interface limpa em tons de cinza (`bg-zinc-950`, superfícies `zinc-900`/`zinc-800`), sem bibliotecas pesadas de UI — estilizada com **Tailwind CSS puro**.
- **Performance e Boas Práticas Vercel React** (seguindo o skill `@react`):
  - `rerender-memo`: Componentes `MessageBubble` e `SourcesPanel` envolvidos em `React.memo` para evitar re-renderizações a cada token recebido.
  - `bundle-dynamic-imports`: `FilterPanel` carregado dinamicamente com `next/dynamic` (`ssr: false`).
  - `rerender-use-deferred-value`: `useDeferredValue` na lista de mensagens, mantendo a digitação no input ágil e responsiva.
  - `rerender-functional-setstate`: Atualizações de estado funcionais `setMessages((prev) => ...)`.
  - `rendering-conditional-render`: Uso de ternários em vez de `&&` para renderizações condicionais seguras.
  - `async-suspense-boundaries`: `Suspense` boundary na página principal para streaming e hidratação eficiente.

---

### ✨ Recursos da Interface

| Recurso | Descrição |
|---|---|
| **Modo Normal** | Envia a consulta e aguarda a resposta completa do backend. Exibe a latência em milissegundos (`latency_ms`) e as fontes recuperadas. |
| **Modo Stream (SSE)** | Consome a rota de streaming do backend token a token em tempo real (`text/event-stream`), renderizando a resposta com efeito typewriter e cursor ativo. |
| **Painel de Filtros** | Barra colapsável no topo com contador de filtros ativos:<ul><li>**Tenant**: texto livre (ex: `teletech`)</li><li>**Audience**: seletor entre `b2b`, `b2c`, `all` (ou sem filtro)</li><li>**Plan**: texto livre (ex: `enterprise`, `fibra_pro`)</li><li>Botão **Limpar filtros** para reset rápido</li></ul> |
| **Painel de Fontes** | Accordion colapsável abaixo de respostas do assistente (`Ver fontes (N)`), detalhando título, tipo de documento e o trecho de contexto recuperado do pgvector. |
| **Proxy Next.js Integrado** | Route Handlers em `/api/chat` e `/api/stream` que repassam as requisições para a API Python FastAPI (`http://localhost:8000`), evitando bloqueios de CORS e encapsulando o streaming. |

---

### 🚀 Como Executar o Frontend

1. **Garantir que a API Backend está em execução**:
   ```powershell
   uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
   ```

2. **Entrar no diretório do frontend**:
   ```powershell
   cd frontend
   ```

3. **Instalar dependências (caso não tenham sido instaladas)**:
   ```powershell
   npm install
   ```

4. **Iniciar em modo de desenvolvimento**:
   ```powershell
   npm run dev
   ```

5. **Acessar no navegador**:
   Abra [http://localhost:3000](http://localhost:3000)

> **Nota de Configuração**: O arquivo `frontend/.env.local` já vem configurado por padrão apontando para `NEXT_PUBLIC_API_URL=http://localhost:8000`.

---

### 🧪 Cenários de Teste no Frontend

#### Teste 1: Chat com Streaming em Tempo Real
1. No canto superior direito da tela, clique no seletor de modo e escolha **Stream**.
2. No campo de texto na parte inferior, digite:
   > *"Quais são as velocidades e benefícios dos planos de fibra óptica?"*
3. Pressione **Enter** ou clique no botão de envio (ícone de seta).
4. **Comportamento esperado**: Os tokens aparecem progressivamente na tela com animação de digitação em tempo real.

#### Teste 2: Chat Normal com Diagnóstico de Fontes e Latência
1. No seletor de modo, alterne para **Normal**.
2. Digite:
   > *"Qual é o prazo de fidelidade e as regras de cancelamento sem multa?"*
3. Pressione **Enter**.
4. **Comportamento esperado**:
   - A resposta completa é exibida acompanhada da latência de inferência (ex: `⏱ 1120ms`).
   - Um botão `Ver fontes (X)` aparece no rodapé da resposta. Ao clicar, visualize os trechos recuperados do catálogo e a política de cancelamento.

#### Teste 3: Consulta com Filtros de Metadados (Tenant, Audience, Plan)
1. Clique em **Filtros** no topo da tela para expandir os campos opcionais.
2. Preencha os campos desejados:
   - **Tenant**: `teletech`
   - **Audience**: Selecione `b2b`
   - **Plan**: `enterprise`
3. Observe que o badge ao lado de "Filtros" atualiza indicando a quantidade de filtros ativos (ex: `3`).
4. Envie uma pergunta corporativa:
   > *"Quais as condições e SLAs para clientes corporativos?"*
5. **Comportamento esperado**: O backend aplica os filtros vetoriais na busca do pgvector, restringindo a recuperação aos documentos B2B/Enterprise da TeleTech.
6. Clique no botão **Limpar filtros** para resetar os filtros a qualquer momento.

---

## 📂 Estrutura do Projeto

```text
chat_specialist/
├── .agents/                    # Agentes e personas especializadas
├── frontend/                   # Interface Web Next.js (Minimalist Dark UI)
│   ├── app/
│   │   ├── api/
│   │   │   ├── chat/route.ts   # Proxy para POST /api/v1/chat
│   │   │   └── stream/route.ts # Proxy SSE para POST /api/v1/chat/stream
│   │   ├── globals.css         # Tailwind + customização de scrollbar dark
│   │   ├── layout.tsx          # Root Layout com fonte Inter e tema dark
│   │   └── page.tsx            # Página principal com Suspense boundary
│   ├── components/
│   │   ├── ChatInterface.tsx   # Container principal de chat (normal + stream)
│   │   ├── FilterPanel.tsx     # Painel de filtros retrátil (tenant, audience, plan)
│   │   ├── MessageBubble.tsx   # Bolha de mensagem otimizada com React.memo
│   │   └── SourcesPanel.tsx    # Accordion de fontes com React.memo
│   ├── .env.local              # URL base da API backend (http://localhost:8000)
│   ├── next.config.ts          # Configuração Next.js
│   ├── package.json            # Scripts e dependências do frontend
│   └── tailwind.config.ts      # Configuração do Tailwind CSS
├── knowledge_docs/             # Base de documentos oficiais da operadora (.md com frontmatter)
├── src/
│   ├── controllers/            # Roteadores da API (chat, ingestão, health)
│   │   ├── chat_controller.py
│   │   ├── health_controller.py
│   │   └── ingestion_controller.py
│   ├── infra/                  # Conexão com banco, fábrica de modelos e configurações
│   │   ├── ai_factory.py       # Chat model e embeddings (Gemini/OpenAI)
│   │   ├── config.py
│   │   └── database.py
│   ├── schemas/                # Schemas Pydantic de validação e I/O
│   │   ├── chat.py
│   │   └── ingestion.py
│   ├── services/               # Lógica de negócio e pipelines RAG (LCEL)
│   │   ├── ingestion.py        # Splitter hierárquico e ingestão PGVector
│   │   ├── query_planner.py    # Clarificação de intenção da pergunta via LLM
│   │   └── rag_service.py      # Cadeia LangChain LCEL e busca vetorial
│   ├── utils/                  # Scripts auxiliares, migração de banco e telemetria
│   │   ├── create_database.py
│   │   └── telemetry.py        # OpenTelemetry (tracer, helpers e callback de LLM)
│   └── main.py                 # Ponto de entrada FastAPI com lifespan e middlewares
├── docker-compose.yml          # PostgreSQL com pgvector + Jaeger (profile `jaeger`)
├── requirements.txt            # Dependências Python
└── README.md                   # Instruções de execução e documentação
```
