"""Episodic memory storage for conversation history and agent experiences."""

import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from agent.memory.embeddings import EmbeddingGenerator
from agent.memory.vector_store import VectorDocument, VectorStore


class Episode(BaseModel):
    """An episode in agent memory (conversation turn or action)."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Episode ID")
    session_id: str = Field(description="Session this episode belongs to")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="When episode occurred"
    )
    role: str = Field(description="Role (user, assistant, system, tool)")
    content: str = Field(description="Episode content")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class EpisodicMemory:
    """Manage episodic memory for agent conversations and experiences."""

    def __init__(
        self,
        vector_store: VectorStore,
        embedder: EmbeddingGenerator,
        max_episodes_per_session: int = 1000,
    ):
        """Initialize episodic memory.

        Args:
            vector_store: Vector store for semantic search
            embedder: Embedding generator
            max_episodes_per_session: Max episodes to store per session (for cleanup)
        """
        self.vector_store = vector_store
        self.embedder = embedder
        self.max_episodes_per_session = max_episodes_per_session

    async def initialize(self) -> None:
        """Initialize memory storage."""
        await self.vector_store.initialize()

    async def add_episode(self, episode: Episode) -> None:
        """Add an episode to memory.

        Args:
            episode: Episode to store
        """
        # Generate embedding for the content
        embedding = await self.embedder.encode_text(episode.content)

        # Create vector document with episode data in metadata
        doc = VectorDocument(
            id=episode.id,
            content=episode.content,
            embedding=embedding,
            metadata={
                "session_id": episode.session_id,
                "timestamp": episode.timestamp.isoformat(),
                "role": episode.role,
                **episode.metadata,
            },
        )

        await self.vector_store.add_documents([doc])

    async def add_episodes(self, episodes: list[Episode]) -> None:
        """Add multiple episodes efficiently.

        Args:
            episodes: Episodes to store
        """
        if not episodes:
            return

        # Generate embeddings in batch
        contents = [ep.content for ep in episodes]
        embeddings = await self.embedder.encode_batch(contents)

        # Create vector documents
        documents = []
        for episode, embedding in zip(episodes, embeddings):
            doc = VectorDocument(
                id=episode.id,
                content=episode.content,
                embedding=embedding,
                metadata={
                    "session_id": episode.session_id,
                    "timestamp": episode.timestamp.isoformat(),
                    "role": episode.role,
                    **episode.metadata,
                },
            )
            documents.append(doc)

        await self.vector_store.add_documents(documents)

    async def search_episodes(
        self,
        query: str,
        session_id: str | None = None,
        role: str | None = None,
        limit: int = 10,
    ) -> list[Episode]:
        """Search for relevant episodes semantically.

        Args:
            query: Search query text
            session_id: Optional filter by session
            role: Optional filter by role
            limit: Max number of results

        Returns:
            List of relevant episodes, sorted by relevance
        """
        # Generate query embedding
        query_embedding = await self.embedder.encode_query(query)

        # Build metadata filters
        filter_metadata = {}
        if session_id:
            filter_metadata["session_id"] = session_id
        if role:
            filter_metadata["role"] = role

        # Search vector store
        results = await self.vector_store.search(
            query_embedding=query_embedding,
            limit=limit,
            filter_metadata=filter_metadata or None,
        )

        # Convert to Episode objects
        episodes = []
        for result in results:
            episode = Episode(
                id=result.id,
                content=result.content,
                session_id=result.metadata.get("session_id", ""),
                role=result.metadata.get("role", ""),
                timestamp=datetime.fromisoformat(result.metadata.get("timestamp", datetime.now(timezone.utc).isoformat())),
                metadata={
                    k: v
                    for k, v in result.metadata.items()
                    if k not in ("session_id", "role", "timestamp")
                },
            )
            episodes.append(episode)

        return episodes

    async def get_session_episodes(
        self,
        session_id: str,
        limit: int = 100,
        role: str | None = None,
    ) -> list[Episode]:
        """Get recent episodes from a session.

        Args:
            session_id: Session to retrieve from
            limit: Max episodes to return
            role: Optional filter by role

        Returns:
            List of episodes from session
        """
        # For now, use search with empty query - will return by relevance
        # In production, would query database directly with timestamp ordering
        return await self.search_episodes(
            query="",  # Empty query with filter
            session_id=session_id,
            role=role,
            limit=limit,
        )

    async def delete_session(self, session_id: str) -> None:
        """Delete all episodes from a session.

        Args:
            session_id: Session to delete
        """
        # Note: This is a simplified implementation
        # In production, would query all episode IDs first, then delete
        # For now, assumes external tracking of episode IDs per session
        pass

    async def close(self) -> None:
        """Close memory connections."""
        await self.vector_store.close()


async def create_conversation_episode(
    session_id: str,
    role: str,
    content: str,
    metadata: dict[str, Any] | None = None,
) -> Episode:
    """Helper to create a conversation episode.

    Args:
        session_id: Session ID
        role: Role (user, assistant, system, tool)
        content: Message content
        metadata: Additional metadata

    Returns:
        Episode object
    """
    return Episode(
        session_id=session_id,
        role=role,
        content=content,
        metadata=metadata or {},
    )
