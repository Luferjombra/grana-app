from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = ""
    supabase_url: str = ""
    supabase_service_key: str = ""

    mindee_api_key: str = ""
    receipt_ocr_provider: str = "mock"

    pluggy_client_id: str = ""
    pluggy_client_secret: str = ""
    bank_aggregator_provider: str = "mock"


settings = Settings()
