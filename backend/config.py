from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_name: str = "Repository Intelligence Platform"
    environment: str = "development"

    class Config:
        env_file = ".env"

settings = Settings()
