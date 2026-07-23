import os
from celery import Celery

REDIS_URL = os.environ.get('REDIS_URL', 'redis://redis:6379/0')

celery_app = Celery(
    'cineforge_tasks',
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=['fastapi_service.pipeline.tasks']
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=1800,  # 30 minutes max per job
)
