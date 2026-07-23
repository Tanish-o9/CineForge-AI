import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional

# Database helpers
from fastapi_service.database import execute_query, execute_single

logger = logging.getLogger(__name__)

# 1. Screenplay Quality & Hook evaluator
def score_screenplay_quality(story_text: str, screenplay_text: str) -> Dict[str, Any]:
    """
    Evaluates pacing, hook strength, and dialogue naturalness before running the rendering pipeline.
    """
    logger.info("Evaluating screenplay hook pacing and dialogue metrics...")
    
    # Prompt template for scoring LLMs
    prompt = f"""
    Review the following screenplay dialogue:
    "{screenplay_text}"

    Analyze the quality:
    1. Hook Strength: Does the opening (first 10 seconds / 30 words) engage the audience?
    2. Dialogue naturalness: Do character lines feel dynamic and appropriate?
    3. Pacing: Is action balanced with dialogues?
    
    Return scoring metrics out of 10.
    """
    
    # Simulated analysis based on word parameters
    word_count = len(screenplay_text.split())
    hook_score = 8.5 if "alert" in screenplay_text.lower() or "danger" in screenplay_text.lower() else 7.0
    dialogue_score = 8.0 if "?" in screenplay_text or "!" in screenplay_text else 6.5
    
    pacing_score = 7.5
    if word_count > 300:
        pacing_score = 6.0 # dialogue is too verbose, needs action beats!
        
    avg_score = (hook_score + dialogue_score + pacing_score) / 3
    
    feedback = "Screenplay quality passes criteria."
    if avg_score < 7.0:
        feedback = "Alert: Dialogue is too verbose or lacks a hook. Recommend adding action beats."
        
    return {
        "overall_score": avg_score,
        "metrics": {
            "hook_strength": hook_score,
            "dialogue_naturalness": dialogue_score,
            "pacing": pacing_score
        },
        "feedback": feedback
    }


# 2. Dynamic Plugin Interface ABC + Graph Insertion logic
class CineForgePlugin(ABC):
    """
    Abstract base class for worker plugins. Custom plugins must override these hooks.
    """
    @abstractmethod
    def get_hook_point(self) -> str:
        """
        Returns hook stage name: 'before_story', 'after_storyboard', 'before_export', etc.
        """
        pass
        
    @abstractmethod
    def execute(self, state_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Modifies and returns the state dictionary.
        """
        pass

class PluginManager:
    def __init__(self):
        self.registry: Dict[str, List[CineForgePlugin]] = {}
        
    def register_plugin(self, plugin: CineForgePlugin):
        hook = plugin.get_hook_point()
        if hook not in self.registry:
            self.registry[hook] = []
        self.registry[hook].append(plugin)
        logger.info(f"Plugins: Registered custom plugin for hook point '{hook}'")
        
    def run_plugins_at_hook(self, hook_point: str, state_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes registered custom plugins at the designated hook stage.
        """
        plugins = self.registry.get(hook_point, [])
        if not plugins:
            return state_dict
            
        logger.info(f"Plugins: Triggering {len(plugins)} plugins at hook point '{hook_point}'")
        current_state = state_dict.copy()
        
        for p in plugins:
            try:
                # Execution sandbox wrapper (in production, run inside subprocess / isolated scope)
                current_state = p.execute(current_state)
            except Exception as e:
                logger.error(f"Plugins: Plugin {p.__class__.__name__} failed: {e}")
                
        return current_state


# 3. Gamified Creator Progression XP tables
def initialize_creative_tables():
    try:
        execute_query("""
            CREATE TABLE IF NOT EXISTS core_user_xp_ledger (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                xp_gained INTEGER NOT NULL,
                event_type VARCHAR(50) NOT NULL, -- MOVIE_COMPLETED, REMIX_CREATED, LIKE_RECEIVED
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        execute_query("""
            CREATE TABLE IF NOT EXISTS core_user_milestone (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                milestone_title VARCHAR(100) NOT NULL,
                unlocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, milestone_title)
            );
        """)
    except Exception as e:
        logger.error(f"Failed to initialize creative progression: {e}")

def reward_user_progression_xp(user_id: int, event_type: str) -> Dict[str, Any]:
    """
    Logs XP points in database, checks for milestone thresholds, and unlocks perks.
    """
    initialize_creative_tables()
    
    xp_rewards = {
        "MOVIE_COMPLETED": 100,
        "REMIX_CREATED": 50,
        "LIKE_RECEIVED": 20
    }
    
    xp = xp_rewards.get(event_type, 10)
    
    # Ingest XP record
    execute_query(
        "INSERT INTO core_user_xp_ledger (user_id, xp_gained, event_type) VALUES (%s, %s, %s)",
        (user_id, xp, event_type)
    )
    
    # Query total accumulated XP
    total = execute_single(
        "SELECT SUM(xp_gained) as total_xp FROM core_user_xp_ledger WHERE user_id = %s",
        (user_id,)
    )
    total_xp = total["total_xp"] if total and total["total_xp"] is not None else 0
    
    # Milestone checks
    unlocked_milestones = []
    milestone_thresholds = {
        "Novice Creator": 100,
        "Auteur Director": 500,
        "CineForge Legend": 2000
    }
    
    for title, req_xp in milestone_thresholds.items():
        if total_xp >= req_xp:
            # Attempt milestone insertion (will ignore on duplicate constraint)
            try:
                execute_query("""
                    INSERT INTO core_user_milestone (user_id, milestone_title)
                    VALUES (%s, %s)
                    ON CONFLICT DO NOTHING
                """, (user_id, title))
                unlocked_milestones.append(title)
            except Exception as me:
                logger.error(f"Failed to register milestone: {me}")
                
    return {
        "user_id": user_id,
        "xp_gained": xp,
        "total_xp": total_xp,
        "unlocked_milestones": unlocked_milestones
    }
