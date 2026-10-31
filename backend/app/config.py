from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    session_secret: str = "local-only-change-this-secret"
    auth_mode: str = "dev"
    auth0_domain: str = ""
    auth0_client_id: str = ""
    auth0_client_secret: str = ""
    auth0_callback_url: str = "http://localhost:8000/api/auth/callback"
    frontend_url: str = "http://localhost:3000"
    database_url: str = "sqlite:///./commerce.db"
    payment_provider: str = "mock"
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    razorpay_webhook_secret: str = ""
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    livekit_url: str = "ws://localhost:7880"
    livekit_api_key: str = "devkey"
    livekit_api_secret: str = "secret"
    voice_mode: str = "browser"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
