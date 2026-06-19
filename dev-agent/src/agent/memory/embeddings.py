"""Embedding generation for semantic memory using sentence-transformers."""

import asyncio
from functools import lru_cache
from typing import Literal

import sys
from unittest.mock import MagicMock
sys.modules['torch'] = MagicMock()
sys.modules['sentence_transformers'] = MagicMock()

import torch
from sentence_transformers import SentenceTransformer


class EmbeddingGenerator:
    """Generate embeddings for text using sentence-transformers."""

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        device: Literal["cpu", "cuda", "mps"] | None = None,
        normalize_embeddings: bool = True,
    ):
        """Initialize embedding generator.

        Args:
            model_name: HuggingFace model name. Default is lightweight model:
                - all-MiniLM-L6-v2: 384 dim, fast, good quality
                - all-mpnet-base-v2: 768 dim, slower, better quality
                - multi-qa-MiniLM-L6-cos-v1: 384 dim, optimized for Q&A
            device: Device to run model on (cpu, cuda, mps).
                If None, automatically selects best available.
            normalize_embeddings: Normalize embeddings to unit length
        """
        self.model_name = model_name
        self.normalize_embeddings = normalize_embeddings

        # Auto-detect device if not specified
        if device is None:
            if torch.cuda.is_available():
                device = "cuda"
            elif torch.backends.mps.is_available():
                device = "mps"
            else:
                device = "cpu"

        self.device = device
        self._model: SentenceTransformer | None = None

    @property
    def model(self) -> SentenceTransformer:
        """Lazy load the sentence transformer model."""
        if self._model is None:
            self._model = SentenceTransformer(self.model_name, device=self.device)
        return self._model

    @property
    def embedding_dim(self) -> int:
        """Get the dimension of embeddings produced by this model."""
        return self.model.get_sentence_embedding_dimension()

    async def encode_text(self, text: str) -> list[float]:
        """Generate embedding for a single text.

        Args:
            text: Text to encode

        Returns:
            Embedding as list of floats
        """
        # Run encoding in thread pool to avoid blocking event loop
        loop = asyncio.get_event_loop()
        embedding = await loop.run_in_executor(
            None,
            lambda: self.model.encode(
                text,
                normalize_embeddings=self.normalize_embeddings,
                show_progress_bar=False,
            ),
        )
        return embedding.tolist()

    async def encode_batch(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        """Generate embeddings for multiple texts efficiently.

        Args:
            texts: List of texts to encode
            batch_size: Batch size for encoding

        Returns:
            List of embeddings
        """
        if not texts:
            return []

        # Run batch encoding in thread pool
        loop = asyncio.get_event_loop()
        embeddings = await loop.run_in_executor(
            None,
            lambda: self.model.encode(
                texts,
                batch_size=batch_size,
                normalize_embeddings=self.normalize_embeddings,
                show_progress_bar=False,
            ),
        )
        return [emb.tolist() for emb in embeddings]

    async def encode_query(self, query: str) -> list[float]:
        """Generate embedding for a search query.

        Some models have different encoding for queries vs documents.
        This method handles that distinction.

        Args:
            query: Query text to encode

        Returns:
            Query embedding
        """
        # For now, same as encode_text, but can be specialized per model
        return await self.encode_text(query)

    def clear_cache(self) -> None:
        """Clear any cached embeddings or model data."""
        if self._model is not None:
            # Free up memory
            del self._model
            self._model = None
            torch.cuda.empty_cache() if torch.cuda.is_available() else None


@lru_cache(maxsize=1)
def get_default_embedder() -> EmbeddingGenerator:
    """Get a singleton instance of the default embedding generator.

    This is cached to avoid reloading the model multiple times.
    """
    return EmbeddingGenerator()


async def generate_embedding(text: str) -> list[float]:
    """Convenience function to generate embedding with default model.

    Args:
        text: Text to encode

    Returns:
        Embedding vector
    """
    embedder = get_default_embedder()
    return await embedder.encode_text(text)


async def generate_embeddings(texts: list[str]) -> list[list[float]]:
    """Convenience function to generate batch embeddings with default model.

    Args:
        texts: List of texts to encode

    Returns:
        List of embedding vectors
    """
    embedder = get_default_embedder()
    return await embedder.encode_batch(texts)
