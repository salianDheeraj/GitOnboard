from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_name: str = "Repository Intelligence Platform"
    environment: str = "development"
    deployment_type: str = "LOCAL"

    # Database
    local_database_url: str = "postgresql+psycopg://myuser:mypassword@localhost:5432/repository_intelligence"
    prod_database_url: str = ""

    # GitHub OAuth
    github_client_id: str = ""
    github_client_secret: str = ""

    # JWT Config
    jwt_secret: str = "change_me_in_production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440

    # Frontend URL (for redirects)
    local_frontend_url: str = "http://localhost:3000"
    prod_frontend_url: str = ""

    class Config:
        env_file = ".env"
        extra = "ignore"

    @property
    def database_url(self) -> str:
        return self.local_database_url if self.deployment_type == "LOCAL" else self.prod_database_url

    @property
    def frontend_url(self) -> str:
        return self.local_frontend_url if self.deployment_type == "LOCAL" else self.prod_frontend_url

settings = Settings()
