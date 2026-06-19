"""Semantic retrieval system with hybrid search and reranking."""

from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, Field

from agent.memory.embeddings import EmbeddingGenerator
from agent.memory.episodic import EpisodicMemory, Episode
from agent.memory.procedural import LearnedPattern, ProceduralMemory


class RetrievalResult(BaseModel):
    """Result from semantic retrieval with relevance score."""

    content: str = Field(description="Retrieved content")
    source_type: Literal["episodic", "procedural"] = Field(description="Memory source")
    relevance_score: float = Field(description="Relevance score (0-1)")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class SemanticRetriever:
    """Unified semantic retrieval across episodic and procedural memory."""

    def __init__(
        self,
        episodic_memory: EpisodicMemory,
        procedural_memory: ProceduralMemory,
        embedder: EmbeddingGenerator,
        rerank_threshold: float = 0.5,
    ):
        """Initialize semantic retriever.

        Args:
            episodic_memory: Episodic memory instance
            procedural_memory: Procedural memory instance
            embedder: Embedding generator for reranking
            rerank_threshold: Minimum score to keep after reranking
        """
        self.episodic_memory = episodic_memory
        self.procedural_memory = procedural_memory
        self.embedder = embedder
        self.rerank_threshold = rerank_threshold

    async def retrieve_context(
        self,
        query: str,
        session_id: str | None = None,
        include_episodic: bool = True,
        include_procedural: bool = True,
        max_results: int = 10,
    ) -> list[RetrievalResult]:
        """Retrieve relevant context from memory using hybrid search.

        Args:
            query: Search query
            session_id: Optional session filter for episodic memory
            include_episodic: Include conversation history
            include_procedural: Include learned patterns
            max_results: Maximum results to return

        Returns:
            List of relevant results, ranked by relevance
        """
        results = []

        # Search episodic memory (recent conversations)
        if include_episodic:
            episodes = await self.episodic_memory.search_episodes(
                query=query,
                session_id=session_id,
                limit=max_results,
            )

            for episode in episodes:
                results.append(
                    RetrievalResult(
                        content=episode.content,
                        source_type="episodic",
                        relevance_score=0.8,  # Initial score, will be reranked
                        metadata={
                            "episode_id": episode.id,
                            "role": episode.role,
                            "timestamp": episode.timestamp.isoformat(),
                            "session_id": episode.session_id,
                        },
                    )
                )

        # Search procedural memory (learned patterns)
        if include_procedural:
            patterns = await self.procedural_memory.search_patterns(
                query=query,
                limit=max_results,
            )

            for pattern in patterns:
                # Format pattern as readable context
                content = f"Pattern: {pattern.context}\n\nSolution: {pattern.solution}\n\nSuccess rate: {pattern.success_rate:.1%} (used {pattern.success_count + pattern.failure_count} times)"

                results.append(
                    RetrievalResult(
                        content=content,
                        source_type="procedural",
                        relevance_score=pattern.confidence,  # Use pattern confidence
                        metadata={
                            "pattern_id": pattern.id,
                            "pattern_type": pattern.pattern_type,
                            "confidence": pattern.confidence,
                            "success_rate": pattern.success_rate,
                        },
                    )
                )

        # Rerank results based on query similarity
        if results:
            results = await self._rerank_results(query, results)

        # Filter by threshold and limit
        results = [r for r in results if r.relevance_score >= self.rerank_threshold]
        return results[:max_results]

    async def _rerank_results(
        self, query: str, results: list[RetrievalResult]
    ) -> list[RetrievalResult]:
        """Rerank results using cross-encoder or similarity scoring.

        Args:
            query: Original query
            results: Initial results to rerank

        Returns:
            Reranked results sorted by relevance
        """
        # Simple reranking using embedding similarity
        # In production, could use cross-encoder models for better accuracy

        if not results:
            return results

        # Generate embeddings
        query_emb = await self.embedder.encode_text(query)
        contents = [r.content for r in results]
        content_embs = await self.embedder.encode_batch(contents)

        # Calculate cosine similarity scores
        import numpy as np

        query_vec = np.array(query_emb)
        for result, content_emb in zip(results, content_embs):
            content_vec = np.array(content_emb)

            # Cosine similarity
            similarity = np.dot(query_vec, content_vec) / (
                np.linalg.norm(query_vec) * np.linalg.norm(content_vec)
            )

            # Blend with initial score (60% rerank, 40% initial)
            result.relevance_score = 0.6 * float(similarity) + 0.4 * result.relevance_score

        # Sort by relevance score
        results.sort(key=lambda r: r.relevance_score, reverse=True)

        return results

    async def retrieve_similar_episodes(
        self,
        query: str,
        session_id: str | None = None,
        max_results: int = 5,
    ) -> list[Episode]:
        """Retrieve similar conversation episodes.

        Args:
            query: Search query
            session_id: Optional session filter
            max_results: Maximum episodes to return

        Returns:
            List of similar episodes
        """
        return await self.episodic_memory.search_episodes(
            query=query,
            session_id=session_id,
            limit=max_results,
        )

    async def retrieve_relevant_patterns(
        self,
        query: str,
        pattern_type: str | None = None,
        max_results: int = 5,
    ) -> list[LearnedPattern]:
        """Retrieve relevant learned patterns.

        Args:
            query: Context or problem description
            pattern_type: Optional pattern type filter
            max_results: Maximum patterns to return

        Returns:
            List of relevant patterns
        """
        return await self.procedural_memory.search_patterns(
            query=query,
            pattern_type=pattern_type,
            limit=max_results,
        )

    async def build_context_prompt(
        self,
        query: str,
        session_id: str | None = None,
        max_tokens: int = 2000,
    ) -> str:
        """Build a context prompt from relevant memory.

        Args:
            query: Current query or task
            session_id: Optional session for recent history
            max_tokens: Approximate max tokens for context

        Returns:
            Formatted context string for LLM prompt
        """
        # Retrieve relevant context
        results = await self.retrieve_context(
            query=query,
            session_id=session_id,
            max_results=10,
        )

        # Build context sections
        context_parts = []

        # Separate by source type
        episodes = [r for r in results if r.source_type == "episodic"]
        patterns = [r for r in results if r.source_type == "procedural"]

        # Add recent conversation context
        if episodes:
            context_parts.append("## Recent Conversation Context\n")
            for i, result in enumerate(episodes[:5], 1):
                role = result.metadata.get("role", "unknown")
                context_parts.append(f"{i}. [{role}]: {result.content}\n")

        # Add relevant learned patterns
        if patterns:
            context_parts.append("\n## Relevant Learned Patterns\n")
            for i, result in enumerate(patterns[:3], 1):
                pattern_type = result.metadata.get("pattern_type", "solution")
                context_parts.append(f"{i}. [{pattern_type}]: {result.content}\n")

        # Combine and limit length (rough token estimation: 1 token ≈ 4 chars)
        context = "".join(context_parts)
        max_chars = max_tokens * 4

        if len(context) > max_chars:
            context = context[:max_chars] + "\n... (context truncated)"

        return context


async def create_semantic_retriever(
    episodic_memory: EpisodicMemory,
    procedural_memory: ProceduralMemory,
    embedder: EmbeddingGenerator,
) -> SemanticRetriever:
    """Factory function to create configured semantic retriever.

    Args:
        episodic_memory: Episodic memory instance
        procedural_memory: Procedural memory instance
        embedder: Embedding generator

    Returns:
        Configured SemanticRetriever
    """
    return SemanticRetriever(
        episodic_memory=episodic_memory,
        procedural_memory=procedural_memory,
        embedder=embedder,
        rerank_threshold=0.5,
    )
