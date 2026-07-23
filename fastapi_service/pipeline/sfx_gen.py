import os
import json
import logging
from typing import Dict, Any, List, Tuple
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)

from fastapi_service.database import execute_query, execute_single

# 1. Pydantic extraction schema
class ImpliedSoundEvent(BaseModel):
    event_name: str = Field(description="implied sound event, e.g. footsteps, thunder, door, explosion, wind")
    timestamp_in_scene_seconds: float = Field(description="Estimated timestamp in seconds from the start of the scene")
    intensity: str = Field(description="Volume level: subtle, normal, or loud")

class SoundExtractionOutput(BaseModel):
    events: List[ImpliedSoundEvent] = Field(description="List of extracted sound events")

# final cue list schema
class SFXCue(BaseModel):
    event_name: str
    timestamp: float
    sfx_file_path: str
    volume_db: float

# Local tagged library setup (metadata.json loader)
def get_sfx_library_metadata() -> Dict[str, Any]:
    """
    Maintains a dictionary mapping event classes to file candidates and typical durations.
    Saves a defaults catalog to storage/sfx/metadata.json.
    """
    os.makedirs("storage/sfx", exist_ok=True)
    meta_path = "storage/sfx/metadata.json"
    
    default_catalog = {
        "footsteps": {
            "files": ["storage/sfx/footsteps_concrete.wav", "storage/sfx/footsteps_gravel.wav"],
            "duration": 2.0
        },
        "thunder": {
            "files": ["storage/sfx/thunder_distant.wav", "storage/sfx/thunder_crack.wav"],
            "duration": 5.0
        },
        "door": {
            "files": ["storage/sfx/door_creak.wav", "storage/sfx/door_slam.wav"],
            "duration": 1.5
        },
        "explosion": {
            "files": ["storage/sfx/explosion_heavy.wav"],
            "duration": 3.0
        },
        "wind": {
            "files": ["storage/sfx/wind_howl.wav", "storage/sfx/wind_breeze.wav"],
            "duration": 10.0
        }
    }
    
    if not os.path.exists(meta_path):
        with open(meta_path, "w") as f:
            json.dump(default_catalog, f, indent=2)
        return default_catalog
        
    try:
        with open(meta_path, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to read metadata.json: {e}")
        return default_catalog

# 2. Local Embedding Matching Lookup Function
def find_closest_sfx(event_name: str, library_metadata: Dict[str, Any]) -> Tuple[str, float]:
    """
    Queries sentence-transformers model embeddings to pick the closest asset,
    falling back to keyword match if dependencies are missing.
    """
    candidates = list(library_metadata.keys())
    if not candidates:
        return "", 2.0
        
    try:
        # Attempt local SentenceTransformer match
        from sentence_transformers import SentenceTransformer
        import numpy as np
        model = SentenceTransformer('all-MiniLM-L6-v2')
        
        event_emb = model.encode(event_name)
        cand_embs = model.encode(candidates)
        
        similarities = []
        for c_emb in cand_embs:
            dot = np.dot(event_emb, c_emb)
            norm_a = np.linalg.norm(event_emb)
            norm_b = np.linalg.norm(c_emb)
            sim = dot / (norm_a * norm_b) if norm_a > 0 and norm_b > 0 else 0.0
            similarities.append(sim)
            
        best_idx = int(np.argmax(similarities))
        best_cand = candidates[best_idx]
        logger.info(f"SFX Embedding Match: '{event_name}' matches catalog key '{best_cand}' (similarity: {similarities[best_idx]:.4f})")
    except Exception as e:
        logger.warning(f"Embedding search failed: {e}. Falling back to simple keyword matching.")
        # Simple text intersection lookup
        best_cand = candidates[0]
        max_overlap = -1
        for cand in candidates:
            overlap = len(set(event_name.lower().split()) & set(cand.lower().split()))
            if overlap > max_overlap:
                max_overlap = overlap
                best_cand = cand
                
    info = library_metadata[best_cand]
    files = info.get("files", [])
    path = files[0] if files else f"storage/sfx/{best_cand}.wav"
    duration = info.get("duration", 2.0)
    
    return path, duration

# 3. LLM sound extraction chain
def extract_sound_events_from_script(action_lines: List[str], api_key: str) -> List[ImpliedSoundEvent]:
    """
    Invokes the LLM to parse action text for implied sound events.
    """
    if not api_key:
        logger.warning("No API key. Simulating sound extraction.")
        return mock_extracted_events(action_lines)
        
    try:
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3, openai_api_key=api_key)
        structured_llm = llm.with_structured_output(SoundExtractionOutput)
        
        system_prompt = (
            "You are an expert film foley and sound design coordinator.\n"
            "Analyze the action script lines and extract implied sound events.\n\n"
            "FEW-SHOT EXAMPLES:\n"
            "- 'Alex walks across the gravel' -> event: 'footsteps', intensity: 'normal'\n"
            "- 'Lightning illuminates the sky followed by a deafening roar' -> event: 'thunder', intensity: 'loud'\n"
            "- 'He softly pushes open the rusty hinge' -> event: 'door', intensity: 'subtle'\n\n"
            "DIRECTIVE:\n"
            "Keep detections conservative. Only extract sounds that are explicitly implied by movement or visual cues."
        )
        
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("user", "Action script lines:\n{lines}")
        ])
        
        chain = prompt_template | structured_llm
        output = chain.invoke({"lines": "\n".join(action_lines)})
        return output.events
    except Exception as e:
        logger.error(f"Sound extraction LLM call failed: {e}. Splicing fallbacks.")
        return mock_extracted_events(action_lines)

