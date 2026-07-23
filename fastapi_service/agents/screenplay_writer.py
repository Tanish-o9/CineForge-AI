import os
import json
import logging
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)

# Custom exception for validation failures
class ScreenplayValidationError(ValueError):
    pass

# Dialogue and Scene Schemas
class CustomDialogueLine(BaseModel):
    character: str = Field(description="Name of the character speaking (MUST exist in character roster)")
    line: str = Field(description="The spoken dialogue line text")
    delivery_note: str = Field(description="Delivery note, e.g. (whispering), (panicked), (angrily)")

class SceneScreenplay(BaseModel):
    scene_number: int = Field(description="Sequential scene number matching the story beat")
    scene_heading: str = Field(description="Heading format, e.g., INT. COCKPIT - DAY or EXT. MARS SURFACE - NIGHT")
    action_lines: List[str] = Field(description="Actions and visual descriptions in the scene")
    dialogue: List[CustomDialogueLine] = Field(description="List of dialogue lines in this scene")
    estimated_screen_time_seconds: int = Field(description="Estimated duration for this scene in seconds")

# Validator 1: Character Verification
def validate_scene_characters(scene_screenplay: SceneScreenplay, valid_characters: List[str]):
    """
    Validates that every speaking character in dialogue exists in the approved character list.
    """
    valid_set = {c.strip().upper() for c in valid_characters}
    for dial in scene_screenplay.dialogue:
        char_name = dial.character.strip().upper()
        if char_name not in valid_set:
            raise ScreenplayValidationError(
                f"Character '{dial.character}' in scene {scene_screenplay.scene_number} dialogue is not in the approved character roster: {valid_characters}."
            )

# Validator 2: Word Count Verification
def validate_screenplay_word_count(scenes_screenplay: List[SceneScreenplay], target_duration_seconds: int) -> tuple[bool, str]:
    """
    Enforces total spoken word count across all scenes maps to target_duration_seconds
    at ~130 words/minute (+-10% tolerance).
    """
    total_words = 0
    for sc in scenes_screenplay:
        for dial in sc.dialogue:
            total_words += len(dial.line.split())
            
    # Calculate target words
    target_words = int((target_duration_seconds / 60.0) * 130)
    tolerance = int(target_words * 0.10)
    min_words = target_words - tolerance
    max_words = target_words + tolerance
    
    logger.info(f"Word Count Validation: Total words = {total_words}, Target = {target_words} ({min_words} - {max_words})")
    
    if total_words < min_words:
        diff = min_words - total_words
        return False, f"UNDER_FLOW: Total spoken dialogue has {total_words} words, which is under the minimum required {min_words} words. Please expand dialogue by roughly {diff} words."
    elif total_words > max_words:
        diff = total_words - max_words
        return False, f"OVER_FLOW: Total spoken dialogue has {total_words} words, which exceeds the maximum allowed {max_words} words. Please trim dialogue by roughly {diff} words."
        
    return True, "Word count is within acceptable range."

# Scene generation chain call
def generate_single_scene_screenplay_raw(
    movie_title: str,
    characters: List[Dict[str, Any]],
    scene_beat: Dict[str, Any],
    target_word_count: int,
    api_key: str,
    feedback: str = ""
) -> SceneScreenplay:
    """
    Invokes LLM for a single scene screenplay.
    """
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7, openai_api_key=api_key)
    structured_llm = llm.with_structured_output(SceneScreenplay)
    
    system_prompt = (
        "You are an expert Hollywood scriptwriter. Convert the provided story beat into a detailed scene screenplay.\n\n"
        "DIRECTIVES:\n"
        f"1. Spoken Word Count: Try to keep the total dialogue words for this scene close to {target_word_count} words.\n"
        f"2. Characters: You can ONLY use these character names in dialogue: {', '.join([c['name'] for c in characters])}.\n"
        "3. Format: Return a valid scene heading, a list of action lines, dialogues with delivery notes, and estimated screen time."
    )
    
    user_content = (
        f"Movie Title: {movie_title}\n"
        f"Character Profiles: {json.dumps(characters)}\n"
        f"Target Scene Duration: {scene_beat.get('estimated_duration', 20)} seconds\n"
        f"Scene Beat: {json.dumps(scene_beat)}\n"
    )
    if feedback:
        user_content += f"\nFEEDBACK TO CORRECT: {feedback}\n"
        
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", user_content)
    ])
    
    chain = prompt_template | structured_llm
    return chain.invoke({})

# Scene-level retry wrapper
def generate_scene_with_retry(
    movie_title: str,
    characters: List[Dict[str, Any]],
    scene_beat: Dict[str, Any],
    target_word_count: int,
    api_key: str,
    feedback: str = ""
) -> SceneScreenplay:
    """
    Attempts generation and retries once if character roster validation fails.
    """
    valid_chars = [c['name'] for c in characters]
    
    try:
        logger.info(f"Generating Scene {scene_beat.get('scene_number')}: Attempt 1")
        scene_output = generate_single_scene_screenplay_raw(movie_title, characters, scene_beat, target_word_count, api_key, feedback)
        validate_scene_characters(scene_output, valid_chars)
        return scene_output
    except ScreenplayValidationError as sve:
        logger.warning(f"Character validation failed on first attempt: {sve}. Auto-retrying...")
        
        retry_feedback = (
            f"{feedback}\n"
            f"ERROR: Your previous generation failed validation with error: {str(sve)}. "
            f"You MUST only use characters from: {valid_chars} in dialogue fields."
        )
        # Attempt 2 (Retry)
        scene_output = generate_single_scene_screenplay_raw(movie_title, characters, scene_beat, target_word_count, api_key, retry_feedback)
        validate_scene_characters(scene_output, valid_chars)
        return scene_output

