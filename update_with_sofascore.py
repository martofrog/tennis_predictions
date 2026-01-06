#!/usr/bin/env python3
"""
Daily Update Script with SofaScore Integration

This script:
1. Downloads recent matches from SofaScore (last 7 days)
2. Updates CSV files for both ATP and WTA
3. Updates player ratings with the new match data

Run this daily via cron to keep your tennis predictions fresh!
"""

import sys
from pathlib import Path
from datetime import datetime
import logging

# Setup path
project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def main():
    """Run daily update process."""
    logger.info("=" * 70)
    logger.info("TENNIS PREDICTIONS - DAILY UPDATE WITH SOFASCORE")
    logger.info("=" * 70)
    
    current_year = datetime.now().year
    
    # Step 1: Update CSV files with SofaScore data
    logger.info("\nStep 1: Downloading recent matches from SofaScore...")
    
    try:
        from src.infrastructure.sofascore_adapter import update_csv_with_sofascore
        
        # Update ATP
        atp_csv = project_root / f"data/atp/atp_matches_{current_year}.csv"
        logger.info(f"Updating {atp_csv.name}...")
        atp_added = update_csv_with_sofascore(
            str(atp_csv),
            days_back=7,
            tour='atp'
        )
        logger.info(f"✓ Added {atp_added} new ATP matches")
        
        # Update WTA
        wta_csv = project_root / f"data/wta/wta_matches_{current_year}.csv"
        logger.info(f"Updating {wta_csv.name}...")
        wta_added = update_csv_with_sofascore(
            str(wta_csv),
            days_back=7,
            tour='wta'
        )
        logger.info(f"✓ Added {wta_added} new WTA matches")
        
        total_new = atp_added + wta_added
        logger.info(f"\n✓ Total new matches downloaded: {total_new}")
        
        if total_new == 0:
            logger.info("No new matches to process. Ratings are up to date.")
            return
        
    except Exception as e:
        logger.error(f"Error downloading from SofaScore: {e}", exc_info=True)
        logger.error("Continuing without new data...")
    
    # Step 2: Update player ratings
    logger.info("\nStep 2: Updating player ratings...")
    
    try:
        from src.data.update_data import main as update_ratings_main
        import sys
        
        # Update ratings for current year
        old_argv = sys.argv
        sys.argv = ['update_data.py', '--years', str(current_year)]
        
        update_ratings_main()
        
        sys.argv = old_argv
        
        logger.info("✓ Player ratings updated successfully")
        
    except Exception as e:
        logger.error(f"Error updating ratings: {e}", exc_info=True)
        raise
    
    # Step 3: Summary
    logger.info("\n" + "=" * 70)
    logger.info("DAILY UPDATE COMPLETE")
    logger.info("=" * 70)
    logger.info(f"✓ {total_new} new matches processed")
    logger.info("✓ Player ratings updated")
    logger.info("✓ System ready for predictions")
    logger.info("=" * 70)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"Daily update failed: {e}", exc_info=True)
        sys.exit(1)

