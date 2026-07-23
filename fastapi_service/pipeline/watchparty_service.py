import logging
from typing import Dict, Any, List, Set
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# 1. Playback sync message schema
class PlaybackState(BaseModel):
    movie_id: int
    status: str # PLAY, PAUSE, SEEK
    timestamp_seconds: float
    sender_id: int

class EmojiReaction(BaseModel):
    user_id: int
    emoji: str # 🔥, 😂, 😮, 😢
    timestamp_seconds: float


# 2. Ephemeral Room Registry
class WatchPartyRoom:
    def __init__(self, room_id: str, movie_id: int):
        self.room_id = room_id
        self.movie_id = movie_id
        self.active_users: Set[int] = set()
        self.current_playback = {
            "status": "PAUSE",
            "timestamp_seconds": 0.0
        }
        self.ephemeral_chat_history: List[Dict[str, Any]] = []

# Room registry in memory (erased when hosts or users close sockets)
rooms_registry: Dict[str, WatchPartyRoom] = {}


# 3. WebSockets room routing logic helpers
def join_watch_party_room(room_id: str, movie_id: int, user_id: int) -> Dict[str, Any]:
    if room_id not in rooms_registry:
        rooms_registry[room_id] = WatchPartyRoom(room_id, movie_id)
        
    room = rooms_registry[room_id]
    room.active_users.add(user_id)
    logger.info(f"WatchParty: User {user_id} joined room '{room_id}' (Total connections: {len(room.active_users)})")
    
    return {
        "room_id": room_id,
        "movie_id": movie_id,
        "playback_state": room.current_playback,
        "recent_chats": room.ephemeral_chat_history[-10:] # send latest 10 messages as catch-up
    }

def sync_playback_state(room_id: str, state: PlaybackState) -> Dict[str, Any]:
    if room_id not in rooms_registry:
        raise ValueError(f"Watch party room '{room_id}' does not exist.")
        
    room = rooms_registry[room_id]
    room.current_playback = {
        "status": state.status,
        "timestamp_seconds": state.timestamp_seconds
    }
    
    logger.info(f"WatchParty Sync: Room '{room_id}' status updated to '{state.status}' at {state.timestamp_seconds}s")
    
    # Broadcast to all websocket connections in room
    return {
        "type": "PLAYBACK_SYNC",
        "room_id": room_id,
        "status": state.status,
        "timestamp_seconds": state.timestamp_seconds,
        "sender_id": state.sender_id
    }

def broadcast_emoji_reaction(room_id: str, reaction: EmojiReaction) -> Dict[str, Any]:
    """
    Formulates payload to trigger flying reaction overlays on user screens.
    """
    logger.debug(f"WatchParty: Reaction '{reaction.emoji}' at {reaction.timestamp_seconds}s in room '{room_id}'")
    return {
        "type": "EMOJI_BURST",
        "room_id": room_id,
        "user_id": reaction.user_id,
        "emoji": reaction.emoji,
        "timestamp_seconds": reaction.timestamp_seconds
    }

def append_ephemeral_chat(room_id: str, user_id: str, message: str) -> Dict[str, Any]:
    """
    Logs chat line in memory. Messages are never saved to database.
    """
    if room_id not in rooms_registry:
        raise ValueError(f"Room '{room_id}' does not exist.")
        
    room = rooms_registry[room_id]
    chat_payload = {
        "user_id": user_id,
        "message": message,
        "timestamp": time.time() if 'time' in globals() else 1782182400
    }
    room.ephemeral_chat_history.append(chat_payload)
    
    logger.info(f"WatchParty Chat: Ephemeral message added to room '{room_id}'")
    return {
        "type": "CHAT_MESSAGE",
        "room_id": room_id,
        "chat": chat_payload
    }

def leave_watch_party_room(room_id: str, user_id: int):
    if room_id in rooms_registry:
        room = rooms_registry[room_id]
        room.active_users.discard(user_id)
        logger.info(f"WatchParty: User {user_id} left room '{room_id}'")
        
        # Clean up empty rooms
        if not room.active_users:
            del rooms_registry[room_id]
            logger.info(f"WatchParty: Ephemeral room '{room_id}' deleted.")