# Per-scene regeneration function (diff-friendly)
def regenerate_scene(
    movie_title: str,
    characters: List[Dict[str, Any]],
    scene_beat: Dict[str, Any],
    target_word_count: int,
    api_key: str,
    feedback: str
) -> SceneScreenplay:
    """
    Regenerates a single scene independently with specific feedback instruction
    (e.g., 'trim dialogue' or 'add a beat').
    """
    logger.info(f"Regenerating Scene {scene_beat.get('scene_number')} with instruction: {feedback}")
    return generate_scene_with_retry(movie_title, characters, scene_beat, target_word_count, api_key, feedback)

# LangGraph entrypoint views/handlers
def run_screenplay_writer(state: Any) -> Dict[str, Any]:
    """
    Runs the Screenplay Agent. Combines scene-by-scene generation, character checks,
    and runs the global word count alignment routine.
    """
    movie_id = state.movie_id
    movie_title = state.title
    characters = state.characters
    scenes = state.scenes
    target_duration = state.target_duration_seconds
    api_key = os.environ.get("OPENAI_API_KEY")

    if not api_key:
        logger.info("Running Fallback Screenplay Writer")
        from fastapi_service.agents.screenplay_writer_fallback import generate_fallback_screenplay
        fallback = generate_fallback_screenplay(movie_title, characters, scenes, target_duration)
        save_screenplay_to_db(movie_id, fallback)
        return {
            "screenplay_raw": json.dumps(fallback.model_dump(), default=str),
            "scenes": [s.model_dump() for s in fallback.scenes]
        }

    # Generate scene-by-scene
    scene_count = len(scenes)
    total_target_words = int((target_duration / 60.0) * 130)
    word_share_per_scene = total_target_words // max(1, scene_count)
    
    generated_scenes: List[SceneScreenplay] = []
    
    for sc in scenes:
        scene_output = generate_scene_with_retry(
            movie_title=movie_title,
            characters=characters,
            scene_beat=sc,
            target_word_count=word_share_per_scene,
            api_key=api_key
        )
        generated_scenes.append(scene_output)
        
    # Global Word Count validation check
    is_valid, msg = validate_screenplay_word_count(generated_scenes, target_duration)
    
    # If over/under, perform one round of single-scene correction
    if not is_valid:
        logger.warning(f"Global word count check failed: {msg}. Correcting...")
        
        # Choose a scene to correct:
        # For trim (OVER_FLOW), choose the scene with the most words.
        # For expansion (UNDER_FLOW), choose the scene with the fewest words.
        word_counts = []
        for s in generated_scenes:
            wc = sum(len(d.line.split()) for d in s.dialogue)
            word_counts.append(wc)
            
        if "OVER_FLOW" in msg:
            target_idx = word_counts.index(max(word_counts))
            target_scene = generated_scenes[target_idx]
            scene_beat = next(s for s in scenes if s['scene_number'] == target_scene.scene_number)
            
            # Regenerate with trim prompt
            corrected = regenerate_scene(
                movie_title, characters, scene_beat, 
                max(5, word_counts[target_idx] - 25), api_key, 
                "TRIM DIALOGUE: Please trim or condense dialogue. Make it shorter."
            )
            generated_scenes[target_idx] = corrected
        else:
            target_idx = word_counts.index(min(word_counts))
            target_scene = generated_scenes[target_idx]
            scene_beat = next(s for s in scenes if s['scene_number'] == target_scene.scene_number)
            
            # Regenerate with expand prompt
            corrected = regenerate_scene(
                movie_title, characters, scene_beat, 
                word_counts[target_idx] + 25, api_key, 
                "EXPAND DIALOGUE: Please add dialogue lines or beats to expand length."
            )
            generated_scenes[target_idx] = corrected

    # Final wrap-up
    screenplay_output = ScreenplayOutputSchema(scenes=generated_scenes)
    save_screenplay_to_db(movie_id, screenplay_output)
    
    return {
        "screenplay_raw": json.dumps(screenplay_output.model_dump(), default=str),
        "scenes": [s.model_dump() for s in screenplay_output.scenes]
    }

class ScreenplayOutputSchema(BaseModel):
    scenes: List[SceneScreenplay]

def save_screenplay_to_db(movie_id: int, screenplay: ScreenplayOutputSchema):
    """
    Saves screenplay details to Django backend tables.
    """
    from fastapi_service.database import execute_query
    
    raw_json = json.dumps(screenplay.model_dump(), default=str)
    execute_query("UPDATE core_movie SET screenplay_raw = %s WHERE id = %s", (raw_json, movie_id))
    
    for scene in screenplay.scenes:
        dialogues_str = "\n".join([f"{d.character} {d.delivery_note}\n   \"{d.line}\"" for d in scene.dialogue])
        actions_str = "\n".join(scene.action_lines)
        full_text = f"{scene.scene_heading}\n\n{actions_str}\n\n{dialogues_str}"
        
        execute_query(
            "UPDATE core_scene SET screenplay_text = %s, estimated_duration = %s WHERE movie_id = %s AND scene_number = %s",
            (full_text, scene.estimated_screen_time_seconds, movie_id, scene.scene_number)
        )
