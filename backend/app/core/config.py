from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "video-censorship"

    DATABASE_URL: str = "postgresql://postgres:postgres@postgres:5432/video_censorship"

    REDIS_URL: str = "redis://redis:6379/0"

    MINIO_ENDPOINT: str = "minio:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_SECURE: bool = False
    MINIO_BUCKET: str = "videos"

    CHUNK_SECONDS: int = 10
    FRAME_SAMPLE_RATE: int = 10  # sample every Nth frame

    # How many chunks may be `processing` at once, per video. This is the
    # concurrency cap the scheduler enforces — keep it <= worker concurrency.
    MAX_CONCURRENT_CHUNKS: int = 2

    class Config:
        env_file = ".env"


settings = Settings()
