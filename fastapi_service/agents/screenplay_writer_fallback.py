import logging
from typing import List, Dict, Any
from .screenplay_writer import ScreenplayOutputSchema, SceneScreenplay, CustomDialogueLine

logger = logging.getLogger(__name__)

def generate_fallback_screenplay(title: str, characters: List[Dict[str, Any]], scenes: List[Dict[str, Any]], target_duration: int) -> ScreenplayOutputSchema:
    """
    Synthesizes script pages matching character lists.
    """
    written_scenes = []
    num_scenes = len(scenes)
    duration_per_scene = max(10, target_duration // num_scenes if num_scenes > 0 else 20)

    # Detect character names
    char_names = [c['name'] for c in characters]
    p1 = char_names[0] if len(char_names) > 0 else "Protagonist"
    p2 = char_names[1] if len(char_names) > 1 else "Supporting"

    for idx, sc in enumerate(scenes):
        scene_number = sc.get('scene_number', idx + 1)
        location = sc.get('location', 'Location')
        time_of_day = sc.get('time_of_day', 'DAY')
        heading = f"EXT. {location.upper()} - {time_of_day.upper()}"
        
        # Build dialogues based on location / prompt matching
        dialogue = []
        action_lines = []

        if "Martian" in location or "Habitat" in location or "Ridge" in location:
            if scene_number == 1:
                action_lines = [
                    f"{p1} stands near a massive red crag, suit covered in fine orange dust.",
                    "The wind howls, a low frequency rumble through his audio suit receiver.",
                    "He raises a gloved hand to shield his eyes from the glare."
                ]
                dialogue = [
                    CustomDialogueLine(character=p1, delivery_note="(sighing)", line="Another sol, another endless horizon. Nothing but rust and cold."),
                    CustomDialogueLine(character=p2, delivery_note="(synthetic crackle)", line="Warning: Core body temperature is decreasing, Alex. Suggest returning to pod.")
                ]
            elif scene_number == 2:
                action_lines = [
                    f"Inside the dimly lit Habitat Capsule. Control screens glow red, casting shadows.",
                    f"{p1} strips off his helmet, gasping. He walks to the main computer terminal."
                ]
                dialogue = [
                    CustomDialogueLine(character=p1, delivery_note="(frustrated)", line="How long can the atmospheric seal hold, EVA? Give me a straight answer."),
                    CustomDialogueLine(character=p2, delivery_note="(logical tone)", line="At current leak rates, pressure containment remains viable for 48 hours.")
                ]
            elif scene_number == 3:
                action_lines = [
                    "Outside. Red wind whips dust in thick currents.",
                    "Alex drags a heavy cable through the storm, his boots slipping in the dry silt."
                ]
                dialogue = [
                    CustomDialogueLine(character=p1, delivery_note="(screaming over wind)", line="Hold on! I almost have the primary link locked down!"),
                    CustomDialogueLine(character=p2, delivery_note="(strained warning)", line="Grid power fluctuations detected. Solar collector alignment critical.")
                ]
            else:
                action_lines = [
                    "Back in the habitat core. Alex sits in front of the console recorder.",
                    "He presses record, a small green light reflects in his eyes."
                ]
                dialogue = [
                    CustomDialogueLine(character=p1, delivery_note="(softly)", line="If you're hearing this... I made it. Look up at the stars. I'm coming home."),
                    CustomDialogueLine(character=p2, delivery_note="(cheerful chirp)", line="Comms link established. Rescue lander is entering final descent.")
                ]
        else:
            # Generic fallback dialogue
            action_lines = [
                f"{p1} moves slowly around the {location}.",
                f"The atmosphere is tense. {p1} looks toward the screen."
            ]
            dialogue = [
                CustomDialogueLine(character=p1, delivery_note="(calmly)", line=f"I can feel the history in this place. It's too quiet."),
            ]
            if len(char_names) > 1:
                dialogue.append(
                    CustomDialogueLine(character=p2, delivery_note="(nervously)", line=f"We should leave before the system resets itself.")
                )

        written_scenes.append(
            SceneScreenplay(
                scene_number=scene_number,
                scene_heading=heading,
                action_lines=action_lines,
                dialogue=dialogue,
                estimated_screen_time_seconds=duration_per_scene
            )
        )

    # Adjust durations to sum precisely to target_duration
    total_est = sum(s.estimated_screen_time_seconds for s in written_scenes)
    diff = target_duration - total_est
    if diff != 0 and len(written_scenes) > 0:
        written_scenes[-1].estimated_screen_time_seconds = max(5, written_scenes[-1].estimated_screen_time_seconds + diff)

    return ScreenplayOutputSchema(scenes=written_scenes)
