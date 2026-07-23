import os
import sys
import json
import logging
from unittest.mock import MagicMock

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestEnterpriseSSOQA")

# Mock database module to prevent dependency exception
mock_db = MagicMock()
sys.modules['fastapi_service.database'] = mock_db

# Mock Celery to prevent host import exceptions
sys.modules['celery'] = MagicMock()
sys.modules['celery.exceptions'] = MagicMock()

# Import targets
from fastapi_service.pipeline.compliance_service import write_compliance_audit_log, simulate_oidc_sso_handshake, execute_scim_user_provisioning
from fastapi_service.pipeline.qa_service import run_golden_set_pipeline_tests, detect_visual_drift, assert_cost_regression
from fastapi_service.pipeline.creative_service import score_screenplay_quality, reward_user_progression_xp, CineForgePlugin, PluginManager

def run_enterprise_sso_qa_tests():
    logger.info("=== STARTING ENTERPRISE SSO, COMPLIANCE, QA, SCORING, & PLUGIN TESTS ===")

    # 1. Compliance immutable hash chains
    logger.info("\nTask 20: Testing SOC2 Immutable Hash-Chained Audit Trails & SSO")
    mock_db.execute_single.side_effect = [
        None, # Log 1: empty database check
        {"current_hash": "f8a2de62bca908b98efacb287661"}, # Log 2: returns previous hash
        {"current_hash": "f8a2de62bca908b98efacb287661"}  # SCIM log: returns previous hash
    ]
    mock_db.execute_query.return_value = None
    
    # Write first log
    log_1 = write_compliance_audit_log("USER_LOGIN", "User admin logged in.")
    logger.info(f"Log 1 hashes: parent={log_1['parent_hash'][:8]}... | current={log_1['current_hash'][:8]}...")
    assert log_1["parent_hash"] == "0" * 64
    
    # Write second log (parent hash must match log 1's current_hash mock)
    log_2 = write_compliance_audit_log("PROJECT_DELETED", "Movie project 45 deleted.")
    logger.info(f"Log 2 hashes: parent={log_2['parent_hash'][:8]}... | current={log_2['current_hash'][:8]}...")
    assert log_2["parent_hash"] == "f8a2de62bca908b98efacb287661"
    
    # OIDC SSO
    sso = simulate_oidc_sso_handshake("https://issuer.com", "OIDC_VALID_TOKEN")
    assert sso["status"] == "AUTHENTICATED"
    
    # SCIM Sync
    scim = execute_scim_user_provisioning("CREATE", "test@corp.com", org_id=5)
    assert scim["status"] == "SUCCESS"
    logger.info("✔ OIDC auth, SCIM provisioning, and SOC2 immutable hash chains verified successfully.")

    # 2. Automated QA Regression
    logger.info("\nTask 21: Testing Golden-Set Runner, Drift, & Cost Alerting")
    # Golden Set Runner
    qa_results = run_golden_set_pipeline_tests(["Mars expedition stranded astronaut", "Comedy diner talking dog"])
    logger.info(f"QA results: {qa_results}")
    assert qa_results["total_test_prompts"] == 2
    
    # Visual Drift detection (comparing two frame embedding matrices)
    emb_a = [[0.12, 0.45, 0.88]]
    emb_b = [[0.13, 0.44, 0.87]] # high similarity -> STABLE
    drift_res = detect_visual_drift(emb_a, emb_b)
    logger.info(f"Drift detector output (Stable): {drift_res}")
    assert drift_res["status"] == "STABLE"
    
    emb_c = [[0.88, -0.45, -0.12]] # low similarity -> DRIFT
    drift_res_2 = detect_visual_drift(emb_a, emb_c)
    logger.info(f"Drift detector output (Drifted): {drift_res_2}")
    assert drift_res_2["status"] == "DRIFT_DETECTED"
    
    # Cost regression
    cost_ok = assert_cost_regression(current_run_cost=0.45, baseline_run_cost=0.42)
    assert cost_ok is True
    cost_bad = assert_cost_regression(current_run_cost=0.98, baseline_run_cost=0.42) # exceeds 15% allowance
    assert cost_bad is False
    logger.info("✔ Golden-set tests, cosine drift alerts, and cost regressions verified successfully.")

    # 3. Creative Scoring, Plugins, & Progression
    logger.info("\nTask 22: Testing Pacing Quality, Plugins, & XP Milestones")
    # Quality scoring
    quality = score_screenplay_quality("Space movie story", "A silent astronaut stands in danger. Alert bells ring!")
    logger.info(f"Screenplay quality: {quality}")
    assert quality["overall_score"] >= 7.0
    
    # XP Ledger
    mock_db.execute_single.side_effect = None
    mock_db.execute_single.return_value = {"total_xp": 250} # mock user total XP
    xp = reward_user_progression_xp(user_id=12, event_type="MOVIE_COMPLETED")
    logger.info(f"XP Reward: {xp}")
    assert xp["xp_gained"] == 100
    assert "Novice Creator" in xp["unlocked_milestones"]
    
    # Dynamic Plugin Sandbox insertion
    class MockTitlePlugin(CineForgePlugin):
        def get_hook_point(self) -> str:
            return "before_story"
        def execute(self, state_dict: dict) -> dict:
            state_dict["user_prompt"] = state_dict["user_prompt"].upper()
            return state_dict
            
    p_mgr = PluginManager()
    p_mgr.register_plugin(MockTitlePlugin())
    
    state = {"user_prompt": "chess duel in rain"}
    modified_state = p_mgr.run_plugins_at_hook("before_story", state)
    logger.info(f"Plugin execution result state: {modified_state}")
    assert modified_state["user_prompt"] == "CHESS DUEL IN RAIN"
    logger.info("✔ Pacing scorers, dynamic sandbox plugins, and XP Milestones verified successfully.")

    logger.info("=== ALL ENTERPRISE COMPLIANCE AND CREATIVE TESTS COMPLETED SUCCESSFULLY ===")

if __name__ == '__main__':
    run_enterprise_sso_qa_tests()
