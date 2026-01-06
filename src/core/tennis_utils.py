"""
Tennis-specific utility functions.

Provides reusable utilities for tennis season calculations, date handling,
and common operations to eliminate code duplication.
"""

from datetime import datetime
from typing import List, Optional
import pandas as pd


def get_current_tennis_year() -> int:
    """
    Get the current tennis year.
    
    Tennis season runs year-round, so we use calendar year.
    
    Returns:
        int: The current calendar year
    """
    return datetime.now().year


def get_years_to_check() -> List[int]:
    """
    Get the current and previous tennis years.
    
    Useful for loading match data that might span multiple years.
    
    Returns:
        List[int]: [previous_year, current_year]
    """
    current_year = get_current_tennis_year()
    return [current_year - 1, current_year]


def find_date_column(df: pd.DataFrame) -> Optional[str]:
    """
    Find the date column in a DataFrame by checking common column names.
    
    Args:
        df: DataFrame to search for date column
        
    Returns:
        Optional[str]: Name of the date column if found, None otherwise
    """
    # Try common date column names in order of preference
    date_column_candidates = ['date', 'Date', 'tourney_date', 'match_date']
    
    for col in date_column_candidates:
        if col in df.columns:
            return col
    
    return None


def normalize_player_name(player_name: str) -> str:
    """
    Normalize player name for consistent matching.
    
    Args:
        player_name: Raw player name
        
    Returns:
        str: Normalized player name (stripped and title-cased)
    """
    return player_name.strip().title()


def parse_surface(surface_str: Optional[str]) -> str:
    """
    Parse and normalize surface string.
    
    Args:
        surface_str: Surface string from data
        
    Returns:
        str: Normalized surface ('hard', 'clay', 'grass', 'carpet')
    """
    if not surface_str:
        return "hard"  # Default
    
    surface_lower = str(surface_str).lower().strip()
    
    # Map variations to standard surfaces
    surface_map = {
        "hard": "hard",
        "hard court": "hard",
        "hardcourt": "hard",
        "clay": "clay",
        "clay court": "clay",
        "grass": "grass",
        "grass court": "grass",
        "carpet": "carpet",
        "indoor hard": "hard",
        "outdoor hard": "hard"
    }
    
    return surface_map.get(surface_lower, "hard")


def parse_tour(tour_str: Optional[str]) -> str:
    """
    Parse and normalize tour string.
    
    Args:
        tour_str: Tour string from data
        
    Returns:
        str: Normalized tour ('atp' or 'wta')
    """
    if not tour_str:
        return "atp"  # Default
    
    tour_lower = str(tour_str).lower().strip()
    
    if "wta" in tour_lower:
        return "wta"
    elif "atp" in tour_lower:
        return "atp"
    else:
        return "atp"  # Default


def calculate_sets_score(score_str: Optional[str]) -> Optional[dict]:
    """
    Parse tennis score string to extract sets information.
    
    Args:
        score_str: Score string (e.g., "6-4 6-3" or "6-4 4-6 6-2")
        
    Returns:
        dict: {'sets_won': int, 'sets_lost': int, 'total_sets': int} or None
    """
    if not score_str:
        return None
    
    try:
        sets = score_str.strip().split()
        sets_won = 0
        sets_lost = 0
        
        for set_score in sets:
            if '-' in set_score:
                parts = set_score.split('-')
                if len(parts) == 2:
                    try:
                        player1_games = int(parts[0])
                        player2_games = int(parts[1])
                        
                        if player1_games > player2_games:
                            sets_won += 1
                        elif player2_games > player1_games:
                            sets_lost += 1
                    except ValueError:
                        continue
        
        return {
            'sets_won': sets_won,
            'sets_lost': sets_lost,
            'total_sets': len(sets)
        }
    except Exception:
        return None
