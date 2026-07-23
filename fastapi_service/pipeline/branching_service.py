import os
import json
import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException

# Database helpers
from fastapi_service.database import execute_query, execute_single

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/branching", tags=["Branching Narrative"])

# 1. Extended Story schemas forming a DAG
class SceneChoice(BaseModel):
    choice_text: str = Field(description="Decisional text displayed to the viewer, e.g. 'Enter the dark pod'")
    next_scene_number: int = Field(description="The scene number this branch leads to")

class BranchingSceneBeat(BaseModel):
    scene_number: int = Field(description="Unique scene number")
    location: str = Field(description="Scene location")
    time_of_day: str = Field(description="DAY or NIGHT")
    description: str = Field(description="Action plot description beat")
    emotional_beat: str = Field(description="Emotional tone parameter")
    branches: Optional[List[SceneChoice]] = Field(default=None, description="Narrative branches available at the end of this scene")

class ChoiceSelection(BaseModel):
    next_scene_number: int

# 2. On-demand Branch Generator Trigger in Orchestrator
def generate_branch_on_demand(movie_id: int, target_scene_number: int):
    """
    Dynamically generates script pages, voice assets, storyboard prompts, and animated clips
    for a specific choice scene when a user picks it (on-demand compile).
    """
    logger.info(f"On-Demand Trigger: Requesting narrative branch scene #{target_scene_number} for Movie #{movie_id}")
    
    # Check if scene outline exists in Postgres (inserted during Story Writer phase)
    scene = execute_single(
        "SELECT id, location, time_of_day, description, emotional_beat, screenplay_text FROM core_scene WHERE movie_id = %s AND scene_number = %s",
        (movie_id, target_scene_number)
    )
    if not scene:
        raise ValueError(f"Scene #{target_scene_number} outline not found in database.")
        
    # Cache hit check: if screenplay already generated, skip compiling!
    if scene.get("screenplay_text"):
        logger.info(f"Narrative branch scene #{target_scene_number} is already generated (cached).")
        return
        
    logger.info(f"Narrative cache miss: Compiling branch scene #{target_scene_number} on-demand...")
    
    # Retrieve movie info & characters list
    movie = execute_single("SELECT title, screenplay_raw FROM core_movie WHERE id = %s", (movie_id,))
    if not movie or not movie.get("screenplay_raw"):
        raise ValueError(f"Movie state checkpoint missing.")
    state_dict = json.loads(movie["screenplay_raw"])
    
    # Step A: Generate script screenplay page for just this scene
    from fastapi_service.agents.screenplay_writer import generate_scene_with_retry
    api_key = os.environ.get("OPENAI_API_KEY")
    
    scene_beat = {
        "scene_number": target_scene_number,
        "location": scene["location"],
        "time_of_day": scene["time_of_day"],
        "description": scene["description"],
        "emotional_beat": scene["emotional_beat"]
    }
    
    script = generate_scene_with_retry(
        movie_title=movie["title"],
        characters=state_dict["characters"],
        scene_beat=scene_beat,
        target_word_count=45,
        api_key=api_key
    )
    
    # Save script to database
    dialogues_str = "\n".join([f"{d.character} {d.delivery_note}\n   \"{d.line}\"" for d in script.dialogue])
    actions_str = "\n".join(script.action_lines)
    full_text = f"{script.scene_heading}\n\n{actions_str}\n\n{dialogues_str}"
    
    execute_query(
        "UPDATE core_scene SET screenplay_text = %s, estimated_duration = %s WHERE id = %s",
        (full_text, script.estimated_screen_time_seconds, scene["id"])
    )
    
    # Step B: Generate storyboard prompts and visuals
    from fastapi_service.agents.storyboard_agent import generate_fallback_scene_storyboard
    env_style = f"Desolate rocky location of {scene['location']}"
    storyboard = generate_fallback_scene_storyboard(
        target_scene_number, script.estimated_screen_time_seconds, 
        scene["location"], state_dict["characters"], env_style
    )
    
    for shot in storyboard["shots"]:
        meta = json.dumps(shot)
        img_path = f"storage/movies/{movie_id}/scene_{target_scene_number}_shot_{shot['shot_number']}.png"
        execute_query(
            "INSERT INTO core_asset (movie_id, scene_id, asset_type, file_path, meta_data, created_at) VALUES (%s, %s, 'IMAGE', %s, %s, NOW())",
            (movie_id, scene["id"], img_path, meta)
        )
        
    # Step C: Synthesize vocals
    from fastapi_service.pipeline.voice_gen import process_scene_dialogue_batch, get_tts_provider
    tts = get_tts_provider()
    process_scene_dialogue_batch(
        movie_id, scene["id"], target_scene_number, 
        [d.model_dump() for d in script.dialogue], tts
    )
    
    # Step D: Render animated video clips
    from fastapi_service.pipeline.animation import animate_shot
    for shot in storyboard["shots"]:
        shot_num = shot["shot_number"]
        img_file = f"storage/movies/{movie_id}/scene_{target_scene_number}_shot_{shot_num}.png"
        clip_file = f"storage/movies/{movie_id}/clips/scene_{target_scene_number}_shot_{shot_num}.mp4"
        
        # Build visual image mock if missing on host
        if not os.path.exists(img_file):
            with open(img_file, "wb") as f:
                f.write(b"MOCK REFERENCE IMAGE")
                
        animate_shot(img_file, shot.get("camera_movement", "STATIC"), float(shot.get("duration_seconds", 5.0)))
        
        meta = {"shot_number": shot_num, "duration": shot.get("duration_seconds", 5.0)}
        execute_query(
            "INSERT INTO core_asset (movie_id, scene_id, asset_type, file_path, meta_data, created_at) VALUES (%s, %s, 'VIDEO', %s, %s, NOW())",
            (movie_id, scene["id"], clip_file, json.dumps(meta))
        )
        
    logger.info(f"Narrative branch scene #{target_scene_number} compiled successfully.")

# 3. Choice Selector POST endpoint
@router.post("/movies/{movie_id}/choose", response_model=Dict[str, Any])
def api_choose_narrative_branch(movie_id: int, data: ChoiceSelection):
    """
    Resolves viewer narrative choice and triggers on-demand rendering of the next DAG path.
    """
    try:
        # Trigger on-demand generation
        generate_branch_on_demand(movie_id, data.next_scene_number)
        
        # Fetch output scene clips
        scene_row = execute_single(
            "SELECT id, location FROM core_scene WHERE movie_id = %s AND scene_number = %s",
            (movie_id, data.next_scene_number)
        )
        
        clips = []
        if scene_row:
            rows = execute_query(
                "SELECT file_path FROM core_asset WHERE movie_id = %s AND scene_id = %s AND asset_type = 'VIDEO' ORDER BY id",
                (movie_id, scene_row['id']), fetch=True
            )
            clips = [r["file_path"] for r in rows] if rows else []
            
        # Retrieve branching choices
        movie = execute_single("SELECT screenplay_raw FROM core_movie WHERE id = %s", (movie_id,))
        state_dict = json.loads(movie["screenplay_raw"])
        
        choices = []
        for s in state_dict.get("scenes", []):
            if s.get("scene_number") == data.next_scene_number:
                choices = s.get("branches", [])
                break
                
        return {
            "status": "SUCCESS",
            "scene_number": data.next_scene_number,
            "clips": clips,
            "choices": choices
        }
    except Exception as e:
        logger.error(f"Narrative choice resolution failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate choice branch: {e}")
