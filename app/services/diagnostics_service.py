import openai

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.knowledge_repository import KnowledgeRepository
from app.settings import (
    EMBEDDING_MODEL,
    LLM_MODEL,
    OPENAI_API_KEY,
    RAG_TOK_K,
)

openai_client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)


class DiagnosticsService:
    def __init__(self, db: AsyncSession) -> None:
        self.repository = KnowledgeRepository(db)
    
    async def _embed(self, text: str) -> list[float]:
        response = await openai_client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=text,
        )
        
        return response.data[0].embedding
    
    async def _generate_diagnosis(
        self,
        appliance_type: str,
        symptoms: str,
        chunks: list[dict],
    ) -> str:
        if not chunks:
            return (
                f"I wasn't able to find specific guidance for a {appliance_type} "
                f"with the symptom '{symptoms}' in our knowledge base. "
                "A technician visit is recommended."
            )

        context_block = "\n\n---\n\n".join(
            f"[Source; {c['source']}\n{c['content']}]" for c in chunks
        )

        response = await openai_client.chat.completions.create(
            model=LLM_MODEL,
            max_tokens=1024,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert appliance repair technician. "
                        "Use the reference material provided to give diagnostic guidance. "
                        "DO NOT invent steps not supported by the reference material."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"## Reference Material\n{context_block}\n\n"
                        f"## Customer's Appliance\n"
                        f"Type: {appliance_type}\n"
                        f"Reported Symptoms: {symptoms}\n\n"
                        "Provide numbered troubleshooting steps the customer can try at home. "
                        "End with a recommendation on whether a technician visit is needed."
                    ),
                },
            ],
        )

        return response.choices[0].message.content

    async def diagnose(self, appliance_type: str, symptoms: str) -> dict:
        # Step 1 - embed the user's query
        query_embedding = await self._embed(f"{appliance_type} {symptoms}")

        # Step 2 - retrieve the most relevant chunks from pgvector
        chunks = await self.repository.similarity_search(
            query_embedding=query_embedding,
            appliance_type=appliance_type,
            top_k=RAG_TOK_K,
        )
        diagnosis = await self._generate_diagnosis(appliance_type, symptoms, chunks)

        return {
            "found": len(chunks) > 0,
            "appliance": appliance_type,
            "symptom": symptoms,
            "diagnosis": diagnosis,
            "sources": [c["source"] for c in chunks],
            "chunks_used": len(chunks),
        }
