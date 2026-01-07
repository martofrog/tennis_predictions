"""
Update Tennis Ratings from Match Data

Processes historical match data and updates player ratings.
"""

import sys
from pathlib import Path
import logging
import argparse
import pandas as pd

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
    data_dir: str = DEFAULT_DATA_DIR,
    incremental: bool = True,
    force_full: bool = False
):
    """
    Update player ratings from historical match data.
    
    Args:
        years: List of years to process (None = all available)
        tour: Tour filter ('atp' or 'wta', None = both)
        ratings_file: Path to ratings JSON file
        data_dir: Directory containing match data CSV files
        incremental: If True, only process matches since last update
        force_full: If True, force full retrain even if ratings exist
    """
    container = get_container(ratings_file=ratings_file, data_dir=data_dir)
    rating_service = container.rating_service()
    rating_system = container.rating_system()
    
    # Check if we should do incremental update
    last_update_date = None
    if incremental and not force_full and rating_service.ratings_exist():
        last_update_date = rating_system.get_last_update_date()
        if last_update_date:
            logger.info(f"Incremental update mode: processing matches since {last_update_date}")
    
    # Load match data
    logger.info(f"Loading match data (years={years}, tour={tour})...")
    matches_df = load_match_data(years=years, tour=tour, data_dir=data_dir)
    
    if matches_df.empty:
        logger.warning("No match data found")
        return
    
    # Filter to only new matches if incremental
    if last_update_date:
        # Convert last_update_date to datetime for comparison
        from datetime import datetime
        try:
            last_update_dt = datetime.fromisoformat(last_update_date.replace('Z', '+00:00'))
            
            # Ensure date column is datetime
            if 'date' in matches_df.columns:
                matches_df['date'] = pd.to_datetime(matches_df['date'], errors='coerce')
                original_count = len(matches_df)
                matches_df = matches_df[matches_df['date'] > last_update_dt]
                new_count = len(matches_df)
                
                if new_count == 0:
                    logger.info("No new matches to process - ratings are up to date")
                    return
                
                logger.info(f"Incremental update: {new_count} new matches (skipped {original_count - new_count} already processed)")
        except Exception as e:
            logger.warning(f"Could not parse last update date, doing full update: {e}")
            last_update_date = None
    
    logger.info(f"Loaded {len(matches_df)} matches")
    
    # Process matches
    processed = 0
    errors = 0
    
    for _, row in matches_df.iterrows():
        try:
            # Extract match information - try different column name variations
            winner = row.get('winner_name') or row.get('winner') or row.get('player1')
            loser = row.get('loser_name') or row.get('loser') or row.get('player2')
            
            if winner is None or loser is None:
                continue
                
            winner = normalize_player_name(str(winner))
            loser = normalize_player_name(str(loser))
            
            if not winner or not loser:
                continue
            
            # Extract scores - try different column name variations
            winner_score = row.get('score') or row.get('winner_score') or row.get('player1_score')
            loser_score = row.get('loser_score') or row.get('player2_score')
            
            # Convert to string if not None
            if winner_score is not None:
                winner_score = str(winner_score)
            if loser_score is not None:
                loser_score = str(loser_score)
            
            # Extract surface
            surface = parse_surface(row.get('surface'))
            
            # Update ratings
            rating_service.update_ratings_from_match(
                winner=winner,
                loser=loser,
                winner_score=winner_score if winner_score else None,
                loser_score=loser_score if loser_score else None,
                surface=surface
            )
            
            processed += 1
            
            if processed % 100 == 0:
                logger.info(f"Processed {processed} matches...")
                
        except Exception as e:
            errors += 1
            logger.warning(f"Error processing match: {e}")
            continue
    
    # Save ratings with last update date
    latest_match_date = None
    if not matches_df.empty and 'date' in matches_df.columns:
        latest_match_date = matches_df['date'].max()
        if pd.notna(latest_match_date):
            latest_match_date = latest_match_date.isoformat()
    
    # Save with metadata
    if hasattr(rating_system, 'save_ratings'):
        rating_system.save_ratings(last_update_date=latest_match_date)
    else:
        rating_service.save_ratings()
    
    logger.info(f"Completed: {processed} matches processed, {errors} errors")
    if latest_match_date:
        logger.info(f"Last processed match date: {latest_match_date}")
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
