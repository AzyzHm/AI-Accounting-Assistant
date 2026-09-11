from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.api_keys import FRONTEND_ORIGIN
from config.firebase import init_firebase
from config.llm_providers import warm_up_embedding_model
from routes import admin, auth, chats

app = FastAPI(title="Accounting Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

init_firebase()
warm_up_embedding_model()
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(chats.router)


@app.get("/")
def home():
    """Simple Backend Status route"""
    return {"status": "online"}
