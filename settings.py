# settings.py
from pydantic import BaseModel
from typing import List, Dict, Any, Optional


class Settings(BaseModel):
    environment: str = "development"
    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = False
    ssl_certfile: str = ""
    ssl_keyfile: str = ""
    timeout_keep_alive: int = 5

    INDEX_NAME: str = "mauibuildingcode"
    pinecone_top_k: int = 3

    model_name: str = "gpt-4.1-mini"
    max_tokens: int = 500
    temperature: float = 0.7

    use_responses_api: bool = True
    MAX_ATTEMPTS: int = 3
    PINECONE_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    DATABASE_URL: str = ""
