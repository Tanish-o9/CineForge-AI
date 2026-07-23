import json
import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

# Database helpers
from fastapi_service.database import execute_query, execute_single

logger = logging.getLogger(__name__)

# 1. Yjs screenplay editor sync delta schema
class YjsSyncUpdate(BaseModel):
    movie_id: int
    scene_number: int
    update_bytes: str = Field(description="Base64 encoded Yjs State Update binary array")
    user_id: int

# 2. WebSocket Teammate Presence Indicator
class ClientPresence(BaseModel):
    user_id: int
    username: str
    active_scene_number: int
    cursor_position: int
    status: str = "VIEWING" # VIEWING, EDITING

# In-memory presence registry (for active Websocket rooms)
active_presences: Dict[int, List[Dict[str, Any]]] = {}

def update_user_presence(movie_id: int, presence: ClientPresence):
    if movie_id not in active_presences:
        active_presences[movie_id] = []
        
    # Remove existing record of user if present
    active_presences[movie_id] = [p for p in active_presences[movie_id] if p["user_id"] != presence.user_id]
    active_presences[movie_id].append(presence.model_dump())
    logger.debug(f"Collab Presence: User {presence.username} is active on Movie #{movie_id} Scene #{presence.active_scene_number}")

def get_movie_active_presences(movie_id: int) -> List[Dict[str, Any]]:
    return active_presences.get(movie_id, [])


# 3. Comment thread Postgres helper functions
class CommentMessage(BaseModel):
    movie_id: int
    scene_number: int
    user_id: int
    username: str
    comment_text: str
    parent_comment_id: Optional[int] = None # For threaded replies

def initialize_comment_tables():
    try:
        execute_query("""
            CREATE TABLE IF NOT EXISTS core_collab_comment (
                id SERIAL PRIMARY KEY,
                movie_id INTEGER NOT NULL,
                scene_number INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                username VARCHAR(100) NOT NULL,
                comment_text TEXT NOT NULL,
                parent_comment_id INTEGER REFERENCES core_collab_comment(id) ON DELETE CASCADE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
    except Exception as e:
        logger.error(f"Failed to initialize comment tables: {e}")

def add_scene_comment(comment: CommentMessage) -> int:
    initialize_comment_tables()
    query = """
        INSERT INTO core_collab_comment (movie_id, scene_number, user_id, username, comment_text, parent_comment_id)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id
    """
    res = execute_single(query, (
        comment.movie_id, comment.scene_number, comment.user_id,
        comment.username, comment.comment_text, comment.parent_comment_id
    ))
    # Parse @mentions
    words = comment.comment_text.split()
    mentions = [w.strip("@").strip(",").strip(".") for w in words if w.startswith("@")]
    for user in mentions:
        logger.info(f"Collab @Notification: Notifying user '{user}' about mention on Movie #{comment.movie_id}")
        
    return res["id"] if res else 1

def get_scene_comments(movie_id: int, scene_number: int) -> List[Dict[str, Any]]:
    initialize_comment_tables()
    query = """
        SELECT id, user_id, username, comment_text, parent_comment_id, created_at
        FROM core_collab_comment
        WHERE movie_id = %s AND scene_number = %s
        ORDER BY created_at ASC
    """
    rows = execute_query(query, (movie_id, scene_number), fetch=True)
    return rows if rows else []


# 4. Role-based Permission Middleware Checker
# Role permissions priority mapping
ROLE_HIERARCHY = {
    "OWNER": 4,
    "EDITOR": 3,
    "COMMENTER": 2,
    "VIEWER": 1
}

def verify_project_permissions(user_id: int, org_id: int, required_role: str = "VIEWER") -> bool:
    """
    Verifies that the user belongs to the active organization and possesses appropriate permissions.
    """
    # Fetch active user membership in Organization
    row = execute_single(
        "SELECT role FROM core_membership WHERE user_id = %s AND org_id = %s",
        (user_id, org_id)
    )
    if not row:
        logger.warning(f"Access Denied: User {user_id} has no memberships in Org {org_id}")
        return False
        
    user_role = row["role"].upper()
    user_priority = ROLE_HIERARCHY.get(user_role, 0)
    required_priority = ROLE_HIERARCHY.get(required_role.upper(), 1)
    
    is_allowed = user_priority >= required_priority
    if not is_allowed:
        logger.warning(f"Access Denied: User {user_id} has role '{user_role}', requires '{required_role}' in Org {org_id}")
    return is_allowed
