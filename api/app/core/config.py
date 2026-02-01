import os


def env(key: str, default: str) -> str:
  value = os.getenv(key)
  return value if value else default


DATABASE_URL = env("DATABASE_URL", "postgresql+psycopg2://storyfill:storyfill@postgres:5432/storyfill")
REDIS_URL = env("REDIS_URL", "redis://redis:6379/0")
OTEL_SERVICE_NAME = env("OTEL_SERVICE_NAME", "storyfill-api")
WEB_ORIGINS = [origin.strip() for origin in env("WEB_ORIGINS", "http://localhost:3000").split(",") if origin.strip()]
WEB_BASE_URL = env("WEB_BASE_URL", WEB_ORIGINS[0] if WEB_ORIGINS else "http://localhost:3000")
WS_BASE_URL = env("WS_BASE_URL", "ws://localhost:8000/v1/ws")
MINIO_ENDPOINT = env("MINIO_ENDPOINT", "http://minio:9000")
MINIO_ROOT_USER = env("MINIO_ROOT_USER", "minio")
MINIO_ROOT_PASSWORD = env("MINIO_ROOT_PASSWORD", "minio123")
MINIO_BUCKET = env("MINIO_BUCKET", "storyfill-audio")
MINIO_REGION = env("MINIO_REGION", "us-east-1")
TTS_SERVICE_URL = env("TTS_SERVICE_URL", "http://tts:7000")
TTS_DEFAULT_MODEL = env("TTS_DEFAULT_MODEL", "openai/tts-1")
TTS_DEFAULT_VOICE = env("TTS_DEFAULT_VOICE", "alloy")
TTS_RESPONSE_FORMAT = env("TTS_RESPONSE_FORMAT", "mp3")
