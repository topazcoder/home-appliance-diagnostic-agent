"""
Ingest repair documents into the pgvector knowledge base.

Usage:
    python -m app.utils.ingest \
        --file docs/whirlpool_washer.txt \
        --appliance washer \
        --source whirlpool_washer_manual \
        --tags "leaking,not spinning,noisy"
"""
import asyncio
import argparse
import openai
from app.db.database import engine, AsyncSessionLocal
from app.db.models import Base
from app.repositories.knowledge_repository import KnowledgeRepository
from app.settings import EMBEDDING_MODEL, OPENAI_API_KEY

openai_client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)

CHUNK_SIZE    = 500
CHUNK_OVERLAP = 50


def split_into_chunks(text: str) -> list[str]:
    chunks, start = [], 0
    while start < len(text):
        end = start + CHUNK_SIZE
        chunks.append(text[start:end].strip())
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return [c for c in chunks if len(c) > 50]


async def embed_batch(texts: list[str]) -> list[list[float]]:
    response = await openai_client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=texts,
    )
    return [item.embedding for item in response.data]


async def ingest_file(filepath: str, appliance_type: str, source: str, tags: str = ""):
    with open(filepath, "r") as f:
        raw_text = f.read()

    chunks = split_into_chunks(raw_text)
    print(f"📄 {len(chunks)} chunks from '{filepath}'")

    all_embeddings = []
    for i in range(0, len(chunks), 100):
        batch      = chunks[i : i + 100]
        embeddings = await embed_batch(batch)
        all_embeddings.extend(embeddings)
        print(f"  ✅ Embedded {min(i + 100, len(chunks))}/{len(chunks)}")

    async with AsyncSessionLocal() as db:
        repo = KnowledgeRepository(db)
        for chunk_text, embedding in zip(chunks, all_embeddings):
            await repo.insert_chunk(
                appliance_type=appliance_type,
                symptom_tags=tags,
                source=source,
                content=chunk_text,
                embedding=embedding,
            )

    print(f"✅ Ingested {len(chunks)} chunks → knowledge_chunks")


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file",      required=True)
    parser.add_argument("--appliance", required=True)
    parser.add_argument("--source",    required=True)
    parser.add_argument("--tags",      default="")
    args = parser.parse_args()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await ingest_file(args.file, args.appliance, args.source, args.tags)


if __name__ == "__main__":
    asyncio.run(main())
