from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import KnowledgeChunkModel


class KnowledgeRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def similarity_search(
        self,
        query_embedding: list[float],
        appliance_type: str,
        top_k: int,
    ) -> list[dict]:
        result = await self.db.execute(
            text("""
                SELECT content, source, symptom_tags,
                       1 - (embedding <=> CAST(:embedding AS vector)) AS similarity
                FROM knowledge_chunks
                WHERE appliance_type = :appliance_type
                ORDER BY embedding <=> CAST(:embedding AS vector)
                LIMIT :top_k
            """),
            {
                "embedding":      str(query_embedding),
                "appliance_type": appliance_type.lower(),
                "top_k":          top_k,
            },
        )
        rows = result.fetchall()
        return [
            {
                "content":      row.content,
                "source":       row.source,
                "symptom_tags": row.symptom_tags,
                "similarity":   round(row.similarity, 4),
            }
            for row in rows
        ]
    
    async def insert_chunk(
        self,
        appliance_type: str,
        symptom_tags: str | None,
        source: str | None,
        content: str,
        embedding: list[float],
    ) -> KnowledgeChunkModel:
        chunk = KnowledgeChunkModel(
            appliance_type=appliance_type.lower(),
            symptom_tags=symptom_tags,
            source=source,
            content=content,
            embedding=embedding,
        )
        self.db.add(chunk)
        await self.db.commit()
        await self.db.refresh(chunk)
        return chunk
