import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

# 1. Celery priority queue mapping
TASK_QUEUE_MAP = {
    "story_generation": "llm_tasks",         # CPU-only, cheap
    "screenplay_writing": "llm_tasks",       # CPU-only, cheap
    "storyboard_generation": "image_gen_tasks", # GPU-medium (needs VRAM for SDXL/Flux turnarounds)
    "voice_synthesis": "voice_audio_tasks",   # CPU / light-GPU
    "ken_burns_animation": "video_gen_tasks",# GPU-heavy (needs codecs, ffmpeg, MoviePy scaling)
    "video_assembly": "video_gen_tasks"      # GPU-heavy
}

def get_target_queue_for_task(task_type: str, billing_plan: str = "FREE") -> str:
    """
    Returns appropriate Celery queue for task types.
    Enforces paid priority routing: PRO and ENTERPRISE tasks are routed
    to high-priority queues to preempt FREE queue pools.
    """
    base_queue = TASK_QUEUE_MAP.get(task_type, "llm_tasks")
    if billing_plan in ["PRO", "ENTERPRISE"]:
        # High priority queues have higher celery concurrency weights
        return f"priority_{base_queue}"
    return base_queue


# 2. Pre-flight GPU Minutes Estimator
def estimate_gpu_minutes(scenes_count: int, shots_per_scene: int) -> float:
    """
    Estimates total GPU execution minutes based on visual asset tasks.
    - SDXL image-gen: ~3 seconds per shot still (0.05 minutes)
    - MoviePy rendering/panning: ~9 seconds per shot clip (0.15 minutes)
    """
    total_shots = scenes_count * shots_per_scene
    image_gen_mins = total_shots * 0.05
    video_anim_mins = total_shots * 0.15
    return float(image_gen_mins + video_anim_mins)


# 3. GPU Node Scheduler Load Balancer
class GPUNode:
    def __init__(self, node_id: str, capacity_limit: float = 60.0):
        self.node_id = node_id
        self.capacity = capacity_limit # Max GPU minutes load allowed concurrently
        self.current_load = 0.0

class GPUScheduler:
    def __init__(self):
        # Sample cluster nodes
        self.nodes = [
            GPUNode("gpu-node-us-east-1", capacity_limit=120.0),
            GPUNode("gpu-node-us-east-2", capacity_limit=120.0),
            GPUNode("gpu-node-us-west-1", capacity_limit=60.0)
        ]
        
    def assign_gpu_node_for_job(self, scenes_count: int, shots_per_scene: int) -> str:
        """
        Estimates job size and schedules it to the GPU node with the least active load.
        Enforces load-balancing instead of blind round-robin.
        """
        job_load = estimate_gpu_minutes(scenes_count, shots_per_scene)
        
        # Pick node with least current load
        best_node = min(self.nodes, key=lambda n: n.current_load)
        
        # Check capacity bounds
        if best_node.current_load + job_load > best_node.capacity:
            logger.warning(
                f"Cluster warning: GPUScheduler capacity warning. Best node {best_node.node_id} "
                f"current load: {best_node.current_load}m, job requires: {job_load}m."
            )
            
        best_node.current_load += job_load
        logger.info(
            f"GPUScheduler: Assigned job of {job_load:.2f} GPU-minutes to node '{best_node.node_id}' "
            f"(New Load: {best_node.current_load:.2f}m)"
        )
        return best_node.node_id
        
    def release_node_load(self, node_id: str, scenes_count: int, shots_per_scene: int):
        """
        Deducts load upon successful task complete.
        """
        job_load = estimate_gpu_minutes(scenes_count, shots_per_scene)
        for n in self.nodes:
            if n.node_id == node_id:
                n.current_load = max(0.0, n.current_load - job_load)
                logger.info(f"GPUScheduler: Released {job_load:.2f}m load from node '{node_id}'. Current Load: {n.current_load:.2f}m")
                break
