import logging
from typing import Dict, Any, List

# Database helpers
from fastapi_service.database import execute_query, execute_single

logger = logging.getLogger(__name__)

# 1. Gallery DB Schemas
def initialize_gallery_tables():
    try:
        execute_query("""
            CREATE TABLE IF NOT EXISTS core_gallery_movie (
                id SERIAL PRIMARY KEY,
                movie_id INTEGER NOT NULL REFERENCES core_movie(id) ON DELETE CASCADE,
                is_public BOOLEAN DEFAULT TRUE,
                likes_count INTEGER DEFAULT 0,
                views_count INTEGER DEFAULT 0,
                remixed_from_id INTEGER REFERENCES core_movie(id) ON DELETE SET NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        execute_query("""
            CREATE TABLE IF NOT EXISTS core_gallery_comment (
                id SERIAL PRIMARY KEY,
                gallery_movie_id INTEGER REFERENCES core_gallery_movie(id) ON DELETE CASCADE,
                user_id INTEGER NOT NULL,
                comment_text TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
    except Exception as e:
        logger.error(f"Failed to initialize gallery tables: {e}")


# 2. Text-Only Clone Function
def clone_movie_text_layer(original_movie_id: int, new_owner_id: int) -> int:
    """
    Clones screenplay and story outline of an existing movie to start a remix.
    Excludes visual, voice, music or video files to prevent consistency drifts.
    Sets attribution to original_movie_id.
    """
    initialize_gallery_tables()
    
    # Query original text data
    movie = execute_single(
        "SELECT title, user_prompt, genre, tone, target_duration_seconds, story_summary, screenplay_raw "
        "FROM core_movie WHERE id = %s",
        (original_movie_id,)
    )
    if not movie:
        raise ValueError(f"Movie ID {original_movie_id} does not exist.")
        
    remix_title = f"Remix of {movie['title']}"
    
    # Insert new cloned movie row
    insert_movie = """
        INSERT INTO core_movie (user_id, title, user_prompt, genre, tone, target_duration_seconds, story_summary, screenplay_raw, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'PENDING')
        RETURNING id
    """
    new_movie = execute_single(insert_movie, (
        new_owner_id, remix_title, movie["user_prompt"], movie["genre"],
        movie["tone"], movie["target_duration_seconds"], movie["story_summary"], movie["screenplay_raw"]
    ))
    new_movie_id = new_movie["id"]
    
    # Clone scenes text rows
    scenes = execute_query(
        "SELECT scene_number, location, time_of_day, description, emotional_beat, screenplay_text, estimated_duration, order_index "
        "FROM core_scene WHERE movie_id = %s",
        (original_movie_id,), fetch=True
    )
    
    if scenes:
        for s in scenes:
            insert_scene = """
                INSERT INTO core_scene (movie_id, scene_number, location, time_of_day, description, emotional_beat, screenplay_text, estimated_duration, order_index)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            execute_query(insert_scene, (
                new_movie_id, s["scene_number"], s["location"], s["time_of_day"],
                s["description"], s["emotional_beat"], s["screenplay_text"], s["estimated_duration"], s["order_index"]
            ))
            
    # Register in gallery under remix link (Attribution lock!)
    execute_query("""
        INSERT INTO core_gallery_movie (movie_id, remixed_from_id)
        VALUES (%s, %s)
    """, (new_movie_id, original_movie_id))
    
    logger.info(f"Remix Gallery: Cloned text layer of Movie {original_movie_id} -> New Movie {new_movie_id} (Attribution locked)")
    return new_movie_id


# 3. Attribution Enforcement Query helpers
def get_movie_remix_attribution_details(movie_id: int) -> Dict[str, Any]:
    """
    Returns original title and creator of parent movie if active project is a remix.
    """
    initialize_gallery_tables()
    query = """
        SELECT g.remixed_from_id, m.title as parent_title, u.username as parent_creator
        FROM core_gallery_movie g
        JOIN core_movie m ON g.remixed_from_id = m.id
        LEFT JOIN auth_user u ON m.user_id = u.id
        WHERE g.movie_id = %s
    """
    row = execute_single(query, (movie_id,))
    if row and row["remixed_from_id"]:
        return {
            "is_remix": True,
            "remixed_from_id": row["remixed_from_id"],
            "parent_title": row["parent_title"],
            "parent_creator": row["parent_creator"] or "System Creator",
            "attribution_label": f"Remixed from '{row['parent_title']}' by {row['parent_creator'] or 'System Creator'}"
        }
    return {"is_remix": False}
