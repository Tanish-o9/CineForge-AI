import os
import json
import logging
import numpy as np
from PIL import Image, ImageDraw
from typing import Dict, Any, List

# Database helpers
from fastapi_service.database import execute_query, execute_single

logger = logging.getLogger(__name__)

def run_environment_generator(state: Any) -> Dict[str, Any]:
    """
    Orchestrator node task: Generates visual assets for environments in the movie.
    Ensures environmental visual consistency by creating or retrieving location styling templates.
    """
    movie_id = state.movie_id
    scenes = state.scenes
    logger.info(f"Generating environments for movie {movie_id}")
    
    unique_locations = {}
    for sc in scenes:
        loc_name = sc.get('location')
        if loc_name and loc_name not in unique_locations:
            unique_locations[loc_name] = sc.get('emotional_beat', 'Cinematic atmosphere')
            
    updated_envs = []
    for loc_name, style_beat in unique_locations.items():
        style_prompt = f"A cinematic background of {loc_name}. Mood is {style_beat}. Highly detailed landscape concept art."
        env_data = get_or_create_environment(movie_id, loc_name, style_prompt)
        updated_envs.append(env_data)
        
    return {"environments": updated_envs}

def get_or_create_environment(movie_id: int, location_name: str, style_prompt: str) -> Dict[str, Any]:
    """
    Checks pgvector for an existing location reference in this movie.
    Generates reference if missing and returns styling reference metadata.
    """
    # Look up in postgres
    query = """
        SELECT id, name, style_prompt, reference_image_path
        FROM core_location
        WHERE movie_id = %s AND name = %s
    """
    loc_row = execute_single(query, (movie_id, location_name))
    
    if loc_row:
        logger.info(f"Environment {location_name} already exists. Reusing.")
        return {
            "name": loc_row['name'],
            "style_prompt": loc_row['style_prompt'],
            "reference_image_path": loc_row['reference_image_path']
        }
        
    # Generate new environment style reference
    logger.info(f"Generating new environment template for: {location_name}")
    ref_path = generate_environment_reference_image(movie_id, location_name, style_prompt)
    
    # Generate a mock 512-dimension vector embedding (CLIP-style)
    mock_embedding = list(np.random.normal(0.0, 0.1, 512))
    embedding_str = "[" + ",".join(map(str, mock_embedding)) + "]"
    
    # Save to PostgreSQL pgvector
    insert_query = """
        INSERT INTO core_location (movie_id, name, style_prompt, reference_image_path, embedding)
        VALUES (%s, %s, %s, %s, %s::vector)
    """
    execute_query(insert_query, (movie_id, location_name, style_prompt, ref_path, embedding_str))
    
    return {
        "name": location_name,
        "style_prompt": style_prompt,
        "reference_image_path": ref_path
    }

def generate_environment_reference_image(movie_id: int, location_name: str, style_prompt: str) -> str:
    """
    Generates a high-quality environment reference image.
    If Replicate API is active, calls SDXL. Otherwise, creates a Pillow-based mock image.
    """
    os.makedirs(f"storage/movies/{movie_id}", exist_ok=True)
    clean_name = "".join(x for x in location_name if x.isalnum() or x in (' ', '_')).replace(' ', '_').lower()
    file_path = f"storage/movies/{movie_id}/location_{clean_name}_reference.png"
    
    replicate_token = os.environ.get("REPLICATE_API_TOKEN")
    if replicate_token:
        try:
            import replicate
            logger.info(f"Calling Replicate API for location {location_name} reference board")
            output = replicate.run(
                "stability-ai/sdxl:7730839e782b0ca816349a115840d8565da7d8a922d0d566160d8536e31ae843",
                input={
                    "prompt": f"Environment concept art, wide angle establishing shot of {style_prompt}. Digital painting, scenic, cinematic lighting.",
                    "negative_prompt": "characters, people, low resolution"
                }
            )
            if output and isinstance(output, list) and len(output) > 0:
                import httpx
                resp = httpx.get(output[0])
                if resp.status_code == 200:
                    with open(file_path, "wb") as f:
                        f.write(resp.content)
                    return file_path
        except Exception as e:
            logger.error(f"Replicate API call failed for environment: {e}. Falling back to Pillow.")

    # Pillow fallback: Draw a gorgeous colorized landscape background
    logger.info(f"Generating fallback environment reference image for {location_name} with Pillow")
    img = Image.new("RGB", (800, 450), "#0f172a") # Dark navy base
    draw = ImageDraw.Draw(img)
    
    # Establish distinct colors depending on location type
    loc_lower = location_name.lower()
    if "mars" in loc_lower or "ridge" in loc_lower or "desert" in loc_lower:
        sky_color = "#ea580c"  # Orange sky
        ground_color = "#991b1b" # Rust red ground
        mountain_color = "#7f1d1d"
    elif "spaceship" in loc_lower or "cockpit" in loc_lower or "habitat" in loc_lower:
        sky_color = "#020617"  # Deep black space
        ground_color = "#1e293b" # Steel grey deck
        mountain_color = "#0f172a"
    else:
        sky_color = "#0284c7"  # Soft blue
        ground_color = "#15803d" # Green grass
        mountain_color = "#166534"
        
    # Draw sky
    draw.rectangle([0, 0, 800, 250], fill=sky_color)
    
    # Draw sun/stars
    if "space" in loc_lower or "night" in loc_lower or "habitat" in loc_lower:
        # Draw some stars
        for _ in range(30):
            sx = np.random.randint(10, 790)
            sy = np.random.randint(10, 200)
            draw.ellipse([sx, sy, sx+2, sy+2], fill="#ffffff")
    else:
        # Draw a big sun
        draw.ellipse([350, 80, 450, 180], fill="#fef08a", outline="#facc15", width=2)
        
    # Draw distant mountains
    draw.polygon([(0, 250), (200, 120), (450, 250)], fill=mountain_color)
    draw.polygon([(350, 250), (600, 150), (800, 250)], fill=mountain_color)
    
    # Draw foreground floor
    draw.rectangle([0, 240, 800, 450], fill=ground_color)
    
    # Border
    draw.rectangle([10, 10, 790, 440], outline="#D4AF37", width=3)
    
    # Title Overlay
    draw.rectangle([10, 390, 790, 440], fill="#000000")
    draw.text((30, 405), f"ENVIRONMENT REFERENCE STYLE: {location_name.upper()} — {style_prompt[:60]}...", fill="#D4AF37")
    
    img.save(file_path)
    return file_path
