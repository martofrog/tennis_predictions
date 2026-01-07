"""
Tennis-specific utility functions.

Provides reusable utilities for tennis season calculations, date handling,
and common operations to eliminate code duplication.
"""

from datetime import datetime
from typing import List, Optional, Tuple, TYPE_CHECKING, Dict, Any
import pandas as pd
import logging

if TYPE_CHECKING:
    from src.api.main import MatchResultDTO

logger = logging.getLogger(__name__)


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


def parse_tennis_score(score_str: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """
    Parse tennis score string to extract player scores.
    
    Handles multiple score formats:
    - API-Tennis format: "2 - 0" (sets won)
    - Detailed format: "6-4 6-3" (set scores)
    - Edge cases: retirements, walkovers, tiebreaks
    
    Args:
        score_str: Score string from data
        
    Returns:
        Tuple of (player1_score, player2_score) or (None, None) if parsing fails
    """
    if not score_str or str(score_str).strip() == '' or str(score_str) == 'nan':
        return None, None
    
    score_str = str(score_str).strip()
    
    # Handle API-Tennis format: "2 - 0" (sets won)
    if ' - ' in score_str:
        parts = score_str.split(' - ')
        if len(parts) == 2:
            try:
                # This is sets format, convert to set scores format
                sets_won = int(parts[0].strip())
                sets_lost = int(parts[1].strip())
                # Return as "2 0" format (simplified)
                return str(sets_won), str(sets_lost)
            except ValueError:
                pass
    
    # Handle detailed format: "6-4 6-3" or "6-4 4-6 6-2"
    if '-' in score_str and ' ' in score_str:
        sets = score_str.split()
        player1_sets = []
        player2_sets = []
        
        for set_score in sets:
            if '-' in set_score:
                parts = set_score.split('-')
                if len(parts) == 2:
                    try:
                        p1_games = int(parts[0])
                        p2_games = int(parts[1])
                        player1_sets.append(str(p1_games))
                        player2_sets.append(str(p2_games))
                    except ValueError:
                        continue
        
        if player1_sets and player2_sets:
            return " ".join(player1_sets), " ".join(player2_sets)
    
    # Handle single set format: "6-4"
    if '-' in score_str and ' ' not in score_str:
        parts = score_str.split('-')
        if len(parts) == 2:
            try:
                p1_games = int(parts[0])
                p2_games = int(parts[1])
                return str(p1_games), str(p2_games)
            except ValueError:
                pass
    
    # If we can't parse, return None
    logger.debug(f"Could not parse score format: {score_str}")
    return None, None


def transform_csv_row_to_dto(row: pd.Series, date_str: str, tour: str) -> Optional[Dict[str, Any]]:
    """
    Transform a CSV row to dictionary matching MatchResultDTO format.
    
    Args:
        row: pandas Series representing a CSV row
        date_str: Date string in YYYY-MM-DD format
        tour: Tour type ('atp' or 'wta')
        
    Returns:
        Dictionary with MatchResultDTO fields if valid, None otherwise
    """
    try:
        # Get player names
        winner_name = str(row.get('winner_name', '')).strip()
        loser_name = str(row.get('loser_name', '')).strip()
        
        # Validate player names
        if not winner_name or not loser_name or winner_name == 'nan' or loser_name == 'nan':
            return None
        
        # Skip doubles matches (names containing '/')
        if '/' in winner_name or '/' in loser_name:
            return None
        
        # Parse score
        score_str = str(row.get('score', ''))
        player1_score, player2_score = parse_tennis_score(score_str)
        
        # Get tournament info
        tournament_name = str(row.get('tourney_name', ''))
        surface = str(row.get('surface', 'Hard'))
        round_info = str(row.get('round', ''))
        
        return {
            'player1': winner_name,
            'player2': loser_name,
            'player1_score': player1_score,
            'player2_score': player2_score,
            'winner': winner_name,
            'tournament': tournament_name if tournament_name != 'nan' else None,
            'surface': surface if surface != 'nan' else 'Hard',
            'round': round_info if round_info != 'nan' else None,
            'date': date_str,
            'tour': tour.lower()
        }
    except Exception as e:
        logger.debug(f"Error transforming CSV row to DTO: {e}")
        return None
