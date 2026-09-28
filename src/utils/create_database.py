import asyncio
from sqlalchemy import text
from src.infra.database import database


async def test_connection():
    async with database.session() as session:
        try:
            result = await session.execute(text("SELECT 1;"))
            print("Conexão com PostgreSQL bem-sucedida! OK:", result.scalar())
        except Exception as e:
            print(f"Erro ao testar a conexão com o banco de dados: {e}")


async def enable_pgvector():
    async with database.session() as session:
        try:
            await session.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            await session.commit()
            print("Extensão pgvector ativada com sucesso ou já existente!")
        except Exception as e:
            print(f"Erro ao ativar a extensão pgvector: {e}")


async def main():
    print("Iniciando rotinas de banco de dados...")
    await test_connection()
    await enable_pgvector()


if __name__ == "__main__":
    import sys

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
