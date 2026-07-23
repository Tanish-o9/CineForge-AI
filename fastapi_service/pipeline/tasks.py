import os
import uuid
import logging
from typing import Dict, Any
from celery.exceptions import SoftTimeLimitExceeded

# Import Celery application
from fastapi_service.pipeline.celery_app import celery_app
# Import Database Helpers
from fastapi_service.database import execute_query, execute_single
# Import Orchestrator
from fastapi_service.agents.orchestrator import orchestrator_graph, MovieState, emit_progress, checkpoint_state

logger = logging.getLogger(__name__)

@celery_app.task(name="fastapi_service.pipeline.tasks.run_movie_pipeline_task", bind=True)
def run_movie_pipeline_task(self, movie_id: int) -> Dict[str, Any]:
    """
    Asynchronous Celery task that coordinates the entire movie generation pipeline.
    """
    logger.info(f"Starting pipeline task for Movie ID: {movie_id}")
    
    # 1. Fetch movie parameters from database
    movie_row = execute_single(
        "SELECT title, user_prompt, target_duration_seconds, status FROM core_movie WHERE id = %s",
        (movie_id,)
    )
    if not movie_row:
        err_msg = f"Movie ID {movie_id} not found in database."
        logger.error(err_msg)
        return {"status": "FAILED", "error": err_msg}
        
    # 2. Check or create a RenderJob record in DB
    job_row = execute_single(
        "SELECT job_id, status, state_data FROM core_renderjob WHERE movie_id = %s ORDER BY created_at DESC LIMIT 1",
        (movie_id,)
    )
    
    job_uuid_str = str(uuid.uuid4())
    state_data = {}
    
    if job_row:
        # Resume if crashed, or overwrite
        job_uuid_str = str(job_row['job_id'])
        if job_row['status'] == 'PROCESSING' and job_row['state_data']:
            state_data = job_row['state_data']
            logger.info(f"Resuming existing render job: {job_uuid_str}")
        else:
            # Overwrite status to processing
            execute_query(
                "UPDATE core_renderjob SET status = 'PROCESSING', progress = 0, current_stage = 'story', error_message = NULL, updated_at = NOW() WHERE job_id = %s",
                (job_uuid_str,)
            )
            logger.info(f"Re-starting render job: {job_uuid_str}")
    else:
        # Insert a new render job
        insert_query = """
            INSERT INTO core_renderjob (movie_id, job_id, status, current_stage, progress, state_data, created_at, updated_at)
            VALUES (%s, %s, 'PROCESSING', 'story', 0, '{}', NOW(), NOW())
        """
        execute_query(insert_query, (movie_id, job_uuid_str))
        logger.info(f"Created new render job: {job_uuid_str}")

    # Update Movie status to processing
    execute_query("UPDATE core_movie SET status = 'PROCESSING' WHERE id = %s", (movie_id,))
    
    # 3. Construct initial MovieState
    initial_state = MovieState(
        movie_id=movie_id,
        job_id=job_uuid_str,
        user_prompt=movie_row['user_prompt'],
        title=movie_row['title'],
        target_duration_seconds=movie_row['target_duration_seconds'],
        current_stage="story",
        status="PROCESSING"
    )
    
    # If resuming, load existing checkpoint values
    if state_data:
        try:
            # Merge checkpoint fields
            checkpoint = json.loads(state_data) if isinstance(state_data, str) else state_data
            for key, val in checkpoint.items():
                if val:
                    setattr(initial_state, key, val)
        except Exception as e:
            logger.error(f"Error loading checkpoint state: {e}")

    try:
        emit_progress(movie_id, "story", 0, "RUNNING", "Movie pipeline initiated.")
        
        # 4. Invoke LangGraph Orchestrator
        final_state = orchestrator_graph.invoke(initial_state.model_dump())
        
        logger.info(f"LangGraph execution completed for Movie ID: {movie_id}")
        return {"status": "SUCCESS", "movie_id": movie_id, "job_id": job_uuid_str}
        
    except SoftTimeLimitExceeded as ste:
        err_msg = "Task aborted: Soft time limit exceeded."
        logger.error(err_msg)
        execute_query("UPDATE core_movie SET status = 'FAILED' WHERE id = %s", (movie_id,))
        execute_query("UPDATE core_renderjob SET status = 'FAILED', error_message = %s WHERE job_id = %s", (err_msg, job_uuid_str))
        emit_progress(movie_id, "export", 100, "FAILED", err_msg)
        return {"status": "FAILED", "error": err_msg}
        
    except Exception as e:
        err_msg = f"Fatal pipeline error: {str(e)}"
        logger.error(err_msg, exc_info=True)
        execute_query("UPDATE core_movie SET status = 'FAILED' WHERE id = %s", (movie_id,))
        execute_query("UPDATE core_renderjob SET status = 'FAILED', error_message = %s WHERE job_id = %s", (err_msg, job_uuid_str))
        emit_progress(movie_id, "export", 100, "FAILED", err_msg)
        return {"status": "FAILED", "error": err_msg}
