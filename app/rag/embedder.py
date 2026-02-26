"""
Sentence embedding singleton using SentenceTransformers.
Lazy-loads the model on first use to avoid startup delay.
"""
import numpy as np
from typing import Optional

from app.config import settings


class EmbedderSingleton:
    """
    Singleton wrapper for SentenceTransformers embedding model.
    Model is loaded lazily on first call to encode().
    """

    _instance: Optional["EmbedderSingleton"] = None
    _model = None

    def __new__(cls) -> "EmbedderSingleton":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(settings.EMBEDDING_MODEL)

    def encode(self, texts: list[str]) -> np.ndarray:
        """
        Encode a list of strings into float32 numpy embeddings.
        Shape: (len(texts), embedding_dim)
        """
        self._load()
        embeddings = self._model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
        return embeddings.astype(np.float32)

    def encode_single(self, text: str) -> np.ndarray:
        """
        Encode a single string. Returns shape (1, embedding_dim).
        """
        return self.encode([text])

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    @property
    def embedding_dim(self) -> int:
        self._load()
        return self._model.get_sentence_embedding_dimension()


# Module-level singleton
embedder = EmbedderSingleton()
