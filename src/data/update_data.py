"""
Update Tennis Ratings from Match Data

Processes historical match data and updates player ratings.
Includes smart initial ratings and time decay tracking.
"""

import sys
from pathlib import Path
import logging
import argparse
from datetime import datetime

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.services.dependency_container import get_container
from src.core.constants import DEFAULT_RATINGS_FILE, DEFAULT_DATA_DIR
from src.data.data_loader import load_match_data
from src.core.tennis_utils import parse_surface, parse_tour, normalize_player_name

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def update_ratings_from_matches(
    years: list = None,
    tour: str = None,
    ratings_file: str = DEFAULT_RATINGS_FILE,
    data_dir: str = DEFAULT_DATA_DIR
):
    """
    Update player ratings from historical match data.
    
    Args:
        years: List of years to process (None = all available)
        tour: Tour filter ('atp' or 'wta', None = both)
        ratings_file: Path to ratings JSON file
        data_dir: Directory containing match data CSV files
    """
    container = get_container(ratings_file=ratings_file, data_dir=data_dir)
    rating_service = container.rating_service()
    rating_system = container.rating_system()
    
    # Load match data
    logger.info(f"Loading match data (years={years}, tour={tour})...")
    matches_df = load_match_data(years=years, tour=tour, data_dir=data_dir)
    
    if matches_df.empty:
        logger.warning("No match data found")
        return
    
    logger.info(f"Loaded {len(matches_df)} matches")
    
    # Sort matches by date to process chronologically
    date_col = 'tourney_date' if 'tourney_date' in matches_df.columns else 'date'
    if date_col in matches_df.columns:
        matches_df = matches_df.sort_values(date_col)
        logger.info("Matches sorted chronologically")
    
    # Process matches
    processed = 0
    errors = 0
    
    for _, row in matches_df.iterrows():
        try:
            # Extract match information
            winner = normalize_player_name(str(row.get('winner_name', '') or row.get('winner', '')))
            loser = normalize_player_name(str(row.get('loser_name', '') or row.get('loser', '')))
            
            if not winner or not loser:
                continue
            
            # Extract scores
            winner_score = str(row.get('winner_score', '')) or str(row.get('player1_score', ''))
            loser_score = str(row.get('loser_score', '')) or str(row.get('player2_score', ''))
            
            # Extract surface
            surface = parse_surface(row.get('surface'))
            
            # Extract match date for time decay tracking
            match_date = None
            date_str = row.get('tourney_date') or row.get('date') or row.get('match_date')
            if date_str:
                try:
                    # Handle format like '20240115' (YYYYMMDD)
                    date_str = str(date_str)
                    if len(date_str) == 8 and date_str.isdigit():
                        match_date = datetime.strptime(date_str, '%Y%m%d')
                    else:
                        match_date = datetime.fromisoformat(str(date_str))
                except (ValueError, TypeError):
                    pass
            
            # Update ratings
            rating_system.update_ratings(
                winner=winner,
                loser=loser,
                winner_score=winner_score if winner_score else None,
                loser_score=loser_score if loser_score else None,
                surface=surface,
                match_date=match_date
            )
            
            processed += 1
            
            if processed % 1000 == 0:
                logger.info(f"Processed {processed} matches...")
                
        except Exception as e:
            errors += 1
            logger.warning(f"Error processing match: {e}")
            continue
    
    # Save ratings
    rating_service.save_ratings()
    
    logger.info(f"Completed: {processed} matches processed, {errors} errors")
    logger.info(f"Ratings saved to {ratings_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Update tennis player ratings from match data")
    parser.add_argument("--years", nargs="+", type=int, help="Years to process")
    parser.add_argument("--tour", choices=["atp", "wta"], help="Tour filter")
    parser.add_argument("--ratings-file", default=DEFAULT_RATINGS_FILE, help="Ratings file path")
    parser.add_argument("--data-dir", default=DEFAULT_DATA_DIR, help="Data directory")
    
    args = parser.parse_args()
    
    update_ratings_from_matches(
        years=args.years,
        tour=args.tour,
        ratings_file=args.ratings_file,
        data_dir=args.data_dir
    )
