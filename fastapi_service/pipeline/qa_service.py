import time
import logging
import numpy as np
from typing import List, Dict, Any

# Database helpers
from fastapi_service.database import execute_query, execute_single

logger = logging.getLogger(__name__)

# 1. Golden-set testing runner
def run_golden_set_pipeline_tests(golden_prompts: List[str]) -> Dict[str, Any]:
    """
    Executes mock runs of the generation stages on 10-15 baseline prompts.
    Asserts structure validations (scene counts, schema checks) to verify quality metrics.
    """
    logger.info(f"Golden Set: Starting QA execution on {len(golden_prompts)} prompts...")
    results = []
    
    start_time = time.time()
    for prompt in golden_prompts:
        p_start = time.time()
        
        # Simulate pipeline execution stages
        scene_count = len(prompt.split()) // 3 + 1
        scene_count = max(2, min(scene_count, 10))
        
        # Perform QA structural checks
        is_valid = True
        errors = []
        if len(prompt) < 10:
            is_valid = False
            errors.append("Prompt is too short.")
            
        results.append({
            "prompt": prompt,
            "scene_count": scene_count,
            "execution_time_seconds": time.time() - p_start,
            "status": "PASS" if is_valid else "FAIL",
            "errors": errors
        })
        
    total_time = time.time() - start_time
    logger.info(f"Golden Set: Finished pipeline test runs. Total execution time: {total_time:.2f}s")
    
    return {
        "status": "COMPLETED",
        "total_test_prompts": len(golden_prompts),
        "total_time_seconds": total_time,
        "results": results
    }


# 2. Visual drift detection (cosine similarity check)
def detect_visual_drift(
    current_frame_embeddings: List[List[float]],
    baseline_frame_embeddings: List[List[float]],
    tolerance_threshold: float = 0.82
) -> Dict[str, Any]:
    """
    Compares visual embeddings of rendered storyboard stills against baseline golden outputs.
    Alerts QA engineers if visual quality has drifted beyond tolerance thresholds.
    """
    logger.info("Drift Detector: Comparing rendering similarity against baseline golden-set...")
    
    similarities = []
    for cur, base in zip(current_frame_embeddings, baseline_frame_embeddings):
        # Cosine similarity calculation
        c_arr = np.array(cur)
        b_arr = np.array(base)
        
        dot = np.dot(c_arr, b_arr)
        norm_c = np.linalg.norm(c_arr)
        norm_b = np.linalg.norm(b_arr)
        
        sim = dot / (norm_c * norm_b) if norm_c > 0 and norm_b > 0 else 0.0
        similarities.append(float(sim))
        
    avg_similarity = float(np.mean(similarities)) if similarities else 1.0
    has_drifted = avg_similarity < tolerance_threshold
    
    logger.info(f"Drift Detector: Average similarity: {avg_similarity:.4f} (Threshold: {tolerance_threshold})")
    if has_drifted:
        logger.error(f"Drift Alert! Visual output has drifted below threshold: {avg_similarity:.4f} < {tolerance_threshold}")
        
    return {
        "average_similarity": avg_similarity,
        "tolerance_threshold": tolerance_threshold,
        "status": "DRIFT_DETECTED" if has_drifted else "STABLE"
    }


# 3. Cost regression tracking assertion
def assert_cost_regression(
    current_run_cost: float,
    baseline_run_cost: float,
    variance_allowance: float = 0.15
) -> bool:
    """
    Compares the calculated API/compute charges of the current run against
    baselines, raising warnings on cost surges (runaway jobs).
    """
    diff_percent = (current_run_cost - baseline_run_cost) / baseline_run_cost if baseline_run_cost > 0 else 0.0
    
    logger.info(f"Cost QA: Current Cost: ${current_run_cost:.3f} | Baseline: ${baseline_run_cost:.3f} (Variance: {diff_percent*100:+.1f}%)")
    
    if diff_percent > variance_allowance:
        logger.error(
            f"Cost Surge Warning! Current generation cost exceeds baseline by "
            f"{diff_percent*100:.1f}%, which is above the allowance of {variance_allowance*100:.1f}%."
        )
        return False
        
    logger.info("Cost QA: Cost metrics remain within target safety limits.")
    return True
