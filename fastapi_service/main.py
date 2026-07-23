import os
import json
import logging
import asyncio
import redis
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Database helper
from fastapi_service.database import get_db_connection, execute_single
# Task dispatcher
from fastapi_service.pipeline.tasks import run_movie_pipeline_task
# Consistency router
from fastapi_service.pipeline.consistency_service import router as consistency_router
# YouTube router
from fastapi_service.pipeline.youtube_service import router as youtube_router
# Branching router
from fastapi_service.pipeline.branching_service import router as branching_router
# LoRA router
from fastapi_service.pipeline.lora_service import router as lora_router
# Billing router
from fastapi_service.pipeline.billing_service import router as billing_router
# Provenance router
from fastapi_service.pipeline.provenance_service import router as provenance_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="CineForge AI Generation Pipeline", version="1.0.0")
app.include_router(consistency_router)
app.include_router(youtube_router)
app.include_router(branching_router)
app.include_router(lora_router)
app.include_router(billing_router)
app.include_router(provenance_router)

# Mount Prometheus metrics endpoint
from prometheus_client import make_asgi_app
app.mount("/metrics", make_asgi_app())

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

REDIS_URL = os.environ.get('REDIS_URL', 'redis://redis:6379/0')

class GenerateRequest(BaseModel):
    movie_id: int

@app.get("/health")
def health_check():
    """
    Checks PostgreSQL and Redis connections to ensure microservice health.
    """
    health = {"postgres": "OFFLINE", "redis": "OFFLINE"}
    
    # Check Postgres
    try:
        conn = get_db_connection()
        conn.close()
        health["postgres"] = "OK"
    except Exception as e:
        logger.error(f"Postgres health check failed: {e}")
        
    # Check Redis
    try:
        r = redis.Redis.from_url(REDIS_URL)
        r.ping()
        r.close()
        health["redis"] = "OK"
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        
    if health["postgres"] == "OK" and health["redis"] == "OK":
        return {"status": "healthy", "services": health}
        
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={"status": "unhealthy", "services": health}
    )

@app.post("/api/pipeline/generate", status_code=202)
def trigger_generation_pipeline(data: GenerateRequest):
    """
    Triggers the movie generation pipeline asynchronously by enqueuing a Celery task.
    """
    movie_id = data.movie_id
    logger.info(f"API request received: Triggering pipeline for movie ID {movie_id}")
    
    # Check if movie exists
    movie = execute_single("SELECT id FROM core_movie WHERE id = %s", (movie_id,))
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")
        
    # Enqueue task
    task = run_movie_pipeline_task.delay(movie_id)
    
    return {
        "status": "ACCEPTED",
        "task_id": task.id,
        "movie_id": movie_id,
        "detail": "Pipeline execution enqueued in Celery worker queue"
    }

@app.websocket("/ws/progress/{movie_id}")
async def websocket_progress_stream(websocket: WebSocket, movie_id: int):
    """
    WebSocket endpoint that listens to Redis progress channels and streams
    live update payloads to the React dashboard.
    """
    await websocket.accept()
    logger.info(f"WebSocket connection accepted for movie {movie_id}")
    
    # Establish a connection to Redis (blocking client, but we pull on loop with short timeout)
    r = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    pubsub = r.pubsub()
    pubsub.subscribe(f"movie_progress_{movie_id}")
    
    try:
        while True:
            # We call get_message in a non-blocking fashion
            message = pubsub.get_message(ignore_subscribe_messages=True, timeout=0.1)
            if message:
                data_str = message['data']
                await websocket.send_text(data_str)
            # Yield control back to async loop
            await asyncio.sleep(0.05)
    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected for movie {movie_id}")
    except Exception as e:
        logger.error(f"WebSocket error for movie {movie_id}: {e}")
    finally:
        pubsub.unsubscribe()
        pubsub.close()
        r.close()
