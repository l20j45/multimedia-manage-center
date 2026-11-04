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

    # Rate limiting por IP en /auth/* (login, registro, recuperación)
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_WINDOW: int = 60  # segundos por ventana
    RATE_LIMIT_LOGIN: int = 10  # intentos por ventana y IP
    RATE_LIMIT_REGISTER: int = 5
    RATE_LIMIT_PASSWORD_RESET: int = 5

    # Biblioteca de medios: carpeta de ficheros y subida máxima (MB)
    MEDIA_DIR: str = "uploads"
    MAX_UPLOAD_MB: int = 1024

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()
