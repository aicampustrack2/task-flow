from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import init_db
from app.tasks import router as tasks_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="task-flow API", lifespan=lifespan)

# 로컬 개발 서버(Vite) 주소만 허용한다.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(tasks_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
