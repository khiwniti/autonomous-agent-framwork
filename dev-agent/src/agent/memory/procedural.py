"""Procedural memory for learning and storing reusable patterns."""

import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

from agent.memory.embeddings import EmbeddingGenerator
from agent.memory.vector_store import VectorDocument, VectorStore


class LearnedPattern(BaseModel):
    """A learned pattern that can be reused in future interactions."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Pattern ID")
    pattern_type: Literal["solution", "error", "optimization", "workflow"] = Field(
        description="Type of pattern learned"
    )
    context: str = Field(description="Context where pattern applies")
    solution: str = Field(description="The learned solution or approach")
    success_count: int = Field(default=1, description="How many times successfully applied")
    failure_count: int = Field(default=0, description="How many times it failed")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="When pattern was learned"
    )
    last_used: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="Last time pattern was used"
    )
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    @property
    def success_rate(self) -> float:
        """Calculate success rate of this pattern."""
        total = self.success_count + self.failure_count
        return self.success_count / total if total > 0 else 0.0

    @property
    def confidence(self) -> float:
        """Calculate confidence score (0-1) based on usage and success."""
        # Confidence increases with successful uses, caps at 1.0
        # Formula: min(1.0, success_rate * log(total_uses + 1) / 3)
        import math

        total = self.success_count + self.failure_count
        if total == 0:
            return 0.5  # Neutral confidence for unused patterns

        usage_factor = math.log(total + 1) / 3  # Increases confidence with more uses
        return min(1.0, self.success_rate * usage_factor)


class ProceduralMemory:
    """Manage procedural memory for learned patterns and solutions."""

    def __init__(
        self,
        vector_store: VectorStore,
        embedder: EmbeddingGenerator,
        min_confidence: float = 0.6,
        max_patterns: int = 10000,
    ):
        """Initialize procedural memory.

        Args:
            vector_store: Vector store for semantic pattern matching
            embedder: Embedding generator
            min_confidence: Minimum confidence to return pattern
            max_patterns: Maximum patterns to store (for cleanup)
        """
        self.vector_store = vector_store
        self.embedder = embedder
        self.min_confidence = min_confidence
        self.max_patterns = max_patterns

    async def initialize(self) -> None:
        """Initialize memory storage."""
        await self.vector_store.initialize()

    async def add_pattern(self, pattern: LearnedPattern) -> None:
        """Add a learned pattern to memory.

        Args:
            pattern: Pattern to store
        """
        # Generate embedding from context + solution
        combined_text = f"{pattern.context}\n\n{pattern.solution}"
        embedding = await self.embedder.encode_text(combined_text)

        # Create vector document
        doc = VectorDocument(
            id=pattern.id,
            content=combined_text,
            embedding=embedding,
            metadata={
                "pattern_type": pattern.pattern_type,
                "context": pattern.context,
                "solution": pattern.solution,
                "success_count": pattern.success_count,
                "failure_count": pattern.failure_count,
                "created_at": pattern.created_at.isoformat(),
                "last_used": pattern.last_used.isoformat(),
                **pattern.metadata,
            },
        )

        await self.vector_store.add_documents([doc])

    async def search_patterns(
        self,
        query: str,
        pattern_type: str | None = None,
        limit: int = 10,
    ) -> list[LearnedPattern]:
        """Search for relevant patterns based on context.

        Args:
            query: Context or problem description
            pattern_type: Optional filter by pattern type
            limit: Max patterns to return

        Returns:
            List of relevant patterns, sorted by relevance and confidence
        """
        # Generate query embedding
        query_embedding = await self.embedder.encode_query(query)

        # Build metadata filters
        filter_metadata = {}
        if pattern_type:
            filter_metadata["pattern_type"] = pattern_type

        # Search vector store
        results = await self.vector_store.search(
            query_embedding=query_embedding,
            limit=limit * 2,  # Get more to filter by confidence
            filter_metadata=filter_metadata or None,
        )

        # Convert to LearnedPattern objects and filter by confidence
        patterns = []
        for result in results:
            pattern = LearnedPattern(
                id=result.id,
                pattern_type=result.metadata.get("pattern_type", "solution"),
                context=result.metadata.get("context", ""),
                solution=result.metadata.get("solution", ""),
                success_count=result.metadata.get("success_count", 1),
                failure_count=result.metadata.get("failure_count", 0),
                created_at=datetime.fromisoformat(
                    result.metadata.get("created_at", datetime.now(timezone.utc).isoformat())
                ),
                last_used=datetime.fromisoformat(
                    result.metadata.get("last_used", datetime.now(timezone.utc).isoformat())
                ),
                metadata={
                    k: v
                    for k, v in result.metadata.items()
                    if k
                    not in (
                        "pattern_type",
                        "context",
                        "solution",
                        "success_count",
                        "failure_count",
                        "created_at",
                        "last_used",
                    )
                },
            )

            # Filter by confidence threshold
            if pattern.confidence >= self.min_confidence:
                patterns.append(pattern)

            if len(patterns) >= limit:
                break

        return patterns

    async def record_success(self, pattern_id: str) -> None:
        """Record successful application of a pattern.

        Args:
            pattern_id: Pattern that was successfully applied
        """
        # Retrieve pattern
        doc = await self.vector_store.get_document(pattern_id)
        if not doc:
            return

        # Update success count and last_used
        success_count = doc.metadata.get("success_count", 0) + 1
        pattern = LearnedPattern(
            id=pattern_id,
            pattern_type=doc.metadata.get("pattern_type", "solution"),
            context=doc.metadata.get("context", ""),
            solution=doc.metadata.get("solution", ""),
            success_count=success_count,
            failure_count=doc.metadata.get("failure_count", 0),
            created_at=datetime.fromisoformat(
                doc.metadata.get("created_at", datetime.now(timezone.utc).isoformat())
            ),
            last_used=datetime.now(timezone.utc),
            metadata={
                k: v
                for k, v in doc.metadata.items()
                if k
                not in (
                    "pattern_type",
                    "context",
                    "solution",
                    "success_count",
                    "failure_count",
                    "created_at",
                    "last_used",
                )
            },
        )

        # Re-add pattern with updated counts
        await self.add_pattern(pattern)

    async def record_failure(self, pattern_id: str) -> None:
        """Record failed application of a pattern.

        Args:
            pattern_id: Pattern that failed
        """
        # Retrieve pattern
        doc = await self.vector_store.get_document(pattern_id)
        if not doc:
            return

        # Update failure count and last_used
        failure_count = doc.metadata.get("failure_count", 0) + 1
        pattern = LearnedPattern(
            id=pattern_id,
            pattern_type=doc.metadata.get("pattern_type", "solution"),
            context=doc.metadata.get("context", ""),
            solution=doc.metadata.get("solution", ""),
            success_count=doc.metadata.get("success_count", 0),
            failure_count=failure_count,
            created_at=datetime.fromisoformat(
                doc.metadata.get("created_at", datetime.now(timezone.utc).isoformat())
            ),
            last_used=datetime.now(timezone.utc),
            metadata={
                k: v
                for k, v in doc.metadata.items()
                if k
                not in (
                    "pattern_type",
                    "context",
                    "solution",
                    "success_count",
                    "failure_count",
                    "created_at",
                    "last_used",
                )
            },
        )

        # Re-add pattern with updated counts
        await self.add_pattern(pattern)

    async def close(self) -> None:
        """Close memory connections."""
        await self.vector_store.close()


async def learn_from_experience(
    procedural_memory: ProceduralMemory,
    pattern_type: str,
    context: str,
    solution: str,
    metadata: dict[str, Any] | None = None,
) -> LearnedPattern:
    """Helper to learn a pattern from an experience.

    Args:
        procedural_memory: Procedural memory instance
        pattern_type: Type of pattern (solution, error, optimization, workflow)
        context: Context where pattern applies
        solution: The learned solution
        metadata: Additional metadata

    Returns:
        Created LearnedPattern
    """
    pattern = LearnedPattern(
        pattern_type=pattern_type,
        context=context,
        solution=solution,
        metadata=metadata or {},
    )

    await procedural_memory.add_pattern(pattern)
    return pattern
