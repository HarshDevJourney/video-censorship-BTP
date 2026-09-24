from celery import Celery
from app.core.config import settings
from app.core.database import Base, engine

celery_app = Celery(
    "video_censorship",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_track_started=True,
    imports=("app.workers.tasks",),
)

Base.metadata.create_all(bind=engine)
