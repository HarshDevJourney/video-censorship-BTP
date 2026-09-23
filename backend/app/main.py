from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.database import Base, engine
from app.api import videos, jobs, streaming

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Video Censorship API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(videos.router)
app.include_router(jobs.router)
app.include_router(streaming.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
