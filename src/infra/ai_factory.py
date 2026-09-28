from src.infra.config import settings


def get_embeddings():
    """Retorna a instância de embeddings configurada (Google Gemini ou OpenAI)."""
    if settings.AI_PROVIDER.lower() == "google" or (settings.GOOGLE_API_KEY and not settings.OPENAI_API_KEY):
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        return GoogleGenerativeAIEmbeddings(
            model=settings.GOOGLE_EMBEDDING_MODEL,
            google_api_key=settings.GOOGLE_API_KEY,
        )
    else:
        from langchain_openai import OpenAIEmbeddings

        return OpenAIEmbeddings(
            model=settings.OPENAI_EMBEDDING_MODEL,
            api_key=settings.OPENAI_API_KEY,
        )


def get_chat_model():
    """Retorna o modelo de chat LLM configurado (Google Gemini ou OpenAI)."""
    if settings.AI_PROVIDER.lower() == "google" or (settings.GOOGLE_API_KEY and not settings.OPENAI_API_KEY):
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=settings.GOOGLE_CHAT_MODEL,
            google_api_key=settings.GOOGLE_API_KEY,
            temperature=0.0,
        )
    else:
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=settings.OPENAI_CHAT_MODEL,
            api_key=settings.OPENAI_API_KEY,
            temperature=0.0,
        )


def get_collection_name() -> str:
    """Retorna o nome da collection no pgvector de acordo com o provedor (evita conflito de dimensões 768 vs 1536)."""
    if settings.AI_PROVIDER.lower() == "google" or (settings.GOOGLE_API_KEY and not settings.OPENAI_API_KEY):
        return "document_chunks_gemini"
    return "document_chunks_openai"
