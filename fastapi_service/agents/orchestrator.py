import os
import json
import logging
import redis
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, END

# Import database helpers
from fastapi_service.database import execute_query, execute_single

logger = logging.getLogger(__name__)

# Redis Connection for Live Progress Pub/Sub
REDIS_URL = os.environ.get('REDIS_URL', 'redis://redis:6379/0')
redis_client = redis.Redis.from_url(REDIS_URL)

def emit_progress(movie_id: int, stage: str, progress: int, status: str, message: str = ""):
    """
    Publishes progress update to Redis pub/sub.
    """
    try:
        event = {
            "movie_id": movie_id,
            "stage": stage,
            "progress": progress,
            "status": status,
            "message": message
        }
        channel = f"movie_progress_{movie_id}"
        redis_client.publish(channel, json.dumps(event))
        logger.info(f"Published progress: {event}")
    except Exception as e:
        logger.error(f"Failed to publish progress to Redis: {e}")

def checkpoint_state(movie_id: int, job_id: str, stage: str, progress: int, state_dict: Dict[str, Any], status: str = 'PROCESSING'):
    """
    Persists current pipeline state to core_renderjob and core_movie PostgreSQL tables.
    """
    try:
        query = """
            UPDATE core_renderjob
            SET current_stage = %s, progress = %s, state_data = %s, status = %s, updated_at = NOW()
            WHERE job_id = %s
        """
        # Serialize state dict
        state_json = json.dumps(state_dict, default=str)
        execute_query(query, (stage, progress, state_json, status, job_id))

        # Also update the movie table status and screenplay_raw (used as state checkpoint)
        movie_query = "UPDATE core_movie SET status = %s, screenplay_raw = %s WHERE id = %s"
        execute_query(movie_query, (status, state_json, movie_id))
    except Exception as e:
        logger.error(f"Failed to checkpoint state to PostgreSQL: {e}")

# Pydantic MovieState Definition
class MovieState(BaseModel):
    movie_id: int
    job_id: str
    user_prompt: str
    title: str = ""
    genre: str = ""
    tone: str = ""
    target_duration_seconds: int = 60
    story_summary: str = ""
    screenplay_raw: str = ""
    scenes: List[Dict[str, Any]] = []
    characters: List[Dict[str, Any]] = []
    environments: List[Dict[str, Any]] = []
    audio_assets: List[Dict[str, Any]] = []
    video_clips: List[Dict[str, Any]] = []
    subtitles: str = ""
    final_video_path: str = ""
    current_stage: str = ""
    status: str = "PROCESSING"
    errors: List[str] = []
    retry_counts: Dict[str, int] = {}
    features_disabled: List[str] = []

# Agent / Executor Imports
from fastapi_service.agents.story_writer import run_story_writer
from fastapi_service.agents.screenplay_writer import run_screenplay_writer
from fastapi_service.agents.storyboard_agent import run_storyboard_agent
from fastapi_service.pipeline.voice_gen import run_voice_generator
from fastapi_service.pipeline.music_gen import run_music_generator
from fastapi_service.pipeline.sfx_gen import run_sfx_generator
from fastapi_service.pipeline.animation import run_animation_agent
from fastapi_service.pipeline.video_editor import run_video_editor
from fastapi_service.pipeline.subtitle_gen import run_subtitle_agent

# Unified asset consistency generator calling the consistency service
def run_asset_consistency(state: MovieState) -> Dict[str, Any]:
    """
    Resolves consistency references for both character rosters and scene locations.
    """
    logger.info("Running unified asset consistency node")
    from fastapi_service.pipeline.consistency_service import get_or_create_asset
    
    updated_characters = []
    for char in state.characters:
        name = char.get("name", "Unknown")
        desc = char.get("physical_description", char.get("personality", "Unknown description"))
        # Query / generate turnaround ref sheet
        res = get_or_create_asset("character", name, desc)
        char["reference_sheet_path"] = res["reference_image_url"]
        updated_characters.append(char)
        
    updated_environments = []
    locations = list({s.get("location", "Location") for s in state.scenes})
    for loc in locations:
        res = get_or_create_asset("environment", loc, f"High resolution establishing wide landscape shot of {loc}")
        updated_environments.append({
            "name": loc,
            "reference_image_path": res["reference_image_url"]
        })
        
    return {
        "characters": updated_characters,
        "environments": updated_environments
    }

