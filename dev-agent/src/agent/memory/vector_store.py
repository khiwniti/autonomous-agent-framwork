"""Vector store abstraction for semantic memory storage and retrieval."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, TypedDict

from pydantic import BaseModel, Field
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qdrant_models


class VectorDocument(BaseModel):
    """Document with vector embedding for storage."""

    id: str = Field(description="Unique document ID")
    content: str = Field(description="Original text content")
    embedding: list[float] = Field(description="Vector embedding")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )


class SearchResult(BaseModel):
    """Search result from vector store."""

    id: str = Field(description="Document ID")
    content: str = Field(description="Retrieved content")
    score: float = Field(description="Similarity score (0-1)")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Document metadata"
    )


class VectorStore(ABC):
    """Abstract base class for vector storage backends."""

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the vector store (create collections, etc.)."""
        pass

    @abstractmethod
    async def add_documents(self, documents: list[VectorDocument]) -> None:
        """Add documents with embeddings to the store."""
        pass

    @abstractmethod
    async def search(
        self,
        query_embedding: list[float],
        limit: int = 10,
        filter_metadata: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Search for similar documents by embedding."""
        pass

    @abstractmethod
    async def delete_documents(self, document_ids: list[str]) -> None:
        """Delete documents by ID."""
        pass

    @abstractmethod
    async def get_document(self, document_id: str) -> VectorDocument | None:
        """Retrieve a specific document by ID."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close connections and cleanup resources."""
        pass


class QdrantVectorStore(VectorStore):
    """Qdrant vector store implementation."""

    def __init__(
        self,
        collection_name: str,
        embedding_dim: int,
        host: str = "localhost",
        port: int = 6333,
        api_key: str | None = None,
        use_memory: bool = False,
    ):
        """Initialize Qdrant vector store.

        Args:
            collection_name: Name of the collection
            embedding_dim: Dimension of embeddings
            host: Qdrant server host
            port: Qdrant server port
            api_key: Optional API key for authentication
            use_memory: Use in-memory storage (for testing)
        """
        self.collection_name = collection_name
        self.embedding_dim = embedding_dim
        self.use_memory = use_memory

        if use_memory:
            # In-memory mode for testing
            self.client = AsyncQdrantClient(location=":memory:")
        else:
            # Remote Qdrant server
            self.client = AsyncQdrantClient(
                host=host, port=port, api_key=api_key, timeout=30.0
            )

        self._initialized = False

    async def initialize(self) -> None:
        """Initialize collection with vector configuration."""
        if self._initialized:
            return

        # Check if collection exists
        collections = await self.client.get_collections()
        collection_names = [c.name for c in collections.collections]

        if self.collection_name not in collection_names:
            # Create collection with vector configuration
            await self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=qdrant_models.VectorParams(
                    size=self.embedding_dim,
                    distance=qdrant_models.Distance.COSINE,
                ),
            )

        self._initialized = True

    async def add_documents(self, documents: list[VectorDocument]) -> None:
        """Add documents to Qdrant collection."""
        if not self._initialized:
            await self.initialize()

        points = [
            qdrant_models.PointStruct(
                id=doc.id,
                vector=doc.embedding,
                payload={"content": doc.content, **doc.metadata},
            )
            for doc in documents
        ]

        await self.client.upsert(collection_name=self.collection_name, points=points)

    async def search(
        self,
        query_embedding: list[float],
        limit: int = 10,
        filter_metadata: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Search for similar documents in Qdrant."""
        if not self._initialized:
            await self.initialize()

        # Build filter if provided
        query_filter = None
        if filter_metadata:
            must_conditions = [
                qdrant_models.FieldCondition(
                    key=key,
                    match=qdrant_models.MatchValue(value=value),
                )
                for key, value in filter_metadata.items()
            ]
            query_filter = qdrant_models.Filter(must=must_conditions)

        # Execute search
        search_results = await self.client.search(
            collection_name=self.collection_name,
            query_vector=query_embedding,
            limit=limit,
            query_filter=query_filter,
        )

        # Convert to SearchResult objects
        results = []
        for hit in search_results:
            payload = hit.payload or {}
            results.append(
                SearchResult(
                    id=str(hit.id),
                    content=payload.get("content", ""),
                    score=hit.score,
                    metadata={k: v for k, v in payload.items() if k != "content"},
                )
            )

        return results

    async def delete_documents(self, document_ids: list[str]) -> None:
        """Delete documents from Qdrant collection."""
        if not self._initialized:
            await self.initialize()

        await self.client.delete(
            collection_name=self.collection_name,
            points_selector=qdrant_models.PointIdsList(points=document_ids),
        )

    async def get_document(self, document_id: str) -> VectorDocument | None:
        """Retrieve a specific document from Qdrant."""
        if not self._initialized:
            await self.initialize()

        points = await self.client.retrieve(
            collection_name=self.collection_name, ids=[document_id]
        )

        if not points:
            return None

        point = points[0]
        payload = point.payload or {}

        return VectorDocument(
            id=str(point.id),
            content=payload.get("content", ""),
            embedding=point.vector,
            metadata={k: v for k, v in payload.items() if k != "content"},
        )

    async def close(self) -> None:
        """Close Qdrant client connection."""
        await self.client.close()
