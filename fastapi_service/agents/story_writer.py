import os
import json
import logging
from typing import List, Dict, Any
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)

# Output Schema
class CharacterProfile(BaseModel):
    name: str = Field(description="Name of the character")
    age: str = Field(description="Age of the character")
    role: str = Field(description="Role in the story (e.g. Protagonist, Antagonist, Supporting)")
    personality: str = Field(description="Personality traits and quirks")
    physical_description: str = Field(description="Detailed appearance notes for image generation consistency")

class SceneBeat(BaseModel):
    scene_number: int = Field(description="Sequential scene number starting at 1")
    location: str = Field(description="Broad location name (e.g. Mars Surface, Cockpit, Mission Control)")
    time_of_day: str = Field(description="DAY or NIGHT")
    description: str = Field(description="What happens in the scene")
    emotional_beat: str = Field(description="The emotional tone of this scene (e.g. suspenseful, sorrowful, triumphant)")

class StoryOutput(BaseModel):
    title: str = Field(description="Catchy cinematic title of the film")
    genre: str = Field(description="Main genre (e.g. Sci-Fi, Thriller, Drama)")
    tone: str = Field(description="Overall tone (e.g. melancholic, heroic, dark)")
    target_duration_seconds: int = Field(description="Estimated target duration for the movie")
    characters: List[CharacterProfile] = Field(description="List of characters appearing in the movie")
    plot_summary: str = Field(description="Plot outline summary")
    ending: str = Field(description="Details on the ending scene resolution")
    scene_list: List[SceneBeat] = Field(description="Granular scene breakdown list")

def validate_story_output(story: StoryOutput):
    """
    Validates the generated story.
    Ensures correct structure, consistency, and duration vs. scene count limits.
    """
    if not story.title or not story.title.strip():
        raise ValueError("Title cannot be empty.")
    if not story.genre or not story.genre.strip():
        raise ValueError("Genre cannot be empty.")
    if not story.tone or not story.tone.strip():
        raise ValueError("Tone cannot be empty.")
    if not story.plot_summary or not story.plot_summary.strip():
        raise ValueError("Plot summary cannot be empty.")
    if not story.ending or not story.ending.strip():
        raise ValueError("Ending cannot be empty.")
    if not story.characters:
        raise ValueError("Must generate at least one character.")
    if not story.scene_list:
        raise ValueError("Scene list cannot be empty.")
        
    dur = story.target_duration_seconds
    if dur < 30 or dur > 300:
        raise ValueError(f"Target duration {dur} seconds is outside the permitted range [30, 300].")
        
    scene_count = len(story.scene_list)
    # Target duration dictates expected scene count. Assume 20-30 seconds average per scene (i.e. ~25s/scene).
    # Expected scene count range:
    min_expected = max(1, dur // 35)
    max_expected = max(1, dur // 15)
    
    if scene_count < min_expected or scene_count > max_expected:
        raise ValueError(
            f"Scene count mismatch. For target duration {dur}s, expected between {min_expected} and {max_expected} scenes "
            f"(assuming ~20-30s average per scene). Generated {scene_count} scenes instead."
        )
        
    # Check scene numbers are sequential starting at 1
    for i, scene in enumerate(story.scene_list):
        if scene.scene_number != i + 1:
            raise ValueError(f"Scene numbers must be sequential starting from 1. Scene at index {i} has scene_number={scene.scene_number}.")


def run_story_writer_with_retry(prompt: str, api_key: str) -> StoryOutput:
    """
    Invokes the LLM structure chain. On schema/validation failure, re-prompts once
    with the error appended before raising if it fails twice.
    """
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7, openai_api_key=api_key)
    structured_llm = llm.with_structured_output(StoryOutput)
    
    system_prompt = (
        "You are an expert Hollywood screenplay and story writer. "
        "Analyze the user's prompt and draft a complete story outline.\n\n"
        "IMPORTANT DIRECTIVES:\n"
        "1. Genre and Tone Consistency: Ensure the overall tone and genre match the user prompt.\n"
        "2. Scene Count Constraint: Each scene is estimated to take between 20 and 30 seconds of screen time. "
        "Calculate the appropriate number of scenes by dividing the target duration (between 30 and 300 seconds) "
        "by 25. You MUST NOT generate more or fewer scenes than this calculation allows.\n"
        "3. Output MUST adhere strictly to the schema structure."
    )
    
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", "{prompt}")
    ])
    
    chain = prompt_template | structured_llm
    
    try:
        logger.info("First attempt: Invoking LLM for story writer structured output")
        result = chain.invoke({"prompt": prompt})
        validate_story_output(result)
        return result
    except Exception as e:
        logger.warning(f"First attempt failed: {str(e)}. Retrying with error log appended.")
        
        # Append validation/schema error and retry once
        retry_prompt = (
            f"The previous output failed validation with the following error:\n{str(e)}\n\n"
            f"User Prompt: {prompt}\n\n"
            "Please rewrite and regenerate the story outline. Ensure that:\n"
            "- The scene count matches the target duration constraints (between target_duration / 35 and target_duration / 15 scenes).\n"
            "- All schema attributes are fully populated.\n"
            "- Scene numbers are sequential starting at 1."
        )
        
        try:
            logger.info("Second attempt: Re-invoking LLM for story writer")
            result = chain.invoke({"prompt": retry_prompt})
            validate_story_output(result)
            return result
        except Exception as retry_err:
            logger.error(f"Second attempt failed: {str(retry_err)}")
            raise retry_err


