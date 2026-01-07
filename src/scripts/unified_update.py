"""
Unified Update Process

This module provides a unified update process that:
1. Downloads historical data if missing (Jeff Sackmann 2020-2025)
2. Downloads last 7 days from SofaScore for current year
3. Trains/updates the model with all available data

Used by both startup and daily update processes.
"""

import sys
from pathlib import Path
from datetime import datetime
import logging

# Setup path
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

logger = logging.getLogger(__name__)


def check_historical_data_exists() -> dict:
    """
    Check if historical data exists for previous years.
    
    Returns:
        Dictionary with years as keys and exists status as values
    """
    current_year = datetime.now().year
    historical_years = range(2020, current_year)  # 2020-2025 (not including current year)
    
    data_status = {
        'atp': {},
        'wta': {}
    }
    
    for year in historical_years:
        atp_file = project_root / f"data/atp/atp_matches_{year}.csv"
        wta_file = project_root / f"data/wta/wta_matches_{year}.csv"
        
        data_status['atp'][year] = atp_file.exists()
        data_status['wta'][year] = wta_file.exists()
    
    return data_status


def download_historical_data():
    """
    Download historical data from Jeff Sackmann repository (2020-2025).
    Only downloads if data is missing.
    """
    logger.info("Checking historical data availability...")
    
    data_status = check_historical_data_exists()
    
    # Check if any historical data is missing
    missing_atp = [year for year, exists in data_status['atp'].items() if not exists]
    missing_wta = [year for year, exists in data_status['wta'].items() if not exists]
    
    if not missing_atp and not missing_wta:
        logger.info("✓ All historical data (2020-2025) already exists")
        return True
    
    logger.info(f"Missing historical data - ATP: {missing_atp}, WTA: {missing_wta}")
    logger.info("Downloading from Jeff Sackmann repository...")
    
    try:
        # Import downloader
        downloader_module_path = project_root / "download_match_data.py"
        if not downloader_module_path.exists():
            logger.warning("download_match_data.py not found, skipping historical download")
            return False
        
        import importlib.util
        import io
        import contextlib
        
        spec = importlib.util.spec_from_file_location("download_match_data", downloader_module_path)
        download_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(download_module)
        
        downloader_class = download_module.TennisDataDownloader
        data_dir = project_root / "data"
        downloader = downloader_class(data_dir=str(data_dir))
        
        # Download missing years
        current_year = datetime.now().year
        years_to_download = list(range(2020, current_year))
        
        logger.info(f"Downloading historical data for years: {years_to_download}")
        
        # Suppress print statements from downloader
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            for year in years_to_download:
                # Download ATP
                if year in missing_atp:
                    atp_result = downloader.download_matches(year, tour="atp")
                    if atp_result is not None:
                        logger.info(f"✓ Downloaded ATP {year}: {len(atp_result)} matches")
                
                # Download WTA
                if year in missing_wta:
                    wta_result = downloader.download_matches(year, tour="wta")
                    if wta_result is not None:
                        logger.info(f"✓ Downloaded WTA {year}: {len(wta_result)} matches")
        
        logger.info("✓ Historical data download completed")
        return True
        
    except Exception as e:
        logger.error(f"Error downloading historical data: {e}", exc_info=True)
        return False


def download_recent_data():
    """
    Download last 7 days of matches from SofaScore for current year.
    
    Returns:
        Tuple of (atp_added, wta_added) - number of new matches added
    """
    logger.info("Downloading recent matches from SofaScore (last 7 days)...")
    
    try:
        from src.infrastructure.sofascore_adapter import update_csv_with_sofascore
        
        current_year = datetime.now().year
        
        # Update ATP
        atp_csv = project_root / f"data/atp/atp_matches_{current_year}.csv"
        atp_added = update_csv_with_sofascore(str(atp_csv), days_back=7, tour='atp')
        logger.info(f"✓ Added {atp_added} new ATP matches")
        
        # Update WTA
        wta_csv = project_root / f"data/wta/wta_matches_{current_year}.csv"
        wta_added = update_csv_with_sofascore(str(wta_csv), days_back=7, tour='wta')
        logger.info(f"✓ Added {wta_added} new WTA matches")
        
        return atp_added, wta_added
        
    except Exception as e:
        logger.error(f"Error downloading recent data from SofaScore: {e}", exc_info=True)
        return 0, 0


