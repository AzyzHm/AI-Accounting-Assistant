import os

from dotenv import load_dotenv

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID")
FIREBASE_SERVICE_ACCOUNT_PATH = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH")

FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:4200")
