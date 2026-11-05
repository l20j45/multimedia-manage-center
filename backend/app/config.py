"""Configuración central del backend (lee variables de .env)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    PROJECT_NAME: str = "Biblioteca de Recursos Multimedia API"
    SECRET_KEY: str = "cambia-esta-clave-en-desarrollo"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 horas
    DATABASE_URL: str = "sqlite:///./app.db"

    # SMTP
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAIL_FROM: str = "no-reply@example.com"

    # Orígenes permitidos, separados por comas: http://a,http://b
    # Espera: localhost (web dev), tauri.localhost (escritorio/APK) y tu dominio de producción.
    CORS_ORIGINS: str = "http://localhost:5173,http://tauri.localhost,https://tauri.localhost"

    # Auto-tag con IA (opcional): llave de Gemini para sugerir tags al subir.
    # Sin llave se usa la heurística local (duración/aspecto/nombre).
    GEMINI_API_KEY: str = ""

    # Papelera: recursos borrados se purgan automáticamente tras N días.
    TRASH_RETENTION_DAYS: int = 30

    # ffmpeg/ffprobe explícitos (opcional): útil cuando el PATH del proceso
    # del server no los ve (apps GUI en Windows). En la Pi/Docker，
    # apt/resuelto deja vacío y basta el `which` normal.
    FFMPEG_PATH: str = ""
    FFPROBE_PATH: str = ""

    # Rate limiting por IP en /auth/* (login, registro, recuperación)
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_WINDOW: int = 60  # segundos por ventana
    RATE_LIMIT_LOGIN: int = 10  # intentos por ventana y IP
    RATE_LIMIT_REGISTER: int = 5
    RATE_LIMIT_PASSWORD_RESET: int = 5

    # Biblioteca de medios: carpeta de ficheros y subida máxima (MB)
    MEDIA_DIR: str = "uploads"
    MAX_UPLOAD_MB: int = 1024

    # Duplicados visuales: distancia hamming máx entre dHashes (imágenes)
    # para considerarse "gemelos". Subirlo = más laxo, bajarlo = más estricto.
    PHASH_MAX_BITS: int = 5

    # Compresión de VIDEO al subir (ffmpeg H.264): recodifica con CRF fijado,
    # escala a altura máxima y audio AAC. Borra el original SOLO si el
    # resultado pesa menos. El botón "Comprimir" del detalle reusa lo mismo.
    COMPRESS_ENABLED: bool = True
    COMPRESS_CRF: int = 26
    COMPRESS_MAX_HEIGHT: int = 1080
    COMPRESS_AUDIO_KBPS: int = 128
    # Imágenes: solo se recomprimen si superan este tamaño (KB); JPEG q85,
    # o WebP si traen transparencia (PNG/WebP con alfa).
    COMPRESS_IMG_MIN_KB: int = 200

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()
