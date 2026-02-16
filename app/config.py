import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o")

REQUEST_TIMEOUT: int = 30
MAX_CONTENT_LENGTH: int = 200_000
USER_AGENT: str = (
    "Mozilla/5.0 (compatible; EEATGrader/1.0; +https://github.com/eeat-grader)"
)