def train_model(force_full: bool = False):
    """
    Train/update the model with incremental or full training.
    
    Args:
        force_full: If True, retrain from scratch. If False, incremental update.
    
    Returns:
        Number of players with updated ratings, or 0 if failed
    """
    from src.services.dependency_container import get_container
    
    # Check if ratings exist
    container = get_container()
    rating_service = container.rating_service()
    ratings_exist = rating_service.ratings_exist()
    
    if not ratings_exist:
        logger.info("No existing ratings found - performing full training...")
        force_full = True
    elif force_full:
        logger.info("Force full retrain requested - processing all matches...")
    else:
        logger.info("Incremental update mode - processing only new matches...")
    
    try:
        from src.data.update_data import update_ratings_from_matches
        
        # Update ratings from all available years
        current_year = datetime.now().year
        all_years = list(range(2020, current_year + 1))
        
        # This function loads matches, updates ratings, and saves them
        # incremental=True means it will only process new matches if ratings exist
        update_ratings_from_matches(
            years=all_years,
            tour=None,
            incremental=True,
            force_full=force_full
        )
        
        # Get rating count from container (reload to get updated ratings)
        from src.services.dependency_container import reset_container
        reset_container()
        container = get_container()
        rating_system = container.rating_system()
        ratings_count = len(rating_system.get_all_ratings())
        
        logger.info(f"✓ Model updated - {ratings_count} players rated")
        return ratings_count
        
    except Exception as e:
        logger.error(f"Error training model: {e}", exc_info=True)
        return 0


def run_unified_update(force_historical: bool = False, force_full_retrain: bool = False):
    """
    Run the unified update process.
    
    This function:
    1. Downloads historical data if missing (or if force_historical=True)
    2. Downloads last 7 days from SofaScore
    3. Trains the model (incrementally by default, or full if force_full_retrain=True)
    
    Args:
        force_historical: If True, re-download all historical data even if it exists
        force_full_retrain: If True, retrain from scratch instead of incremental
        
    Returns:
        Dictionary with update results
    """
    logger.info("=" * 70)
    logger.info("UNIFIED UPDATE PROCESS")
    logger.info("=" * 70)
    
    results = {
        'historical_downloaded': False,
        'recent_atp_added': 0,
        'recent_wta_added': 0,
        'total_players': 0,
        'success': False
    }
    
    try:
        # Step 1: Download historical data if missing
        logger.info("\nStep 1: Historical Data")
        if force_historical:
            logger.info("Force download enabled - will re-download all historical data")
            results['historical_downloaded'] = download_historical_data()
        else:
            data_status = check_historical_data_exists()
            missing_years = (
                [y for y, e in data_status['atp'].items() if not e] +
                [y for y, e in data_status['wta'].items() if not e]
            )
            
            if missing_years:
                logger.info(f"Missing data for years: {set(missing_years)}")
                results['historical_downloaded'] = download_historical_data()
            else:
                logger.info("✓ All historical data present")
                results['historical_downloaded'] = True
        
        # Step 2: Download recent data (last 7 days)
        logger.info("\nStep 2: Recent Data (Last 7 Days)")
        atp_added, wta_added = download_recent_data()
        results['recent_atp_added'] = atp_added
        results['recent_wta_added'] = wta_added
        
        total_new = atp_added + wta_added
        logger.info(f"✓ Total new matches: {total_new}")
        
        # Step 3: Train model (incremental by default)
        logger.info("\nStep 3: Update Model")
        total_players = train_model(force_full=force_full_retrain)
        results['total_players'] = total_players
        
        # Summary
        logger.info("\n" + "=" * 70)
        logger.info("UPDATE COMPLETE")
        logger.info("=" * 70)
        logger.info(f"✓ Historical data: {'Downloaded' if results['historical_downloaded'] else 'Already present'}")
        logger.info(f"✓ New matches: ATP={atp_added}, WTA={wta_added}")
        logger.info(f"✓ Players rated: {total_players}")
        logger.info("=" * 70)
        
        results['success'] = True
        return results
        
    except Exception as e:
        logger.error(f"Unified update failed: {e}", exc_info=True)
        results['success'] = False
        return results


if __name__ == "__main__":
    """Allow running as standalone script."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    import argparse
    parser = argparse.ArgumentParser(description='Run unified update process')
    parser.add_argument('--force-historical', action='store_true',
                       help='Force re-download of all historical data')
    parser.add_argument('--full-retrain', action='store_true',
                       help='Force full model retrain instead of incremental update')
    args = parser.parse_args()
    
    results = run_unified_update(
        force_historical=args.force_historical,
        force_full_retrain=args.full_retrain
    )
    
    if not results['success']:
        sys.exit(1)

