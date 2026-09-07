from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import pipeline

app = FastAPI(title="Article Automation Pipeline", version="0.1.0")

# Loosen/tighten this for your Vite dev server + production frontend origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://article-generation-iota.vercel.app",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(pipeline.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
