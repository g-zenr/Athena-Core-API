from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # API Security
    API_KEY: str  # No default — must be in .env

    # LLM Model (GGUF via llama-cpp-python)
    MODEL_PATH: str = "models/qwen2.5-7b-instruct-q4_k_m-00001-of-00002.gguf"
    MODEL_N_CTX: int = 2048
    MODEL_N_GPU_LAYERS: int = 0
    MODEL_N_THREADS: int = 0       # 0 = auto-detect CPU cores
    MODEL_MAX_TOKENS: int = 512
    MODEL_TEMPERATURE: float = 0.1

    # Embeddings
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"

    # Database
    DATABASE_URL: str = "postgresql://postgres:password@localhost:5432/athena_core"

    # Storage
    DATA_DIR: str = "data"
    UPLOAD_DIR: str = "uploads"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8001

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