def get_movie_owner(movie_id: int) -> int:
    from fastapi_service.database import execute_single
    row = execute_single("SELECT user_id FROM core_movie WHERE id = %s", (movie_id,))
    if row and row.get("user_id"):
        return int(row["user_id"])
    return 1 # Default guest user

def check_and_inject_recurring_characters(characters_list: List[Dict[str, Any]], owner_user_id: int) -> List[Dict[str, Any]]:
    from fastapi_service.pipeline.consistency_service import check_recurring_character
    
    updated_list = []
    for char in characters_list:
        name = char.get("name", "")
        # Query recurring index
        recurring = check_recurring_character(name, owner_user_id)
        if recurring:
            logger.info(f"Reusing visual descriptors for recurring character: {name}")
            char["physical_description"] = recurring["description"]
            char["reference_sheet_path"] = recurring["reference_image_url"]
            char["is_recurring"] = True
        updated_list.append(char)
    return updated_list


# LangGraph entrypoint
def run_story_writer(state: Any) -> Dict[str, Any]:
    """
    Executes the Story Writer agent.
    """
    prompt = state.user_prompt
    api_key = os.environ.get("OPENAI_API_KEY")
    
    # Get owner user id
    owner_user_id = get_movie_owner(state.movie_id)

    if api_key:
        try:
            logger.info("Running Story Writer LLM chain")
            result = run_story_writer_with_retry(prompt, api_key)
            
            # Save elements to database
            save_story_to_db(state.movie_id, result, owner_user_id)
            
            chars_dump = [c.model_dump() for c in result.characters]
            chars_dump = check_and_inject_recurring_characters(chars_dump, owner_user_id)
            
            return {
                "title": result.title,
                "genre": result.genre,
                "tone": result.tone,
                "target_duration_seconds": result.target_duration_seconds,
                "story_summary": result.plot_summary,
                "characters": chars_dump,
                "scenes": [s.model_dump() for s in result.scene_list]
            }
        except Exception as e:
            logger.error(f"Story Writer LLM failed both attempts: {e}. Falling back to template-based generator.")

    # Fallback Template-based generator
    logger.info("Running Fallback Story Writer Generator")
    fallback_data = generate_fallback_story(prompt)
    save_story_to_db(state.movie_id, fallback_data, owner_user_id)
    
    chars_dump = [c.model_dump() for c in fallback_data.characters]
    chars_dump = check_and_inject_recurring_characters(chars_dump, owner_user_id)
    
    return {
        "title": fallback_data.title,
        "genre": fallback_data.genre,
        "tone": fallback_data.tone,
        "target_duration_seconds": fallback_data.target_duration_seconds,
        "story_summary": fallback_data.plot_summary,
        "characters": chars_dump,
        "scenes": [s.model_dump() for s in fallback_data.scene_list]
    }

