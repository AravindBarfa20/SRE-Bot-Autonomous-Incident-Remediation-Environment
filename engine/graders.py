from models import Action

def calculate_reward(action: Action, is_correct: bool, steps: int) -> float:
    # Safe fallback decimals strictly between 0 and 1
    if is_correct:
        return 0.85
    return 0.15
