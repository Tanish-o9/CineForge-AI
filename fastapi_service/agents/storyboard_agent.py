import os
import json
import logging
from typing import List, Dict, Any
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)

# Pydantic schemas for the Storyboard Agent
class StoryboardShot(BaseModel):
    shot_number: int = Field(description="Incremental shot number within the scene, starting at 1")
    shot_type: str = Field(description="WIDE, MEDIUM, CLOSE-UP, or POV")
    camera_movement: str = Field(description="STATIC, ZOOM-IN, ZOOM-OUT, PAN-LEFT, or PAN-RIGHT")
    lighting_description: str = Field(description="Cinematic description of the lighting setup")
    character_positions: Dict[str, str] = Field(description="Map of character names present in frame to their position, e.g. {'Alex': 'center-left', 'EVA': 'right-background'}")
    facial_expression: Dict[str, str] = Field(description="Map of character names in frame to their facial expression, e.g. {'Alex': 'terrified', 'EVA': 'neutral'}")
    mood: str = Field(description="Visual mood of the shot (e.g. suspenseful, claustrophobic)")
    color_palette: str = Field(description="Dominant colors, e.g. 'dusty orange, deep space black'")
    duration_seconds: int = Field(description="Duration in seconds for this shot")
    action_focus: str = Field(description="The primary action focus in this shot")

class SceneStoryboard(BaseModel):
    scene_number: int = Field(description="The scene number this storyboard represents")
    shots: List[StoryboardShot] = Field(description="Sequential shot list for the scene")

# Prompt-Builder function for SDXL / Flux
def build_image_prompt(shot: StoryboardShot, characters: List[Dict[str, Any]], environment_style: str) -> Dict[str, str]:
    """
    Concatenates character descriptions, environment style, camera settings, lighting,
    and mood into a final visual prompt with negative default keywords.
    """
    present_char_descs = []
    for name, pos in shot.character_positions.items():
        # Look up character physical description
        char_desc = ""
        for c in characters:
            if c['name'].strip().lower() == name.strip().lower():
                char_desc = c.get('physical_description', '').strip()
                break
                
        expression = shot.facial_expression.get(name, "neutral")
        if char_desc:
            present_char_descs.append(
                f"{name} ({char_desc}) situated at {pos} in the frame with a {expression} expression"
            )
        else:
            present_char_descs.append(
                f"{name} situated at {pos} in the frame with a {expression} expression"
            )
            
    chars_part = ""
    if present_char_descs:
        chars_part = "Featuring " + ", and ".join(present_char_descs) + ". "

    positive_prompt = (
        f"Cinematic {shot.shot_type.upper()} shot. Camera movement: {shot.camera_movement.upper()}. "
        f"Setting/Environment: {environment_style}. {chars_part}"
        f"Action: {shot.action_focus}. "
        f"Lighting is {shot.lighting_description}. Mood: {shot.mood}. "
        f"Color Palette: {shot.color_palette}. "
        f"Style: raw film scan, 35mm cinematography, high contrast, anamorphic lens flares, photo-realism."
    )

    negative_prompt = (
        "text, watermark, logo, branding, signature, letters, subtitles, extra limbs, "
        "deformed body parts, poorly drawn faces, disfigured, double heads, illustration, "
        "render, cartoon, drawing, painting, amateur photography"
    )

    return {
        "prompt": positive_prompt,
        "negative_prompt": negative_prompt
    }

