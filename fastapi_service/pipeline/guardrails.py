import os
import time
import logging
import concurrent.futures
from typing import Dict, Any, Tuple

# Database helpers
from fastapi_service.database import execute_query, execute_single

logger = logging.getLogger(__name__)

# 1. Redis Quota Functions (Key changes per day for auto daily reset)
def get_quota_key(user_id: int) -> str:
    date_str = time.strftime("%Y-%m-%d")
    return f"user_quota:{user_id}:{date_str}"

def check_and_decrement_quota(redis_client, user_id: int, max_daily: int = 5) -> bool:
    """
    Checks if a user has remaining generation slots today, decrementing if available.
    """
    key = get_quota_key(user_id)
    try:
        val = redis_client.get(key)
        if val is None:
            # Set initial daily quota with 24 hours expiry
            redis_client.set(key, max_daily - 1, ex=86400)
            logger.info(f"Quota: Daily quota initialized for User {user_id}. Slots remaining: {max_daily - 1}")
            return True
            
        current = int(val)
        if current <= 0:
            logger.warning(f"Quota Exceeded: User {user_id} has exhausted their daily movie slot quota.")
            return False
            
        redis_client.decr(key)
        logger.info(f"Quota: Decremented quota for User {user_id}. Slots remaining: {current - 1}")
        return True
    except Exception as e:
        logger.error(f"Quota verification failed: {e}")
        # Gracefully proceed if Redis connectivity is down
        return True

def refund_quota(redis_client, user_id: int):
    """
    Refunds a quota slot to a user in case of pipeline failures or timeouts.
    """
    key = get_quota_key(user_id)
    try:
        if redis_client.exists(key):
            redis_client.incr(key)
            logger.info(f"Quota: Refunded one quota slot to User {user_id}")
    except Exception as e:
        logger.error(f"Failed to refund user quota: {e}")

# 2. Pre-flight Cost Estimator
def estimate_movie_generation_cost(
    target_duration_seconds: int,
    num_characters: int,
    max_budget_dollars: float = 0.50
) -> Tuple[bool, float, str]:
    """
    Calculates estimated compute/API cost before launching job, rejecting if budget is exceeded.
    """
    # Clamp target duration to a max of 10 minutes (600s) for demo constraints
    clamped_duration = min(target_duration_seconds, 600)
    
    # Calculate estimations:
    # 25 seconds average per scene
    est_scenes = clamped_duration // 25
    if est_scenes == 0:
        est_scenes = 1
        
    # 4 shots average per scene
    est_shots = est_scenes * 4
    
    # Image gen counts: shots + turnaround sheet per character + establishing environment
    est_images = est_shots + num_characters + 1
    
    # TTS calls: 6 dialogue lines average per scene
    est_tts = est_scenes * 6
    
    # LLM calls: story, screenplay, storyboard, foley, youtube meta
    est_llm = 5
    
    # Price weights in dollars:
    # Replicate SDXL/Flux: $0.03 per image
    # OpenAI/ElevenLabs TTS: $0.004 per voice line
    # GPT-4o-mini: $0.01 per structured call
    cost_images = est_images * 0.03
    cost_tts = est_tts * 0.004
    cost_llm = est_llm * 0.01
    
    total_estimated_cost = cost_images + cost_tts + cost_llm
    
    msg = (
        f"Estimated cost: ${total_estimated_cost:.3f} (Scenes: {est_scenes}, Shots: {est_shots}, "
        f"Images: {est_images}, Voice lines: {est_tts}, LLM calls: {est_llm})"
    )
    
    if total_estimated_cost > max_budget_dollars:
        return False, total_estimated_cost, f"Cost Exceeded! {msg} exceeds budget cap of ${max_budget_dollars:.2f}."
        
    return True, total_estimated_cost, msg

# 3. Per-job Timeout Wrapper
def run_movie_pipeline_with_timeout(
    movie_id: int,
    state_dict: Dict[str, Any],
    redis_client,
    timeout_seconds: float = 1200
) -> Dict[str, Any]:
    """
    Executes the LangGraph orchestrator inside a ThreadPoolExecutor.
    If timeout is reached, kills the execution, marks status as timed_out,
    and refunds the user's daily quota slot.
    """
    from fastapi_service.agents.orchestrator import orchestrator_graph
    
    # Pre-flight cost estimation checks
    target_dur = state_dict.get("target_duration_seconds", 60)
    chars_count = len(state_dict.get("characters", []))
    is_ok, est_cost, cost_msg = estimate_movie_generation_cost(target_dur, chars_count)
    if not is_ok:
        raise ValueError(cost_msg)
        
    logger.info(f"Pre-flight Cost Assessment: {cost_msg}")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(orchestrator_graph.invoke, state_dict)
        try:
            result = future.result(timeout=timeout_seconds)
            return result
        except concurrent.futures.TimeoutError:
            logger.error(f"Hard Timeout Triggered! Movie #{movie_id} exceeded pipeline limit of {timeout_seconds}s.")
            
            # Quota refunding
            try:
                owner = execute_single("SELECT user_id FROM core_movie WHERE id = %s", (movie_id,))
                user_id = owner["user_id"] if owner else 1
                refund_quota(redis_client, user_id)
            except Exception as re:
                logger.error(f"DLQ refund failed: {re}")
                
            # Update Postgres status
            execute_query("UPDATE core_movie SET status = 'TIMED_OUT' WHERE id = %s", (movie_id,))
            execute_query("UPDATE core_renderjob SET status = 'TIMED_OUT' WHERE movie_id = %s", (movie_id,))
            
            raise TimeoutError(f"CineForge pipeline exceeded maximum timeout limit of {timeout_seconds} seconds.")