def save_story_to_db(movie_id: int, story: StoryOutput, owner_user_id: int = 1):
    """
    Saves generated characters, scenes and main metadata back to Django database.
    """
    from fastapi_service.database import execute_query
    from fastapi_service.pipeline.consistency_service import check_recurring_character
    
    # 1. Update Movie
    movie_query = """
        UPDATE core_movie
        SET title = %s, genre = %s, tone = %s, target_duration_seconds = %s, story_summary = %s
        WHERE id = %s
    """
    execute_query(movie_query, (story.title, story.genre, story.tone, story.target_duration_seconds, story.plot_summary, movie_id))
    
    # Clear existing scenes/characters to prevent duplicates on retries
    execute_query("DELETE FROM core_character WHERE movie_id = %s", (movie_id,))
    execute_query("DELETE FROM core_scene WHERE movie_id = %s", (movie_id,))
    
    # 2. Insert Characters
    for c in story.characters:
        # Check if recurring
        recurring = check_recurring_character(c.name, owner_user_id)
        ref_path = recurring["reference_image_url"] if recurring else None
        phys_desc = recurring["description"] if recurring else c.physical_description
        
        char_query = """
            INSERT INTO core_character (movie_id, name, age, role, personality, physical_description, reference_sheet_path)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        execute_query(char_query, (movie_id, c.name, c.age, c.role, c.personality, phys_desc, ref_path))
        
    # 3. Insert Scenes
    for s in story.scene_list:
        scene_query = """
            INSERT INTO core_scene (movie_id, scene_number, location, time_of_day, description, emotional_beat, order_index)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        execute_query(scene_query, (movie_id, s.scene_number, s.location, s.time_of_day, s.description, s.emotional_beat, s.scene_number))

def generate_fallback_story(prompt: str) -> StoryOutput:
    """
    Helper to return a beautifully detailed story if OpenAI is offline or credentials are not supplied.
    """
    prompt_lower = prompt.lower()
    
    if "mars" in prompt_lower or "astronaut" in prompt_lower or "sci-fi" in prompt_lower:
        title = "Red Solitude"
        genre = "Sci-Fi"
        tone = "Melancholic and Cinematic"
        plot_summary = "An astronaut named Alex is left stranded on Mars after a dust storm separates him from his crew. He must survive on limited rations while waiting for a rescue ship."
        ending = "Alex sees the beacons of the rescue lander breaking through the Martian atmosphere."
        
        characters = [
            CharacterProfile(
                name="Alex",
                age="35",
                role="Protagonist",
                personality="Resilient, reflective, slightly anxious but highly professional.",
                physical_description="Astronaut wearing a worn white spacesuit with gold visor, scuffed patches, dark short hair, stubble."
            ),
            CharacterProfile(
                name="EVA",
                age="N/A",
                role="Supporting AI",
                personality="Calm, synthetic, logical, helpful.",
                physical_description="Holographic interface panel or computer terminal with glowing blue light rings."
            )
        ]
        
        scene_list = [
            SceneBeat(
                scene_number=1,
                location="Martian Ridge",
                time_of_day="DAY",
                description="Alex stands alone on a red mountain ridge, staring out at the vast desert terrain under a faint orange sky.",
                emotional_beat="Isolated and awe-inspiring"
            ),
            SceneBeat(
                scene_number=2,
                location="Habitat Core",
                time_of_day="NIGHT",
                description="Inside the dark capsule, Alex checks oxygen status on a flickering terminal. The artificial AI assistant EVA issues a low warning beep.",
                emotional_beat="Claustrophobic and tense"
            ),
            SceneBeat(
                scene_number=3,
                location="Martian Ridge",
                time_of_day="DAY",
                description="A solar storm approaches. Alex struggles against high winds to secure the main solar collector.",
                emotional_beat="Struggle and desperation"
            ),
            SceneBeat(
                scene_number=4,
                location="Habitat Core",
                time_of_day="NIGHT",
                description="Safe inside, Alex records a final video message for his family on Earth. The comms panel crackles as static transforms into a faint signal.",
                emotional_beat="Emotional and hopeful"
            )
        ]
    else:
        # Generic fallback
        title = "The Silent Echo"
        genre = "Drama"
        tone = "Introspective"
        plot_summary = f"A short dramatic piece reflecting on the themes of: {prompt}"
        ending = "The character stands tall, resolving to face the challenges ahead."
        
        characters = [
            CharacterProfile(
                name="Chris",
                age="28",
                role="Protagonist",
                personality="Quiet, artistic, thoughtful.",
                physical_description="Young individual in a cozy knitted brown sweater, glasses, black boots, looking expressive."
            )
        ]
        
        scene_list = [
            SceneBeat(
                scene_number=1,
                location="Quiet Room",
                time_of_day="DAY",
                description="Chris sits by the window, watching rain drip down the glass panel, writing notes in a small leather notebook.",
                emotional_beat="Somber and quiet"
            ),
            SceneBeat(
                scene_number=2,
                location="City Park",
                time_of_day="NIGHT",
                description="Chris walks beneath the warm glow of street lamps, finding a single glowing lantern hanging from an old oak tree.",
                emotional_beat="Mysterious and magical"
            )
        ]
        
    return StoryOutput(
        title=title,
        genre=genre,
        tone=tone,
        target_duration_seconds=90,
        characters=characters,
        plot_summary=plot_summary,
        ending=ending,
        scene_list=scene_list
    )
