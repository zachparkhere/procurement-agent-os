from pydantic_settings import BaseSettings

class MCPSettings(BaseSettings):
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True
    CORS_ORIGINS: list = ["*"]
    
    class Config:
        env_file = ".env"

settings = MCPSettings() 