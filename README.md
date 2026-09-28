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
- **Containerização**: Docker Compose

---

## 📋 Pré-requisitos

1. **Python 3.12 ou superior** instalado.
2. **Docker e Docker Compose** instalados e em execução.
3. **Chave de API do Google Gemini** (`GOOGLE_API_KEY`) ou **OpenAI** (`OPENAI_API_KEY`).

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
```
OPENAI_CHAT_MODEL=gpt-4.1-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

---

## 🗄️ Inicialização do Banco de Dados (pgvector)

### 1. Subir o PostgreSQL via Docker Compose

Inicie o contêiner do PostgreSQL com `pgvector`:

```powershell
docker compose up -d
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
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
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
  "latency_ms": 1150.32
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

## 📂 Estrutura do Projeto

```text
chat_specialist/
├── .agents/                    # Agentes e personas especializadas
├── knowledge_docs/             # Base de documentos oficiais da operadora (.md com frontmatter)
├── src/
│   ├── controllers/            # Roteadores da API (chat, ingestão, health)
│   │   ├── chat_controller.py
│   │   ├── health_controller.py
│   │   └── ingestion_controller.py
│   ├── infra/                  # Conexão com banco e carregamento de configurações
│   │   ├── config.py
│   │   └── database.py
│   ├── schemas/                # Schemas Pydantic de validação e I/O
│   │   ├── chat.py
│   │   └── ingestion.py
│   ├── services/               # Lógica de negócio e pipelines RAG (LCEL)
│   │   ├── ingestion.py        # Splitter hierárquico e ingestão PGVector
│   │   └── rag_service.py      # Cadeia LangChain LCEL e busca vetorial
│   ├── utils/                  # Scripts auxiliares e migração de banco
│   │   └── create_database.py
│   └── main.py                 # Ponto de entrada FastAPI com lifespan e middlewares
├── docker-compose.yml          # Container PostgreSQL com pgvector
├── requirements.txt            # Dependências Python
└── README.md                   # Instruções de execução e documentação
```
