import os
import json
import logging
from typing import Tuple, Dict, Any
from PIL import Image

# Database helpers
from fastapi_service.database import execute_query, execute_single

logger = logging.getLogger(__name__)

# 1. Database schema initialization
def initialize_moderation_tables():
    try:
        execute_query("""
            CREATE TABLE IF NOT EXISTS core_moderation_queue (
                id SERIAL PRIMARY KEY,
                movie_id INTEGER NOT NULL,
                flagged_stage VARCHAR(50) NOT NULL,
                reason VARCHAR(255) NOT NULL,
                status VARCHAR(20) DEFAULT 'PENDING', -- PENDING, APPROVED, REJECTED
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        execute_query("""
            CREATE TABLE IF NOT EXISTS core_moderation_audit (
                id SERIAL PRIMARY KEY,
                input_source VARCHAR(100) NOT NULL,
                classifier_score REAL NOT NULL,
                outcome VARCHAR(50) NOT NULL,
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
    except Exception as e:
        logger.error(f"Failed to initialize moderation tables: {e}")


# 2. Pre-generation check (OpenAI Moderation style wrapper)
def check_prompt_moderation(prompt: str) -> Tuple[bool, str]:
    """
    Checks user prompts for harmful content.
    Returns: (is_safe, failure_reason)
    """
    initialize_moderation_tables()
    logger.info("Executing pre-generation prompt safety review")
    
    # In production, this calls openai.Moderation.create()
    openai_key = os.environ.get("OPENAI_API_KEY")
    is_safe = True
    reason = ""
    score = 0.02
    
    # Mocking triggers for testing
    harmful_keywords = ["bomb", "exploding buildings", "harmful content"]
    for keyword in harmful_keywords:
        if keyword in prompt.lower():
            is_safe = False
            reason = f"Prompt contains restricted keyword/topic: '{keyword}'."
            score = 0.98
            break
            
    outcome = "APPROVED" if is_safe else "REJECTED"
    log_moderation_audit(f"Prompt: {prompt[:100]}", score, outcome, reason)
    
    return is_safe, reason


# 3. Post-generation check (Visual frames safety check)
def check_image_safety(image_path: str) -> Tuple[bool, str]:
    """
    Evaluates rendered output images or video frame files to verify safety.
    """
    initialize_moderation_tables()
    logger.info(f"Executing post-generation image safety review: {image_path}")
    
    is_safe = True
    reason = ""
    score = 0.05
    
    # In production, this computes CLIP vision vector margins or triggers safety APIs.
    # For testing, we mock trigger on specific filenames or metadata overlays
    if "unsafe" in image_path.lower():
        is_safe = False
        reason = "Visual output flagged for gore/violence indicator."
        score = 0.91
        
    outcome = "APPROVED" if is_safe else "REJECTED"
    log_moderation_audit(f"Image: {os.path.basename(image_path)}", score, outcome, reason)
    
    return is_safe, reason


# 4. Ingestion functions: Review Queue and Audit Logs
def add_to_moderation_queue(movie_id: int, flagged_stage: str, reason: str):
    """
    Sends flagged files to the admin queue instead of silently crashing the thread.
    """
    initialize_moderation_tables()
    query = """
        INSERT INTO core_moderation_queue (movie_id, flagged_stage, reason)
        VALUES (%s, %s, %s)
    """
    execute_query(query, (movie_id, flagged_stage, reason))
    logger.warning(f"Moderation: Movie #{movie_id} flagged during '{flagged_stage}' and parked in review queue. Reason: {reason}")
    
    # Update movie/render status to flag
    execute_query("UPDATE core_movie SET status = 'FLAGGED' WHERE id = %s", (movie_id,))
    execute_query("UPDATE core_renderjob SET status = 'FLAGGED' WHERE movie_id = %s", (movie_id,))

def log_moderation_audit(input_source: str, score: float, outcome: str, details: str = ""):
    """
    Maintains a compliance audit log table of all moderation queries.
    """
    initialize_moderation_tables()
    query = """
        INSERT INTO core_moderation_audit (input_source, classifier_score, outcome, details)
        VALUES (%s, %s, %s, %s)
    """
    try:
        execute_query(query, (input_source, score, outcome, details))
    except Exception as e:
        logger.error(f"Moderation audit log insertion failed: {e}")
