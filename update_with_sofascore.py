#!/usr/bin/env python3
"""
Tennis Predictions Update Script

This script uses the unified update process to:
1. Download historical data if missing (Jeff Sackmann 2020-2025)
2. Download recent matches from SofaScore (last 7 days)
3. Train/update the model with all available data

Run this manually or via cron to keep your tennis predictions fresh!
"""

import sys
from pathlib import Path
import logging
import argparse

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
    """Run unified update process."""
    parser = argparse.ArgumentParser(
        description='Update tennis predictions data and model'
    )
    parser.add_argument(
        '--force-historical',
        action='store_true',
        help='Force re-download of all historical data (2020-2025)'
    )
    parser.add_argument(
        '--full-retrain',
        action='store_true',
        help='Force full model retrain instead of incremental update (takes 3-4 minutes)'
    )
    args = parser.parse_args()
    
    try:
        from src.scripts.unified_update import run_unified_update
        
        logger.info("Starting Tennis Predictions update...")
        
        if args.full_retrain:
            logger.info("Full retrain mode: will process all 26K+ matches")
        else:
            logger.info("Incremental mode: will process only new matches (faster)")
        
        results = run_unified_update(
            force_historical=args.force_historical,
            force_full_retrain=args.full_retrain
        )
        
        if results['success']:
            logger.info("✓ Update completed successfully")
            return 0
        else:
            logger.error("✗ Update completed with errors")
            return 1
            
    except Exception as e:
        logger.error(f"Update failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)