# Node Wrappers helper
# Node Wrappers helper
def run_stage_with_retry(state: Dict[str, Any], stage_name: str, runner_func, progress_val: int) -> Dict[str, Any]:
    from fastapi_service.pipeline.resumable_service import RedisDistributedLock, is_stage_already_completed, mark_stage_completed, move_to_dead_letter_queue
    
    state_obj = MovieState(**state)
    state_obj.current_stage = stage_name
    
    # 1. Idempotency Check
    if is_stage_already_completed(state_obj.movie_id, stage_name):
        logger.info(f"Idempotency Hit: Stage '{stage_name}' already completed for Movie #{state_obj.movie_id}. Skipping run.")
        emit_progress(state_obj.movie_id, stage_name, progress_val, "COMPLETED", f"Finished {stage_name} (idempotent skip)")
        return state_obj.model_dump()
        
    if stage_name in state_obj.features_disabled:
        logger.info(f"Stage {stage_name} is disabled. Skipping.")
        emit_progress(state_obj.movie_id, stage_name, progress_val, "SKIPPED", f"Skipping {stage_name} (disabled)")
        return state_obj.model_dump()

    # 2. Redis Distributed Locking
    lock = RedisDistributedLock(redis_client, state_obj.movie_id)
    if not lock.acquire():
        logger.warning(f"Redis Lock Conflict: Movie #{state_obj.movie_id} is locked by another worker. Failing fast.")
        state_obj.status = "FAILED"
        state_obj.errors.append("Concurrency conflict: another worker is running this movie generation.")
        emit_progress(state_obj.movie_id, stage_name, progress_val, "FAILED", "Concurrency lock error")
        return state_obj.model_dump()

    emit_progress(state_obj.movie_id, stage_name, progress_val, "RUNNING", f"Starting {stage_name}...")
    
    if stage_name not in state_obj.retry_counts:
        state_obj.retry_counts[stage_name] = 0

    import time
    from fastapi_service.pipeline.metrics import STAGE_DURATION, STAGE_STATUS
    start_time = time.time()

    try:
        # Run worker function
        updated_fields = runner_func(state_obj)
        for k, v in updated_fields.items():
            setattr(state_obj, k, v)
        
        # Checkpoint successful state
        checkpoint_state(state_obj.movie_id, state_obj.job_id, stage_name, progress_val, state_obj.model_dump())
        mark_stage_completed(state_obj.movie_id, stage_name)
        
        # Record successful metrics
        duration = time.time() - start_time
        STAGE_STATUS.labels(stage_name=stage_name, status="success").inc()
        STAGE_DURATION.labels(stage_name=stage_name).observe(duration)
        
        emit_progress(state_obj.movie_id, stage_name, progress_val, "COMPLETED", f"Finished {stage_name}")
    except Exception as e:
        state_obj.retry_counts[stage_name] += 1
        err_msg = f"Error in {stage_name}: {str(e)}"
        logger.error(err_msg, exc_info=True)
        state_obj.errors.append(err_msg)
        
        duration = time.time() - start_time
        STAGE_DURATION.labels(stage_name=stage_name).observe(duration)
        
        # Append error log/context to user prompt for LLM self-correction retry
        state_obj.user_prompt = f"{state_obj.user_prompt}\n\n[RETRY FEEDBACK from stage {stage_name}]: Your previous attempt failed with error: {str(e)}. Please correct it."
        
        if state_obj.retry_counts[stage_name] >= 2:
            # Record failure metrics
            STAGE_STATUS.labels(stage_name=stage_name, status="failure").inc()
            
            # 3. Dead-Letter Queue (DLQ) Transfer
            move_to_dead_letter_queue(state_obj.movie_id, state_obj.job_id, stage_name, err_msg)
            
            state_obj.status = "FAILED"
            state_obj.current_stage = "FAILED"
            checkpoint_state(state_obj.movie_id, state_obj.job_id, stage_name, progress_val, state_obj.model_dump(), status="FAILED")
            emit_progress(state_obj.movie_id, stage_name, progress_val, "FAILED", err_msg)
            return state_obj.model_dump()
        else:
            # Record retry metrics
            STAGE_STATUS.labels(stage_name=stage_name, status="retry").inc()
            
            emit_progress(state_obj.movie_id, stage_name, progress_val, "RETRYING", f"Retrying {stage_name} (Attempt {state_obj.retry_counts[stage_name]})")
            checkpoint_state(state_obj.movie_id, state_obj.job_id, stage_name, progress_val, state_obj.model_dump())
            
            # Recursive retry call (release lock first to allow retry worker context to acquire it if restarted)
            lock.release()
            return run_stage_with_retry(state_obj.model_dump(), stage_name, runner_func, progress_val)
    finally:
        # Guarantee lock release
        lock.release()

    return state_obj.model_dump()

