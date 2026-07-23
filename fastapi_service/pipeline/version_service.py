import json
import logging
from typing import List, Dict, Any

# Database helpers
from fastapi_service.database import execute_query, execute_single

logger = logging.getLogger(__name__)

# 1. Database table initialization
def initialize_versioning_tables():
    try:
        execute_query("""
            CREATE TABLE IF NOT EXISTS core_project_version (
                id SERIAL PRIMARY KEY,
                movie_id INTEGER NOT NULL REFERENCES core_movie(id) ON DELETE CASCADE,
                stage_name VARCHAR(50) NOT NULL,
                version_number INTEGER NOT NULL,
                state_data JSONB NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
    except Exception as e:
        logger.error(f"Failed to initialize versioning tables: {e}")


# 2. Ingestion logger
def record_project_version(movie_id: int, stage_name: str, state_data: Dict[str, Any]):
    """
    Saves current state checkpoint as a version row. Auto-increments version number.
    """
    initialize_versioning_tables()
    
    # Get highest active version number
    highest = execute_single(
        "SELECT MAX(version_number) as max_v FROM core_project_version WHERE movie_id = %s AND stage_name = %s",
        (movie_id, stage_name)
    )
    next_v = (highest["max_v"] + 1) if highest and highest["max_v"] is not None else 1
    
    query = """
        INSERT INTO core_project_version (movie_id, stage_name, version_number, state_data)
        VALUES (%s, %s, %s, %s)
    """
    execute_query(query, (movie_id, stage_name, next_v, json.dumps(state_data)))
    logger.info(f"Versioning: Recorded snapshot version {next_v} for stage '{stage_name}' (Movie #{movie_id})")


# 3. Variant Branch Generator
def generate_variant_branches(
    movie_id: int,
    base_prompt: str,
    variant_instructions: List[str] # ["sad ending", "epic action battle ending", "comedy twist"]
) -> List[int]:
    """
    Forks the parent movie into 2-3 alternate story branches, returning the created project IDs.
    """
    initialize_versioning_tables()
    
    # Query parent movie details
    parent = execute_single(
        "SELECT user_id, title, genre, tone, target_duration_seconds FROM core_movie WHERE id = %s",
        (movie_id,)
    )
    if not parent:
        raise ValueError(f"Parent Movie ID {movie_id} does not exist.")
        
    created_branch_ids = []
    
    for i, inst in enumerate(variant_instructions):
        branch_title = f"{parent['title']} (Variant: {inst})"
        branch_prompt = f"{base_prompt} [Variant modification: {inst}]"
        
        insert_query = """
            INSERT INTO core_movie (user_id, title, user_prompt, genre, tone, target_duration_seconds, status)
            VALUES (%s, %s, %s, %s, %s, %s, 'PENDING')
            RETURNING id
        """
        res = execute_single(insert_query, (
            parent["user_id"], branch_title, branch_prompt, parent["genre"],
            parent["tone"], parent["target_duration_seconds"]
        ))
        branch_id = res["id"]
        created_branch_ids.append(branch_id)
        
        # Link in version logs as variants
        record_project_version(branch_id, "story", {"base_movie_id": movie_id, "variant_instruction": inst})
        logger.info(f"Versioning: Spawned branch {branch_id} for variant '{inst}'")
        
    return created_branch_ids


# 4. Selective Rollback logic recomputing downstream stages
PIPELINE_STAGES_ORDER = [
    "story", "screenplay", "storyboard", "character_gen",
    "environment_gen", "voice_gen", "music_gen", "sfx_gen",
    "animation", "video_edit", "subtitle_gen", "export"
]

def execute_selective_rollback(movie_id: int, target_version_id: int) -> Dict[str, Any]:
    """
    Restores the project to a previous stage checkpoint.
    Deletes (invalidates) subsequent stages in the history ledger, ensuring
    only the affected downstream stages regenerate (leaving pre-rollback stages cached).
    """
    initialize_versioning_tables()
    
    # Fetch target version metadata
    ver = execute_single(
        "SELECT stage_name, state_data FROM core_project_version WHERE id = %s AND movie_id = %s",
        (target_version_id, movie_id)
    )
    if not ver:
        raise ValueError(f"Version ID {target_version_id} not found for Movie {movie_id}.")
        
    rolled_stage = ver["stage_name"]
    state_data = json.loads(ver["state_data"])
    
    # Locate index in pipeline flow
    idx = PIPELINE_STAGES_ORDER.index(rolled_stage)
    downstream_stages = PIPELINE_STAGES_ORDER[idx + 1:]
    
    # Invalidate stage history completions in DB to force regenerations of downstream steps
    if downstream_stages:
        placeholders = ",".join(["%s"] * len(downstream_stages))
        query_invalidate = f"""
            DELETE FROM core_stage_history
            WHERE movie_id = %s AND stage_name IN ({placeholders})
        """
        params = (movie_id,) + tuple(downstream_stages)
        execute_query(query_invalidate, params)
        logger.info(f"Rollback: Invalidated downstream completed stages: {downstream_stages}")
        
    # Invalidate status in render jobs
    execute_query(
        "UPDATE core_renderjob SET status = 'PROCESSING', current_stage = %s WHERE movie_id = %s",
        (rolled_stage, movie_id)
    )
    
    return {
        "status": "ROLLBACK_COMPLETE",
        "movie_id": movie_id,
        "restored_stage": rolled_stage,
        "invalidated_downstream_stages": downstream_stages,
        "restored_state": state_data
    }
