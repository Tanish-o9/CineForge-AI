import os
import sys
import json
import logging
from unittest.mock import MagicMock, patch

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestSaaSFeatures")

# Mock database module to prevent dependency exception
mock_db = MagicMock()
sys.modules['fastapi_service.database'] = mock_db

# Mock Celery to prevent host import exceptions
sys.modules['celery'] = MagicMock()
sys.modules['celery.exceptions'] = MagicMock()

# Import targets
from fastapi_service.pipeline.saas_service import (
    set_current_org_id,
    get_current_org_id,
    apply_row_level_tenant_scoping,
    get_isolated_s3_prefix,
    extract_jwt_tenant_claims
)
from fastapi_service.pipeline.gpu_scheduler import get_target_queue_for_task, estimate_gpu_minutes, GPUScheduler
from fastapi_service.pipeline.collab_service import (
    update_user_presence,
    get_movie_active_presences,
    ClientPresence,
    CommentMessage,
    add_scene_comment,
    get_scene_comments,
    verify_project_permissions
)
from fastapi_service.pipeline.lora_service import trigger_lora_training_job, get_or_create_asset_with_style
from fastapi_service.pipeline.analytics import log_analytics_event, query_organization_dashboard_metrics, recommend_prompt_templates

def run_saas_tests():
    logger.info("=== STARTING SAAS, GPU, COLLAB, LORA, & ANALYTICS TESTS ===")

    mock_db.execute_single.return_value = None
    mock_db.execute_query.return_value = None

    # 1. Test SaaS Scoping and Thread Locals
    logger.info("\nTask 1: Testing Multi-Tenant SaaS Scoping")
    # Verify thread context isolation
    set_current_org_id(45)
    assert get_current_org_id() == 45
    
    # Verify S3 isolated keys
    prefix = get_isolated_s3_prefix(org_id=45, category="movies", file_name="output.mp4")
    logger.info(f"Isolated S3 key: {prefix}")
    assert prefix == "org_45/movies/output.mp4"
    
    # Verify SQL query tenant isolation mixin
    raw_query = "SELECT * FROM core_movie WHERE id = 10"
    mod_query, mod_params = apply_row_level_tenant_scoping(raw_query, (10,))
    logger.info(f"Modified query: {mod_query} (Params: {mod_params})")
    assert "org_id = %s" in mod_query
    assert mod_params[0] == 45
    
    # Verify JWT extraction
    jwt_claims = {"active_org_id": 99, "user_id": 123}
    active_org = extract_jwt_tenant_claims(jwt_claims)
    assert active_org == 99
    assert get_current_org_id() == 99
    logger.info("✔ SaaS Tenant isolation successfully verified.")

    # 2. Test GPU Scheduling and queue weighting
    logger.info("\nTask 2: Testing GPU Worker Fleet Scheduler")
    # Check paid tier priority queue mapping
    q_free = get_target_queue_for_task("ken_burns_animation", "FREE")
    q_pro = get_target_queue_for_task("ken_burns_animation", "PRO")
    logger.info(f"FREE tier queue: {q_free} | PRO tier queue: {q_pro}")
    assert q_free == "video_gen_tasks"
    assert q_pro == "priority_video_gen_tasks"
    
    # Verify GPU minutes estimator
    mins = estimate_gpu_minutes(scenes_count=2, shots_per_scene=4)
    logger.info(f"Estimated GPU minutes for 8 shots: {mins} mins")
    assert mins == 1.6
    
    # Verify GPUScheduler load balancing
    sched = GPUScheduler()
    node = sched.assign_gpu_node_for_job(scenes_count=10, shots_per_scene=4)
    logger.info(f"Assigned load to node: {node}")
    assert "gpu-node" in node
    logger.info("✔ GPU worker fleet manager loops verified successfully.")

    # 3. Test Collaboration & Cursors Presence
    logger.info("\nTask 3: Testing Collaboration & WebSocket Presence Indicator")
    presence = ClientPresence(
        user_id=123,
        username="alice",
        active_scene_number=3,
        cursor_position=250
    )
    update_user_presence(movie_id=101, presence=presence)
    presences = get_movie_active_presences(movie_id=101)
    logger.info(f"Active movie cursors presence: {presences}")
    assert len(presences) == 1
    assert presences[0]["username"] == "alice"
    
    # Test Threaded Comment inserts
    mock_db.execute_single.return_value = {"id": 1}
    add_scene_comment(CommentMessage(
        movie_id=101,
        scene_number=3,
        user_id=123,
        username="alice",
        comment_text="Looks great! @bob check this out."
    ))
    
    # Test Permissions Role hierarchy check
    mock_db.execute_single.return_value = {"role": "EDITOR"}
    assert verify_project_permissions(user_id=123, org_id=99, required_role="VIEWER") is True
    assert verify_project_permissions(user_id=123, org_id=99, required_role="OWNER") is False
    logger.info("✔ Collaboration and WebSocket presence managers verified successfully.")

    # 4. Test Custom LoRA Training Registry
    logger.info("\nTask 4: Testing Custom LoRA style registries")
    # trigger LoRA training background wrapper
    mock_db.execute_query.return_value = None
    job_id = trigger_lora_training_job(org_id=99, style_name="Steampunk", dataset_dir="staging/")
    logger.info(f"Registered LoRA job id: {job_id}")
    
    # Test get_or_create_asset overrides
    with patch("fastapi_service.pipeline.lora_service.get_or_create_asset") as mock_base:
        mock_base.return_value = {"asset_id": 4, "status": "CACHE_HIT"}
        mock_db.execute_single.return_value = {"adapter_s3_path": "s3://style/path.safetensors", "style_name": "Steampunk"}
        
        asset = get_or_create_asset_with_style("character", "Alex", "desc", custom_style_id=2)
        logger.info(f"Styled asset response: {asset}")
        assert asset["custom_style_adapter_path"] == "s3://style/path.safetensors"
    logger.info("✔ Style Training registry triggers verified successfully.")

    # 5. Test Telemetry and Recommendation Analytics
    logger.info("\nTask 5: Testing Telemetry Event stream and CLIP Recommendations")
    
    # Setup dynamic SQL router to prevent mock sequencing StopIteration errors
    def dynamic_query_router(query, params=None, fetch=False):
        q = query.lower()
        if "avg(updated_at - created_at)" in q:
            return [{"current_stage": "story", "avg_duration": "0:02:15"}]
        elif "group by genre" in q:
            return [{"genre": "Sci-Fi", "count": 8}]
        elif "group by status" in q:
            return [{"status": "COMPLETED", "count": 12}]
        elif "core_prompt_template" in q and "1 -" in q:
            return [{"prompt_text": "An astronaut exploring a neon crystal cave on Mars", "similarity": 0.94}]
        return []
        
    mock_db.execute_single.return_value = {"count": 10}
    mock_db.execute_query.side_effect = dynamic_query_router
    
    log_analytics_event(org_id=99, user_id=123, event_type="PROMPT_SUBMITTED")
    
    metrics = query_organization_dashboard_metrics(org_id=99)
    logger.info(f"Dashboard Aggregations metrics: {metrics}")
    assert metrics["movies_generated_this_month"] == 10
    
    recs = recommend_prompt_templates("astronaut in red silt", limit=1)
    logger.info(f"Prompt templates Recommendations: {recs}")
    assert len(recs) == 1
    assert "Mars" in recs[0]["prompt_text"]
    
    logger.info("✔ Telemetry logging and recommendations verified successfully.")

    logger.info("=== ALL SAAS PLATFORM COMPONENTS COMPLETED SUCCESSFULLY ===")

if __name__ == '__main__':
    run_saas_tests()