# Nodes Definitions
def story_node(state: Dict[str, Any]) -> Dict[str, Any]:
    return run_stage_with_retry(state, "story", run_story_writer, 10)

def screenplay_node(state: Dict[str, Any]) -> Dict[str, Any]:
    return run_stage_with_retry(state, "screenplay", run_screenplay_writer, 15)

def storyboard_node(state: Dict[str, Any]) -> Dict[str, Any]:
    return run_stage_with_retry(state, "storyboard", run_storyboard_agent, 20)

def asset_consistency_node(state: Dict[str, Any]) -> Dict[str, Any]:
    return run_stage_with_retry(state, "asset_consistency", run_asset_consistency, 40)

def voice_gen_node(state: Dict[str, Any]) -> Dict[str, Any]:
    return run_stage_with_retry(state, "voice_gen", run_voice_generator, 60)

def music_gen_node(state: Dict[str, Any]) -> Dict[str, Any]:
    return run_stage_with_retry(state, "music_gen", run_music_generator, 70)

def sfx_gen_node(state: Dict[str, Any]) -> Dict[str, Any]:
    return run_stage_with_retry(state, "sfx_gen", run_sfx_generator, 80)

def animation_node(state: Dict[str, Any]) -> Dict[str, Any]:
    return run_stage_with_retry(state, "animation", run_animation_agent, 85)

def video_edit_node(state: Dict[str, Any]) -> Dict[str, Any]:
    return run_stage_with_retry(state, "video_edit", run_video_editor, 90)

def subtitle_gen_node(state: Dict[str, Any]) -> Dict[str, Any]:
    return run_stage_with_retry(state, "subtitle_gen", run_subtitle_agent, 95)

def export_node(state: Dict[str, Any]) -> Dict[str, Any]:
    state_obj = MovieState(**state)
    state_obj.current_stage = "export"
    emit_progress(state_obj.movie_id, "export", 100, "COMPLETED", "Movie generated successfully!")
    
    # Save final video path to Movie table
    query = "UPDATE core_movie SET final_video_path = %s, status = 'COMPLETED' WHERE id = %s"
    execute_query(query, (state_obj.final_video_path, state_obj.movie_id))
    
    # Update RenderJob
    checkpoint_state(state_obj.movie_id, state_obj.job_id, "export", 100, state_obj.model_dump(), status="COMPLETED")
    
    state_obj.status = "COMPLETED"
    return state_obj.model_dump()

# Resume/Resume Checkpoint helper
def resume_movie_checkpoint(movie_id: int) -> Optional[Dict[str, Any]]:
    """
    Loads saved state data from Postgres to resume rendering.
    """
    row = execute_single("SELECT screenplay_raw FROM core_movie WHERE id = %s", (movie_id,))
    if row and row['screenplay_raw']:
        try:
            return json.loads(row['screenplay_raw'])
        except Exception as e:
            logger.error(f"Failed to decode screenplay_raw checkpoint: {e}")
    return None

# Router Edge Decision
def check_job_status(state: Dict[str, Any]) -> str:
    if state.get("status") == "FAILED":
        return END
    return "next"

# Critic Nodes
from fastapi_service.agents.critic_agent import run_stage_critic, route_stage_critic_decision

def story_critic_node(state: Dict[str, Any]) -> Dict[str, Any]:
    return run_stage_critic(state, "story")

