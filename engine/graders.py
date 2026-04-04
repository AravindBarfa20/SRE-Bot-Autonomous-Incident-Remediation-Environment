from models import Action

def calculate_reward(action: Action, is_correct: bool, steps: int) -> float:
    """
    R = Progress_Score - (k * StepCount)
    Penalizes the agent for taking too many steps (brute-forcing).
    """
    time_penalty = 0.05 * steps
    
    if is_correct:
        if action.action_type.value == "resolve":
            return max(0.0, 1.0 - time_penalty)  # Max reward for fixing it
        return max(0.0, 0.5 - time_penalty)      # Partial reward for correct triage
    else:
        # Destructive action penalty
        if action.action_type.value in ["restart_service", "rollback_config"]:
            return -0.2
        return 0.0