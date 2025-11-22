"""
Service for calculating Spaced Repetition (SM-2) intervals.
"""

from datetime import datetime, timedelta
from typing import Tuple

def calculate_next_review(
    rating: int,
    current_interval: int,
    current_ease: float,
    current_repetition: int
) -> Tuple[datetime, int, float, int]:
    """
    Calculates the next review date, interval, ease factor, and repetition count
    based on the SM-2 algorithm.

    Args:
        rating: User rating (0-5). 0-2: Forgot, 3: Hard, 4: Good, 5: Easy.
        current_interval: Current interval in days.
        current_ease: Current ease factor.
        current_repetition: Current repetition count.

    Returns:
        Tuple containing:
        - next_review_date (datetime)
        - new_interval (int)
        - new_ease_factor (float)
        - new_repetition_count (int)
    """
    
    if rating < 3:
        # Forgot
        new_interval = 1
        new_repetition = 0
        new_ease = current_ease # Ease factor doesn't change on failure in some variations, or drops. 
                                # The prompt says: "If a card is hard, this number drops; if easy, it rises."
                                # But standard SM-2 says: EF' = EF + (0.1 - (5-q)*(0.08+(5-q)*0.02))
                                # And if q < 3, start repetitions from beginning.
                                # The prompt simplified logic:
                                # "If Rating < 3 (Forgot): Reset Interval to 1 day, reset Repetitions to 0."
                                # "If Rating >= 3 (Remembered): New Interval = Current Interval * Ease Factor. Update Ease Factor..."
        
        # Let's stick to the prompt's simplified logic for reset, but we should probably update EF too if we want it to drop?
        # Prompt says: "If a card is hard, this number drops". Usually "Forgot" implies hard.
        # However, prompt explicitly says: "If Rating >= 3 ... Update Ease Factor". 
        # It implies EF is ONLY updated when >= 3. 
        # Let's follow the prompt's specific logic for < 3: Reset Interval to 1, Repetitions to 0. 
        # It doesn't explicitly say to change EF here, so we keep it.
        pass 
    else:
        # Remembered
        if current_repetition == 0:
            new_interval = 1
        elif current_repetition == 1:
            new_interval = 6
        else:
            new_interval = int(current_interval * current_ease)
        
        new_repetition = current_repetition + 1
        
        # SM-2 Formula for Ease Factor
        # EF' = EF + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
        # q is rating
        new_ease = current_ease + (0.1 - (5 - rating) * (0.08 + (5 - rating) * 0.02))
        
        if new_ease < 1.3:
            new_ease = 1.3

    next_review_date = datetime.utcnow() + timedelta(days=new_interval)
    
    return next_review_date, new_interval, new_ease, new_repetition