def route_story_critic(state: Dict[str, Any]) -> str:
    return route_stage_critic_decision(state, next_node="screenplay", self_node="story")

def screenplay_critic_node(state: Dict[str, Any]) -> Dict[str, Any]:
    return run_stage_critic(state, "screenplay")

def route_screenplay_critic(state: Dict[str, Any]) -> str:
    return route_stage_critic_decision(state, next_node="storyboard", self_node="screenplay")

def storyboard_critic_node(state: Dict[str, Any]) -> Dict[str, Any]:
    return run_stage_critic(state, "storyboard")

def route_storyboard_critic(state: Dict[str, Any]) -> str:
    return route_stage_critic_decision(state, next_node="asset_consistency", self_node="storyboard")

def asset_consistency_critic_node(state: Dict[str, Any]) -> Dict[str, Any]:
    return run_stage_critic(state, "asset_consistency")

def route_asset_consistency_critic(state: Dict[str, Any]) -> str:
    return route_stage_critic_decision(state, next_node="voice_gen", self_node="asset_consistency")

def video_edit_critic_node(state: Dict[str, Any]) -> Dict[str, Any]:
    return run_stage_critic(state, "video_edit")

def route_video_edit_critic(state: Dict[str, Any]) -> str:
    return route_stage_critic_decision(state, next_node="subtitle_gen", self_node="video_edit")

# Graph Construction
workflow = StateGraph(dict)

workflow.add_node("story", story_node)
workflow.add_node("story_critic", story_critic_node)
workflow.add_node("screenplay", screenplay_node)
workflow.add_node("screenplay_critic", screenplay_critic_node)
workflow.add_node("storyboard", storyboard_node)
workflow.add_node("storyboard_critic", storyboard_critic_node)
workflow.add_node("asset_consistency", asset_consistency_node)
workflow.add_node("asset_consistency_critic", asset_consistency_critic_node)
workflow.add_node("voice_gen", voice_gen_node)
workflow.add_node("music_gen", music_gen_node)
workflow.add_node("sfx_gen", sfx_gen_node)
workflow.add_node("animation", animation_node)
workflow.add_node("video_edit", video_edit_node)
workflow.add_node("video_edit_critic", video_edit_critic_node)
workflow.add_node("subtitle_gen", subtitle_gen_node)
workflow.add_node("export", export_node)

workflow.set_entry_point("story")

# Connect nodes with critic checks and self-correction loops
workflow.add_conditional_edges("story", check_job_status, {"next": "story_critic", END: END})
workflow.add_conditional_edges("story_critic", route_story_critic, {"story": "story", "screenplay": "screenplay"})

workflow.add_conditional_edges("screenplay", check_job_status, {"next": "screenplay_critic", END: END})
workflow.add_conditional_edges("screenplay_critic", route_screenplay_critic, {"screenplay": "screenplay", "storyboard": "storyboard"})

workflow.add_conditional_edges("storyboard", check_job_status, {"next": "storyboard_critic", END: END})
workflow.add_conditional_edges("storyboard_critic", route_storyboard_critic, {"storyboard": "storyboard", "asset_consistency": "asset_consistency"})

workflow.add_conditional_edges("asset_consistency", check_job_status, {"next": "asset_consistency_critic", END: END})
workflow.add_conditional_edges("asset_consistency_critic", route_asset_consistency_critic, {"asset_consistency": "asset_consistency", "voice_gen": "voice_gen"})

workflow.add_conditional_edges("voice_gen", check_job_status, {"next": "music_gen", END: END})
workflow.add_conditional_edges("music_gen", check_job_status, {"next": "sfx_gen", END: END})
workflow.add_conditional_edges("sfx_gen", check_job_status, {"next": "animation", END: END})
workflow.add_conditional_edges("animation", check_job_status, {"next": "video_edit", END: END})

workflow.add_conditional_edges("video_edit", check_job_status, {"next": "video_edit_critic", END: END})
workflow.add_conditional_edges("video_edit_critic", route_video_edit_critic, {"video_edit": "video_edit", "subtitle_gen": "subtitle_gen"})

workflow.add_conditional_edges("subtitle_gen", check_job_status, {"next": "export", END: END})
workflow.add_edge("export", END)

orchestrator_graph = workflow.compile()
