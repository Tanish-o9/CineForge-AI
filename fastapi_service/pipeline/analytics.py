import json
import logging
import numpy as np
from typing import Dict, Any, List

# Database helpers
from fastapi_service.database import execute_query, execute_single
from fastapi_service.pipeline.consistency_service import get_clip_embedding

logger = logging.getLogger(__name__)

# 1. Event logging Postgres schema + ingestion function
def initialize_analytics_tables():
    try:
        execute_query("""
            CREATE TABLE IF NOT EXISTS core_analytics_event (
                id SERIAL PRIMARY KEY,
                org_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                event_type VARCHAR(100) NOT NULL,
                meta_data JSONB DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        # We also need a template registry for prompts recommendations
        execute_query("""
            CREATE TABLE IF NOT EXISTS core_prompt_template (
                id SERIAL PRIMARY KEY,
                genre VARCHAR(50) NOT NULL,
                prompt_text TEXT NOT NULL,
                embedding VECTOR(512),
                use_count INTEGER DEFAULT 0
            );
        """)
        
        # Populate starter templates if missing
        row = execute_single("SELECT COUNT(*) as count FROM core_prompt_template")
        if row and row["count"] == 0:
            starters = [
                ("Sci-Fi", "An astronaut exploring a neon-glowing crystal cave on Mars."),
                ("Comedy", "A detective trying to interrogate a sassy talking dog in a diner."),
                ("Drama", "An old pianist playing a final concert in an empty opera house.")
            ]
            for genre, prompt in starters:
                emb = get_clip_embedding(prompt)
                emb_str = "[" + ",".join(map(str, emb)) + "]"
                execute_query(
                    "INSERT INTO core_prompt_template (genre, prompt_text, embedding) VALUES (%s, %s, %s::vector)",
                    (genre, prompt, emb_str)
                )
    except Exception as e:
        logger.error(f"Failed to initialize analytics: {e}")

def log_analytics_event(org_id: int, user_id: int, event_type: str, meta_data: Dict[str, Any] = None):
    """
    Logs user action telemetry event into Postgres database.
    """
    initialize_analytics_tables()
    meta = json.dumps(meta_data) if meta_data else "{}"
    query = """
        INSERT INTO core_analytics_event (org_id, user_id, event_type, meta_data)
        VALUES (%s, %s, %s, %s)
    """
    try:
        execute_query(query, (org_id, user_id, event_type, meta))
        logger.debug(f"Telemetry: Logged action '{event_type}' for User {user_id} in Org {org_id}")
    except Exception as e:
        logger.error(f"Telemetry write failed: {e}")


# 2. Aggregation Dashboard Queries
def query_organization_dashboard_metrics(org_id: int) -> Dict[str, Any]:
    """
    Runs group-by aggregation queries to compile active tenant SaaS metrics.
    """
    initialize_analytics_tables()
    
    # 1. Total movies generated this month
    m_count = execute_single(
        "SELECT COUNT(*) as count FROM core_movie WHERE org_id = %s AND created_at >= DATE_TRUNC('month', CURRENT_DATE)",
        (org_id,)
    )
    movies_count = m_count["count"] if m_count else 0
    
    # 2. Average generation time per stage (from render job durations)
    stages_rows = execute_query(
        "SELECT current_stage, AVG(updated_at - created_at) as avg_duration FROM core_renderjob WHERE status = 'COMPLETED' GROUP BY current_stage",
        fetch=True
    )
    avg_stages = {row["current_stage"]: str(row["avg_duration"]) for row in stages_rows} if stages_rows else {}
    
    # 3. Top genre breakdown
    genre_rows = execute_query(
        "SELECT genre, COUNT(*) as count FROM core_movie WHERE org_id = %s GROUP BY genre ORDER BY count DESC LIMIT 5",
        (org_id,), fetch=True
    )
    top_genres = {row["genre"]: row["count"] for row in genre_rows} if genre_rows else {}
    
    # 4. Job completion rate (COMPLETED vs FAILED vs TIMED_OUT)
    job_status = execute_query(
        "SELECT status, COUNT(*) as count FROM core_renderjob GROUP BY status",
        fetch=True
    )
    completion_rates = {row["status"]: row["count"] for row in job_status} if job_status else {}
    
    return {
        "org_id": org_id,
        "movies_generated_this_month": movies_count,
        "average_stage_durations": avg_stages,
        "top_genres": top_genres,
        "job_completion_rates": completion_rates
    }


# 3. Prompt Recommender using CLIP Embedding Cosine Similarity
def recommend_prompt_templates(user_prompt: str, limit: int = 2) -> List[Dict[str, Any]]:
    """
    Finds prompt templates closest to user input by computing cosine similarity over CLIP vectors.
    """
    initialize_analytics_tables()
    query_emb = get_clip_embedding(user_prompt)
    emb_str = "[" + ",".join(map(str, query_emb)) + "]"
    
    # Cosine distance operator <=> (1 - cosine_similarity).
    # ORDER BY <=> asc finds closest distance (highest similarity)
    query = """
        SELECT id, genre, prompt_text, use_count,
               1 - (embedding <=> %s::vector) AS similarity
        FROM core_prompt_template
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """
    try:
        rows = execute_query(query, (emb_str, emb_str, limit), fetch=True)
        return rows if rows else []
    except Exception as e:
        logger.error(f"Recommender search failed: {e}")
        return []
