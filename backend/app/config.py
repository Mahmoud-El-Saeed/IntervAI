from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    GROQ_API_KEY: str
    TAVILY_API_KEY: str
    EMBEDDING_PROVIDER: str 
    EMBEDDING_MODEL: str
    EMBEDDING_DIMENSION: int 
    DATABASE_URI: str
    

def get_settings() -> Settings:
    return Settings()