def mock_extracted_events(action_lines: List[str]) -> List[ImpliedSoundEvent]:
    """
    Mock parser analyzing text keywords for sound cue extraction.
    """
    events = []
    text = "\n".join(action_lines).lower()
    
    if "walk" in text or "step" in text or "boot" in text:
        events.append(ImpliedSoundEvent(event_name="footsteps", timestamp_in_scene_seconds=1.5, intensity="normal"))
    if "storm" in text or "wind" in text or "blow" in text:
        events.append(ImpliedSoundEvent(event_name="wind", timestamp_in_scene_seconds=0.0, intensity="subtle"))
    if "door" in text or "hatch" in text:
        events.append(ImpliedSoundEvent(event_name="door", timestamp_in_scene_seconds=4.5, intensity="normal"))
        
    return events

# LangGraph Orchestrator Node entrypoint
def run_sfx_generator(state: Any) -> Dict[str, Any]:
    """
    Executes SFX Agent. Extracted events are mapped to local WAV paths
    and volume parameters are calculated based on intensity.
    """
    movie_id = state.movie_id
    scenes = state.scenes
    api_key = os.environ.get("OPENAI_API_KEY")
    
    # Load SFX metadata catalog
    catalog = get_sfx_library_metadata()
    
    for sc in scenes:
        scene_number = sc.get('scene_number')
        scene_row = execute_single("SELECT id FROM core_scene WHERE movie_id = %s AND scene_number = %s", (movie_id, scene_number))
        if not scene_row:
            continue
        scene_id = scene_row['id']
        
        # Screenplay action lines extraction
        # Screenplay format: screenplay_text contains action lines and dialogues.
        # We can extract text or search for screenplay fields.
        # Let's mock extract or parse lines:
        raw_text = sc.get('screenplay_text', '')
        action_lines = [line.strip() for line in raw_text.split("\n") if line.strip() and not line.startswith('"')]
        
        # Extract events
        sfx_events = extract_sound_events_from_script(action_lines, api_key)
        
        # Map events to local WAV files
        scene_cues = []
        for ev in sfx_events:
            wav_path, dur = find_closest_sfx(ev.event_name, catalog)
            
            # Map intensity to volume dB values
            # subtle -> -12dB, normal -> -6dB, loud -> 0dB
            volume = -6.0
            if ev.intensity == "subtle":
                volume = -12.0
            elif ev.intensity == "loud":
                volume = 0.0
                
            # Create sound file dummy on host if missing so editor can compile safely
            os.makedirs(os.path.dirname(wav_path), exist_ok=True)
            if not os.path.exists(wav_path):
                with open(wav_path, "wb") as f:
                    f.write(b"MOCK WAV AUDIO DATA")
                    
            cue = SFXCue(
                event_name=ev.event_name,
                timestamp=ev.timestamp_in_scene_seconds,
                sfx_file_path=wav_path,
                volume_db=volume
            )
            
            # Record asset in Postgres
            meta = {"intensity": ev.intensity, "timestamp": ev.timestamp_in_scene_seconds, "volume_db": volume}
            insert_query = """
                INSERT INTO core_asset (movie_id, scene_id, asset_type, file_path, meta_data, created_at)
                VALUES (%s, %s, 'SFX', %s, %s, NOW())
            """
            execute_query(insert_query, (movie_id, scene_id, wav_path, json.dumps(meta)))
            
            scene_cues.append(cue.model_dump())
            
        sc['sfx_cues'] = scene_cues
        
    return {"scenes": scenes}
