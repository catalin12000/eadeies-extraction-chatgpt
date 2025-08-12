from core_.base.datatypes import OpenAIConfig
import os

OPENAI_CONFIG = OpenAIConfig(
    API_KEY=os.getenv("API_KEY", ""),
)
