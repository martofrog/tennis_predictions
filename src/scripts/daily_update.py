"""
Daily Update Script

Automated script to download new match data and update ratings.
"""

import sys
from pathlib import Path
import logging

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.data.download_tennis_data import download_tennis_data
from src.data.update_data import update_ratings_from_matches
from src.core.tennis_utils import get_current_tennis_year

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """Run daily update: download data and update ratings."""
    current_year = get_current_tennis_year()
    
    logger.info("="*70)
    logger.info("Starting daily tennis data update...")
    logger.info("="*70)
    
    # Download data for current year (both tours)
    logger.info("Step 1: Downloading latest match data...")
    try:
        download_tennis_data([current_year], tour="atp")
        download_tennis_data([current_year], tour="wta")
        logger.info("✓ Match data download completed")
    except Exception as e:
        logger.warning(f"⚠ Data download had issues: {e}")
        logger.info("Continuing with existing data...")
    
    # Update ratings
    logger.info("Step 2: Updating player ratings...")
    try:
        update_ratings_from_matches(years=[current_year])
        logger.info("✓ Player ratings updated successfully")
    except Exception as e:
        logger.error(f"✗ Error updating ratings: {e}")
        raise
    
    logger.info("="*70)
    logger.info("Daily update completed")
    logger.info("="*70)


if __name__ == "__main__":
    main()