# LangGraph Orchestration Node Entrypoint
def run_storyboard_agent(state: Any) -> Dict[str, Any]:
    """
    Executes the Storyboard Agent.
    Slices each scene screenplay text into granular shots.
    """
    movie_id = state.movie_id
    scenes = state.scenes
    characters = state.characters
    api_key = os.environ.get("OPENAI_API_KEY")

    processed_scenes = []

    for sc in scenes:
        scene_number = sc.get('scene_number')
        env_name = sc.get('location', 'Location')
        duration = sc.get('estimated_screen_time_seconds', sc.get('estimated_duration', 20))
        script_text = sc.get('screenplay_text', '')

        # Environment style lookup (simulating environment service check)
        env_style = f"Barren rocky surface of {env_name}, desolate atmospheric haze."

        if api_key:
            try:
                logger.info(f"Running Storyboard LLM for scene {scene_number}")
                llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.5, openai_api_key=api_key)
                structured_llm = llm.with_structured_output(SceneStoryboard)
                
                system_prompt = (
                    "You are an expert storyboard artist. Settle scene screenplays into storyboard shots.\n\n"
                    "DIRECTIVES:\n"
                    f"1. Shot Durations: The total duration of all shots in the scene MUST sum precisely to {duration} seconds.\n"
                    "2. Character Positioning: Describe character placement in frame via dictionary mapping name to position.\n"
                    "3. Expressions: Describe character facial expressions via dictionary mapping name to mood."
                )

                prompt_template = ChatPromptTemplate.from_messages([
                    ("system", system_prompt),
                    ("user", "Screenplay Scene:\n{script_text}\n\nCharacters: {characters}")
                ])

                chain = prompt_template | structured_llm
                scene_storyboard = chain.invoke({
                    "script_text": script_text,
                    "characters": json.dumps(characters)
                })

                shots_list = []
                for shot in scene_storyboard.shots:
                    prompts_dict = build_image_prompt(shot, characters, env_style)
                    shot_dict = shot.model_dump()
                    shot_dict['final_sdxl_prompt'] = prompts_dict['prompt']
                    shot_dict['negative_prompt'] = prompts_dict['negative_prompt']
                    shots_list.append(shot_dict)

                processed_scenes.append({
                    "scene_number": scene_number,
                    "shots": shots_list
                })
                continue
            except Exception as e:
                logger.error(f"Storyboard LLM failed for scene {scene_number}: {e}. Splicing fallback.")

        # Fallback generator
        fallback_scene = generate_fallback_scene_storyboard(scene_number, duration, env_name, characters, env_style)
        processed_scenes.append(fallback_scene)

    # Save to database
    save_storyboard_to_db(movie_id, processed_scenes)

    return {"scenes": processed_scenes}

def save_storyboard_to_db(movie_id: int, processed_scenes: List[Dict[str, Any]]):
    """
    Saves storyboard images meta data to Asset database.
    """
    from fastapi_service.database import execute_query, execute_single
    
    execute_query("DELETE FROM core_asset WHERE movie_id = %s AND asset_type = 'IMAGE'", (movie_id,))
    
    for sc in processed_scenes:
        scene_number = sc['scene_number']
        scene_row = execute_single("SELECT id FROM core_scene WHERE movie_id = %s AND scene_number = %s", (movie_id, scene_number))
        if not scene_row:
            continue
        scene_id = scene_row['id']
        
        for shot in sc['shots']:
            file_path = f"storage/movies/{movie_id}/scene_{scene_number}_shot_{shot['shot_number']}.png"
            meta_data = json.dumps(shot)
            
            insert_query = """
                INSERT INTO core_asset (movie_id, scene_id, asset_type, file_path, meta_data, created_at)
                VALUES (%s, %s, 'IMAGE', %s, %s, NOW())
            """
            execute_query(insert_query, (movie_id, scene_id, file_path, meta_data))

def generate_fallback_scene_storyboard(
    scene_number: int,
    duration: int,
    env_name: str,
    characters: List[Dict[str, Any]],
    env_style: str
) -> Dict[str, Any]:
    """
    Constructs a fallback storyboard shot sequence for a scene.
    """
    char_names = [c['name'] for c in characters]
    p1 = char_names[0] if len(char_names) > 0 else "Alex"
    p2 = char_names[1] if len(char_names) > 1 else "EVA"

    dur_1 = duration // 2
    dur_2 = duration - dur_1

    # Shot 1: Establishing WIDE
    shot_1 = StoryboardShot(
        shot_number=1,
        shot_type="WIDE",
        camera_movement="PAN-LEFT",
        lighting_description="dim atmospheric light with orange storm clouds filtering sun rays",
        character_positions={p1: "center-left"},
        facial_expression={p1: "focused"},
        mood="tense",
        color_palette="rust red and dust orange",
        duration_seconds=dur_1,
        action_focus="Alex walks through the dust storm looking at HUD panels"
    )

    # Shot 2: Medium Focus
    shot_2 = StoryboardShot(
        shot_number=2,
        shot_type="MEDIUM",
        camera_movement="ZOOM-IN",
        lighting_description="glowing blue terminal status bars reflecting on helmet visor",
        character_positions={p1: "center", p2: "right-background"},
        facial_expression={p1: "terrified", p2: "neutral"},
        mood="claustrophobic",
        color_palette="dark grey, glowing cyan, rust reflections",
        duration_seconds=dur_2,
        action_focus="Alex secures the power link under wind pressure"
    )

    shots_list = []
    for shot in [shot_1, shot_2]:
        prompts = build_image_prompt(shot, characters, env_style)
        s_dict = shot.model_dump()
        s_dict['final_sdxl_prompt'] = prompts['prompt']
        s_dict['negative_prompt'] = prompts['negative_prompt']
        shots_list.append(s_dict)

    return {
        "scene_number": scene_number,
        "shots": shots_list
    }
