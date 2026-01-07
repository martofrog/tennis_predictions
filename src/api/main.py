"""
Tennis Predictions REST API - SOLID Architecture

This API demonstrates all SOLID principles:
- Single Responsibility: Each endpoint has one responsibility
- Open/Closed: Easy to extend with new endpoints without modification
- Liskov Substitution: Services use interfaces, implementations are interchangeable
- Interface Segregation: Small, focused interfaces
- Dependency Inversion: Depends on abstractions via dependency injection
"""

import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Any
from contextlib import asynccontextmanager
import os
import logging

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from src.services.dependency_container import get_container, reset_container
from src.services.rating_service import RatingService
from src.services.betting_service import BettingService
from src.infrastructure.adapters import ApiTennisAdapter
from src.core.constants import (
    DEFAULT_MIN_EDGE,
    DEFAULT_RATINGS_FILE,
    SportKey
)
from src.core.exceptions import RepositoryError, ValidationError, OddsProviderError

# Load environment variables
try:
    from src.infrastructure.load_env import load_env_file
    load_env_file()
except ImportError:
    pass

# Setup logger
logger = logging.getLogger(__name__)

# Background scheduler for daily updates
scheduler = BackgroundScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    startup_event()
    yield
    shutdown_event()


# Initialize FastAPI app with lifespan
app = FastAPI(
    title="Tennis Predictions API - SOLID Architecture",
    description="REST API following SOLID principles for ATP/WTA match predictions and value betting",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def download_missing_data(missing_years: List[tuple]) -> None:
    """
    Download missing data for specified tours/years.
    
    Args:
        missing_years: List of tuples (tour, year) to download
    """
    downloader_module_path = project_root / "download_match_data.py"
    if not downloader_module_path.exists():
        logger.error("download_match_data.py not found")
        return
    
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("download_match_data", downloader_module_path)
        download_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(download_module)
        TennisDataDownloader = download_module.TennisDataDownloader
        
        downloader = TennisDataDownloader(data_dir=str(project_root / "data"))
        
        for tour, year in missing_years:
            logger.info(f"  Downloading {tour.upper()} {year}...")
            result = downloader.download_matches(year, tour=tour, verbose=False, use_fallback=True)
            if result is not None:
                logger.info(f"  ✓ {tour.upper()} {year} downloaded ({len(result)} matches)")
            else:
                logger.warning(f"  ⚠️  {tour.upper()} {year} not available")
    except Exception as e:
        logger.error(f"Failed to download missing data: {e}")


def download_all_historical_data(years: int = 5) -> None:
    """
    Download all historical data for recent years.
    
    Args:
        years: Number of recent years to download (default: 5)
    """
    from datetime import datetime
    current_year = datetime.now().year
    years_to_download = list(range(current_year - years + 1, current_year + 1))
    
    missing_years = []
    for tour in ['atp', 'wta']:
        for year in years_to_download:
            missing_years.append((tour, year))
    
    if missing_years:
        logger.info(f"📥 Downloading {years} years of historical data...")
        download_missing_data(missing_years)


def update_match_data():
    """Daily update: download recent data and retrain incrementally."""
    logger.info("=" * 70)
    logger.info("🔄 DAILY DATA UPDATE")
    logger.info("=" * 70)
    
    try:
        from datetime import datetime, timedelta
        import pandas as pd
        
        current_year = datetime.now().year
        yesterday = datetime.now() - timedelta(days=1)
        data_dir = project_root / "data"
        
        # Step 1: Fetch yesterday's results from API-Tennis
        logger.info(f"📥 Step 1/3: Fetching yesterday's results ({yesterday.strftime('%Y-%m-%d')}) from API-Tennis...")
        try:
            api_tennis = ApiTennisAdapter()
            for tour in ['atp', 'wta']:
                logger.info(f"  Fetching {tour.upper()} results...")
                results = api_tennis.get_results_by_date(yesterday, tour)
                
                if results:
                    new_df = pd.DataFrame(results)
                    year_file = data_dir / tour / f"{tour}_matches_{current_year}.csv"
                    
                    if year_file.exists():
                        existing_df = pd.read_csv(year_file)
                        combined = pd.concat([existing_df, new_df], ignore_index=True)
                        # Deduplicate by date and player names
                        combined = combined.drop_duplicates(
                            subset=['tourney_date', 'winner_name', 'loser_name'],
                            keep='last'
                        )
                        combined = combined.sort_values('tourney_date')
                        combined.to_csv(year_file, index=False)
                        logger.info(f"  ✓ {tour.upper()} yesterday updated ({len(new_df)} new matches, {len(combined)} total)")
                    else:
                        year_file.parent.mkdir(parents=True, exist_ok=True)
                        new_df.to_csv(year_file, index=False)
                        logger.info(f"  ✓ {tour.upper()} yesterday created ({len(new_df)} matches)")
                else:
                    logger.info(f"  ℹ️  No {tour.upper()} results found for yesterday")
        except Exception as e:
            logger.warning(f"  ⚠️  Failed to fetch results from API-Tennis: {e}")

        # Step 2: Download recent years (current year + previous year) from tennis-data.co.uk
        # This ensures we get updates even if tennis-data.co.uk updates weekly
        logger.info("📥 Step 2/3: Downloading recent data from tennis-data.co.uk...")
        downloader_module_path = project_root / "download_match_data.py"
        if downloader_module_path.exists():
            import importlib.util
            spec = importlib.util.spec_from_file_location("download_match_data", downloader_module_path)
            download_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(download_module)
            TennisDataDownloader = download_module.TennisDataDownloader
            
            data_dir = project_root / "data"
            downloader = TennisDataDownloader(data_dir=str(data_dir))
            
            # Download current year and previous year (tennis-data.co.uk may have updates)
            years_to_update = [current_year - 1, current_year]
            
            for year in years_to_update:
                for tour in ['atp', 'wta']:
                    logger.info(f"  Checking {tour.upper()} {year}...")
                    result = downloader.download_matches(year, tour=tour, verbose=False, use_fallback=True)
                    if result is not None:
                        # Merge with existing file if it exists
                        year_file = data_dir / tour / f"{tour}_matches_{year}.csv"
                        if year_file.exists():
                            existing_df = pd.read_csv(year_file)
                            # Combine and remove duplicates
                            combined = pd.concat([existing_df, result], ignore_index=True)
                            combined = combined.drop_duplicates(
                                subset=['tourney_date', 'winner_name', 'loser_name'],
                                keep='last'
                            )
                            combined = combined.sort_values('tourney_date')
                            combined.to_csv(year_file, index=False)
                            logger.info(f"  ✓ {tour.upper()} {year} updated ({len(combined)} total matches)")
                        else:
                            result.to_csv(year_file, index=False)
                            logger.info(f"  ✓ {tour.upper()} {year} created ({len(result)} matches)")
                    else:
                        logger.info(f"  ℹ️  {tour.upper()} {year} not available or no new data")
        else:
            logger.warning("⚠️  download_match_data.py not found, skipping download")
        
        # Step 3: Retrain model incrementally
        logger.info("🏋️  Step 3/3: Retraining model with new data...")
        train_model_at_startup()
        
        logger.info("=" * 70)
        logger.info("✅ Daily update completed successfully")
        logger.info("=" * 70)
    except Exception as e:
        logger.error("=" * 70)
        logger.error(f"❌ Daily scheduled update failed: {e}")
        logger.error("=" * 70)
        import traceback
        traceback.print_exc()


def train_model_at_startup():
    """
    Train or update the Elo rating model at startup.
    
    - If ratings don't exist: Full training from all available data
    - If ratings exist: Incremental training from last update date
    """
    logger.info("=" * 70)
    logger.info("🎾 TENNIS PREDICTIONS - MODEL TRAINING")
    logger.info("=" * 70)
    
    try:
        from datetime import datetime
        import json
        from src.data.data_loader import load_match_data
        from src.core.tennis_utils import parse_surface, normalize_player_name
        
        metadata_file = project_root / "data" / ".ratings_metadata.json"
        ratings_file = project_root / "data" / "ratings.json"
        
        # Check if ratings exist
        ratings_exist = ratings_file.exists() and ratings_file.stat().st_size > 100
        metadata_exists = metadata_file.exists()
        
        # Load metadata to get last update date
        last_update_date = None
        if metadata_exists:
            try:
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
                    last_update_str = metadata.get('last_update')
                    if last_update_str:
                        last_update_date = datetime.fromisoformat(last_update_str)
            except Exception as e:
                logger.warning(f"Could not load metadata: {e}")
        
        # If metadata is missing but ratings exist, this is an inconsistent state
        # Delete ratings to force full retrain
        if ratings_exist and not metadata_exists:
            logger.warning("⚠️  Ratings file exists but metadata is missing - this is inconsistent!")
            logger.warning("🗑️  Deleting ratings.json to force full retrain...")
            try:
                ratings_file.unlink()
                ratings_exist = False
                logger.info("✓ Ratings file deleted successfully")
                
                # Reset the global container to ensure fresh initialization
                # This is critical because the rating system loads ratings in __init__
                from src.services.dependency_container import reset_container
                reset_container()
                logger.info("✓ Container reset - will reinitialize with empty ratings")
            except Exception as e:
                logger.error(f"Failed to delete ratings file: {e}")
        
        # Check if we have any historical data files
        atp_dir = project_root / "data" / "atp"
        wta_dir = project_root / "data" / "wta"
        atp_files = list(atp_dir.glob("atp_matches_*.csv")) if atp_dir.exists() else []
        wta_files = list(wta_dir.glob("wta_matches_*.csv")) if wta_dir.exists() else []
        has_historical_data = len(atp_files) > 0 or len(wta_files) > 0
        
        # Full dump scenario: no ratings, no metadata, no historical data
        if not ratings_exist and not metadata_exists and not has_historical_data:
            logger.info("🆕 Full dump scenario detected - downloading all available data...")
            download_all_historical_data(years=5)
            # Force full training (last_update_date = None)
            last_update_date = None
        else:
            # Normal flow: check for missing data and download
            from datetime import datetime
            current_year = datetime.now().year
            years_to_check = list(range(current_year - 4, current_year + 1))  # Last 5 years including current
            
            missing_years = []
            for tour in ['atp', 'wta']:
                for year in years_to_check:
                    data_file = (project_root / "data" / tour / f"{tour}_matches_{year}.csv")
                    if not data_file.exists() or data_file.stat().st_size < 1000:  # Empty/small file
                        missing_years.append((tour, year))
            
            # Download missing data using unified download function
            if missing_years:
                logger.info(f"📥 Downloading {len(missing_years)} missing data files...")
                download_missing_data(missing_years)
        
        if ratings_exist and last_update_date:
            logger.info(f"📊 Ratings found - Last updated: {last_update_date.strftime('%Y-%m-%d %H:%M')}")
            logger.info("🔄 Running INCREMENTAL update (processing new matches only)...")
        else:
            logger.info("📊 No ratings found - Running FULL training from scratch...")
            last_update_date = None
        
        # Get container - this will load ratings from file if they exist
        # IMPORTANT: We must get the container AFTER checking/deleting the ratings file
        # because the rating system loads ratings in its __init__ method
        container = get_container()
        rating_system = container.rating_system()
        
        # Load match data
        logger.info("📥 Loading match data...")
        matches_df = load_match_data()
        
        if matches_df.empty:
            logger.error("❌ No match data found after download attempt")
            logger.error("   Please check data directory and try running: python download_match_data.py")
            return
        
        logger.info(f"✓ Loaded {len(matches_df)} total matches")
        
        # Filter to new matches if incremental
        if last_update_date:
            # Convert tourney_date to datetime for comparison
            date_col = 'tourney_date' if 'tourney_date' in matches_df.columns else 'date'
            if date_col in matches_df.columns:
                matches_df[date_col] = matches_df[date_col].astype(str)
                matches_df['match_datetime'] = matches_df[date_col].apply(
                    lambda x: datetime.strptime(x, '%Y%m%d') if len(str(x)) == 8 else None
                )
                matches_df = matches_df[matches_df['match_datetime'] > last_update_date]
                logger.info(f"🔍 Found {len(matches_df)} new matches since last update")
        
        if matches_df.empty and last_update_date:
            logger.info("✓ Ratings are up to date - no new matches to process")
            return
        
        # Sort chronologically
        date_col = 'tourney_date' if 'tourney_date' in matches_df.columns else 'date'
        if date_col in matches_df.columns:
            matches_df = matches_df.sort_values(date_col)
        
        # Process matches
        logger.info("🏋️  Training model...")
        processed = 0
        errors = 0
        start_time = datetime.now()
        
        for _, row in matches_df.iterrows():
            try:
                winner = normalize_player_name(str(row.get('winner_name', '') or row.get('winner', '')))
                loser = normalize_player_name(str(row.get('loser_name', '') or row.get('loser', '')))
                
                if not winner or not loser:
                    continue
                
                surface = parse_surface(row.get('surface'))
                
                # Extract match date
                match_date = None
                date_str = row.get('tourney_date') or row.get('date')
                if date_str:
                    try:
                        date_str = str(date_str)
                        if len(date_str) == 8 and date_str.isdigit():
                            match_date = datetime.strptime(date_str, '%Y%m%d')
                    except (ValueError, TypeError):
                        pass
                
                # Update ratings
                rating_system.update_ratings(
                    winner=winner,
                    loser=loser,
                    surface=surface,
                    match_date=match_date
                )
                
                processed += 1
                
                if processed % 5000 == 0:
                    logger.info(f"  Processed {processed} matches...")
                    
            except Exception as e:
                errors += 1
                if errors < 5:  # Only log first few errors
                    logger.warning(f"Error processing match: {e}")
        
        # Save ratings
        logger.info("💾 Saving ratings...")
        rating_system.save_ratings()
        
        # Save metadata
        metadata = {
            'last_update': datetime.now().isoformat(),
            'total_players': len(rating_system._ratings),
            'matches_processed_this_session': processed
        }
        metadata_file.parent.mkdir(parents=True, exist_ok=True)
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        elapsed = (datetime.now() - start_time).total_seconds()
        
        logger.info("=" * 70)
        logger.info(f"✅ MODEL TRAINING COMPLETE")
        logger.info(f"   Processed: {processed} matches")
        logger.info(f"   Errors: {errors}")
        logger.info(f"   Total players: {metadata['total_players']}")
        logger.info(f"   Time: {elapsed:.1f} seconds")
        logger.info("=" * 70)
        
    except Exception as e:
        logger.error(f"❌ Model training failed: {e}")
        import traceback
        traceback.print_exc()


def startup_event():
    """Startup event - initialize scheduler, download data, and train model."""
    logger.info("🚀 Starting Tennis Predictions API...")
    
    scheduler.start()
    logger.info("✓ Background scheduler started")
    
    # Schedule daily match data update at 6am
    update_hour = int(os.getenv("MATCH_DATA_UPDATE_HOUR", "6"))
    update_minute = int(os.getenv("MATCH_DATA_UPDATE_MINUTE", "0"))
    
    scheduler.add_job(
        update_match_data,
        trigger=CronTrigger(hour=update_hour, minute=update_minute),
        id="update_match_data",
        name="Update match data and retrain model daily",
        replace_existing=True
    )
    logger.info(f"✓ Scheduled daily update & training at {update_hour:02d}:{update_minute:02d}")
    
    # Ensure match data is downloaded if missing (can be disabled via env var)
    auto_download = os.getenv("AUTO_DOWNLOAD_MATCH_DATA", "true").lower() == "true"
    if auto_download:
        try:
            logger.info("📥 Checking for missing match data...")
            # Import from project root
            downloader_module_path = project_root / "download_match_data.py"
            if downloader_module_path.exists():
                import importlib.util
                spec = importlib.util.spec_from_file_location("download_match_data", downloader_module_path)
                download_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(download_module)
                TennisDataDownloader = download_module.TennisDataDownloader
                
                data_dir = project_root / "data"
                
                # Check if we have recent data (last 2 years) for both tours
                from datetime import datetime
                current_year = datetime.now().year
                recent_years = [current_year - 1, current_year]
                
                logger.info(f"📥 Checking for match data (years: {recent_years})...")
                
                missing_data = []
                for tour in ['atp', 'wta']:
                    tour_dir = data_dir / tour
                    for year in recent_years:
                        data_file = tour_dir / f"{tour}_matches_{year}.csv"
                        if not data_file.exists():
                            missing_data.append((tour, year))
                            logger.info(f"  Missing: {tour.upper()} {year}")
                
                if missing_data:
                    logger.info("📥 Downloading missing match data (with tennis-data.co.uk fallback)...")
                    downloader = TennisDataDownloader(data_dir=str(data_dir))
                    
                    for tour, year in missing_data:
                        logger.info(f"  Attempting {tour.upper()} {year}...")
                        result = downloader.download_matches(year, tour=tour, verbose=True, use_fallback=True)
                        if result is not None:
                            logger.info(f"  ✓ {tour.upper()} {year} downloaded successfully ({len(result)} matches)")
                        else:
                            logger.warning(f"  ⚠️  {tour.upper()} {year} could not be downloaded")
                    
                    logger.info("✓ Match data check completed")
                else:
                    logger.info("✓ All required match data is present")
            else:
                logger.debug("download_match_data.py not found, skipping automatic download")
        except Exception as e:
            logger.warning(f"Could not check/download match data: {e}")
    else:
        logger.info("Automatic match data download is disabled (AUTO_DOWNLOAD_MATCH_DATA=false)")
    
    # Train or update model
    train_model_at_startup()


def shutdown_event():
    """Shutdown event - stop scheduler."""
    scheduler.shutdown()
    logger.info("Background scheduler stopped")


# API Models (DTOs)

class PlayerRatingDTO(BaseModel):
    """Data Transfer Object for player rating."""
    player_name: str
    rating: float
    tour: str


class MatchResultDTO(BaseModel):
    """Data Transfer Object for match result."""
    player1: str
    player2: str
    player1_score: Optional[str] = None
    player2_score: Optional[str] = None
    winner: Optional[str] = None
    tournament: Optional[str] = None
    surface: Optional[str] = None
    round: Optional[str] = None
    date: Optional[str] = None
    tour: Optional[str] = None


class PredictionDTO(BaseModel):
    """Data Transfer Object for match prediction."""
    player1: str
    player2: str
    player1_win_probability: float
    player2_win_probability: float
    player1_rating: float
    player2_rating: float
    surface: str
    surface_adjustment: float
    favorite: str
    confidence: float


class ValueBetDTO(BaseModel):
    """Data Transfer Object for value bet."""
    match_id: str
    player1: str
    player2: str
    bet_on_player: str
    is_player1_bet: bool
    bookmaker: str
    odds: float
    our_probability: float
    bookmaker_probability: float
    edge_percentage: float
    expected_value_percentage: float
    recommended_stake: Optional[float]
    commence_time: str
    surface: str
    tour: str


class HealthResponseDTO(BaseModel):
    """Health check response."""
    status: str
    timestamp: str
    service: str
    api_key_configured: bool
    ratings_loaded: bool
    architecture: str


class CacheStatusDTO(BaseModel):
    """Cache status response."""
    enabled: bool
    size: int
    ttl_seconds: int
    cached_keys: List[str] = []
    cache_details: Dict[str, Any] = {}


# Dependency Injection Helpers

def get_rating_service() -> RatingService:
    """Get rating service instance from container."""
    container = get_container()
    return container.rating_service()


def get_betting_service() -> BettingService:
    """Get betting service instance from container."""
    container = get_container()
    return container.betting_service()


# Mount static files for UI
static_dir = project_root / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# API Endpoints

@app.get("/", tags=["General"])
async def root():
    """Root endpoint - serves the web UI."""
    ui_file = project_root / "static" / "index.html"
    if ui_file.exists():
        return FileResponse(str(ui_file))
    return {
        "message": "Tennis Predictions API - SOLID Architecture",
        "version": "2.0.0",
        "architecture": "SOLID Principles",
        "endpoints": {
            "health": "/health",
            "ratings": "/api/v2/ratings",
            "predict": "/api/v2/predict",
            "value_bets": "/api/v2/value-bets",
            "cache_status": "/api/v2/cache/status",
            "cache_clear": "/api/v2/cache/clear (DELETE)",
            "docs": "/docs"
        },
        "features": [
            "Dependency Injection",
            "Repository Pattern",
            "Service Layer",
            "Interface Segregation",
            "Liskov Substitution",
            "ATP & WTA Support",
            "Surface-specific Ratings"
        ]
    }


@app.get("/api/v2/health", response_model=HealthResponseDTO, tags=["General"])
async def health_check():
    """
    Health check endpoint.
    
    Demonstrates: Single Responsibility (only checking health)
    """
    api_key = os.getenv("ODDS_API_KEY")
    rating_service = get_rating_service()
    
    return HealthResponseDTO(
        status="healthy",
        timestamp=datetime.now().isoformat(),
        service="tennis-predictions",
        api_key_configured=bool(api_key),
        ratings_loaded=rating_service.ratings_exist(),
        architecture="SOLID"
    )


@app.get("/api/v2/ratings", response_model=List[PlayerRatingDTO], tags=["Ratings"])
async def get_ratings(
    tour: Optional[str] = Query(None, description="Filter by tour (atp or wta)", pattern="^(atp|wta)$"),
    limit: Optional[int] = Query(None, description="Limit number of results", ge=1),
    surface: Optional[str] = Query(None, description="Get ratings for specific surface", pattern="^(hard|clay|grass)$")
):
    """
    Get player ratings with optional filtering.
    
    Args:
        tour: Filter by tour (atp or wta)
        limit: Maximum number of results to return
        surface: Get ratings for specific surface (hard, clay, grass)
    
    Demonstrates: Dependency Inversion (depends on IRatingSystem via service)
    """
    rating_service = get_rating_service()
    all_ratings = rating_service.get_all_ratings(surface=surface)
    
    # Build player-to-tour lookup
    player_tour_lookup = _get_player_tour_lookup()
    
    # Filter out doubles players and create DTOs
    result = []
    for r in all_ratings:
        if '/' in r.player:
            continue  # Skip doubles
        
        tour_value = player_tour_lookup.get(r.player, "atp")  # Default to ATP if unknown
        
        # Filter by tour if specified
        if tour and tour_value != tour:
            continue
        
        result.append(PlayerRatingDTO(
            player_name=r.player,
            rating=r.rating,
            tour=tour_value
        ))
    
    # Apply limit if specified
    if limit:
        result = result[:limit]
    
    return result


@app.get("/api/v2/matches/yesterday", response_model=List[MatchResultDTO], tags=["Matches"])
async def get_yesterday_matches(tour: str = Query("atp", description="Tour (atp or wta)")):
    """
    Get yesterday's match results from local data files.
    
    Args:
        tour: Tournament tour ('atp' or 'wta')
        
    Returns:
        List of match results
    """
    from datetime import datetime, timedelta
    import pandas as pd
    from pathlib import Path
    
    # Get yesterday's date
    yesterday = datetime.now() - timedelta(days=1)
    date_str = yesterday.strftime("%Y-%m-%d")
    yesterday_date_int = int(yesterday.strftime("%Y%m%d"))
    current_year = datetime.now().year
    
    try:
        # Load from local CSV files (already downloaded)
        data_dir = project_root / "data" / tour.lower()
        csv_file = data_dir / f"{tour.lower()}_matches_{current_year}.csv"
        
        if not csv_file.exists():
            # Try previous year if current year file doesn't exist
            csv_file = data_dir / f"{tour.lower()}_matches_{current_year - 1}.csv"
        
        if not csv_file.exists():
            logger.warning(f"No data file found for {tour} {current_year}")
            return []
        
        # Read CSV file
        df = pd.read_csv(csv_file)
        
        # Filter for yesterday's matches
        matches = []
        
        for _, row in df.iterrows():
            # Parse date from the row (tourney_date is in YYYYMMDD format)
            date_val = row.get('tourney_date')
            if pd.notna(date_val):
                try:
                    # Convert to int for comparison
                    row_date_int = int(str(date_val))
                    
                    # Only include yesterday's matches
                    if row_date_int != yesterday_date_int:
                        continue
                except (ValueError, TypeError):
                    continue
            else:
                continue
            
            # Get player names
            winner_name = str(row.get('winner_name', '')).strip()
            loser_name = str(row.get('loser_name', '')).strip()
            
            if not winner_name or not loser_name or winner_name == 'nan' or loser_name == 'nan':
                continue
            
            # Skip doubles matches (names containing '/')
            if '/' in winner_name or '/' in loser_name:
                continue
            
            # Parse score (format: "6-4 6-3" or similar)
            score_str = str(row.get('score', ''))
            if score_str and score_str != 'nan':
                # Split score into sets
                sets = score_str.split()
                winner_sets = []
                loser_sets = []
                
                for set_score in sets:
                    if '-' in set_score:
                        parts = set_score.split('-')
                        if len(parts) == 2:
                            winner_sets.append(parts[0])
                            loser_sets.append(parts[1])
                
                winner_score_str = " ".join(winner_sets) if winner_sets else None
                loser_score_str = " ".join(loser_sets) if loser_sets else None
            else:
                winner_score_str = None
                loser_score_str = None
            
            # Get tournament info
            tournament_name = str(row.get('tourney_name', ''))
            surface = str(row.get('surface', 'Hard'))
            round_info = str(row.get('round', ''))
            
            # Create match result
            matches.append(MatchResultDTO(
                player1=winner_name,
                player2=loser_name,
                player1_score=winner_score_str,
                player2_score=loser_score_str,
                winner=winner_name,
                tournament=tournament_name,
                surface=surface,
                round=round_info,
                date=date_str,
                tour=tour.lower()
            ))
        
        return matches
        
    except FileNotFoundError as e:
        logger.error(f"Match data file not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Match data not available for {tour} {current_year}"
        )
    except Exception as e:
        logger.error(f"Error processing yesterday's matches: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing match data: {str(e)}"
        )


def _get_player_tour_lookup() -> Dict[str, str]:
    """Build a lookup dictionary mapping player names to their tour (ATP/WTA) from historical data."""
    player_tour = {}
    
    try:
        container = get_container()
        match_repo = container.match_data_repository()
        
        # Load ATP matches
        try:
            atp_matches = match_repo.load_matches(tour="atp")
            for _, row in atp_matches.iterrows():
                winner = row.get("winner_name", "")
                loser = row.get("loser_name", "")
                if winner:
                    player_tour[winner] = "atp"
                if loser:
                    player_tour[loser] = "atp"
        except Exception as e:
            logger.debug(f"Could not load ATP matches: {e}")
        
        # Load WTA matches
        try:
            wta_matches = match_repo.load_matches(tour="wta")
            for _, row in wta_matches.iterrows():
                winner = row.get("winner_name", "")
                loser = row.get("loser_name", "")
                if winner:
                    player_tour[winner] = "wta"
                if loser:
                    player_tour[loser] = "wta"
        except Exception as e:
            logger.debug(f"Could not load WTA matches: {e}")
                
    except Exception as e:
        logger.warning(f"Could not build player-tour lookup: {e}")
    
    return player_tour


@app.get("/api/v2/predict", response_model=PredictionDTO, tags=["Predictions"])
async def predict_match(
    player1: str = Query(..., description="Player 1 name"),
    player2: str = Query(..., description="Player 2 name"),
    surface: str = Query("hard", description="Court surface (hard, clay, grass)", pattern="^(hard|clay|grass)$")
):
    """
    Predict match outcome.
    
    Demonstrates: 
    - Single Responsibility (only prediction)
    - Dependency Inversion (uses service abstraction)
    """
    if not player1 or not player2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Both player1 and player2 are required"
        )
    
    if player1 == player2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Players must be different"
        )
    
    if surface not in ["hard", "clay", "grass"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Surface must be one of: hard, clay, grass"
        )
    
    rating_service = get_rating_service()
    prediction = rating_service.predict_match(player1, player2, surface)
    
    return PredictionDTO(
        player1=prediction.player1,
        player2=prediction.player2,
        player1_win_probability=prediction.player1_win_probability,
        player2_win_probability=prediction.player2_win_probability,
        player1_rating=prediction.player1_rating,
        player2_rating=prediction.player2_rating,
        surface=prediction.surface,
        surface_adjustment=prediction.surface_adjustment,
        favorite=prediction.favorite,
        confidence=prediction.confidence
    )


@app.get("/api/v2/value-bets", response_model=List[ValueBetDTO], tags=["Betting"])
async def get_value_bets(
    min_edge: float = Query(
        DEFAULT_MIN_EDGE,
        ge=0,
        le=100,
        description="Minimum edge percentage (probability edge)"
    ),
    regions: str = Query("uk", description="Bookmaker regions"),
    sport: str = Query(SportKey.TENNIS_ATP.value, description="Sport (tennis_atp or tennis_wta)"),
    use_cache: bool = Query(True, description="Use cached data if available")
):
    """
    Find value betting opportunities for matches in the next 24 hours.
    
    Demonstrates:
    - Open/Closed: Easy to add new betting strategies without modifying this code
    - Dependency Inversion: Depends on abstractions (IBettingService, IOddsProvider)
    """
    betting_service = get_betting_service()
    
    try:
        value_bets = betting_service.get_todays_value_bets(
            min_edge=min_edge,
            regions=regions,
            sport=sport
        )
        
        return [
            ValueBetDTO(
                match_id=vb.match_id,
                player1=vb.player1,
                player2=vb.player2,
                bet_on_player=vb.bet_on_player,
                is_player1_bet=vb.is_player1_bet,
                bookmaker=vb.bookmaker,
                odds=vb.odds,
                our_probability=vb.our_probability,
                bookmaker_probability=vb.bookmaker_probability,
                edge_percentage=vb.edge_percentage,
                expected_value_percentage=vb.expected_value_percentage,
                recommended_stake=vb.recommended_stake,
                commence_time=vb.commence_time.isoformat(),
                surface=vb.surface,
                tour=vb.tour
            )
            for vb in value_bets
        ]
    except OddsProviderError as e:
        # Tennis not available on The Odds API yet
        if "404" in str(e):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Tennis odds are not currently available on The Odds API. Please check back later."
            )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Odds provider error: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching value bets: {str(e)}"
        )


@app.get("/api/v2/cache/status", response_model=CacheStatusDTO, tags=["Cache"])
async def get_cache_status():
    """
    Get cache status.
    
    Demonstrates: Interface Segregation (ICacheStorage has focused methods)
    """
    container = get_container()
    cache = container.cache_storage()
    
    keys = cache.keys()
    details = {}
    
    for key in keys:
        details[key] = {
            "valid": cache.is_valid(key)
        }
    
    return CacheStatusDTO(
        enabled=True,
        size=len(keys),
        ttl_seconds=3600,  # Default TTL from cache implementation
        cached_keys=keys,
        cache_details=details
    )


@app.delete("/api/v2/cache/clear", tags=["Cache"])
async def clear_cache(
    key: Optional[str] = Query(None, description="Specific key to clear")
):
    """
    Clear cache entries.
    
    Demonstrates: Single Responsibility (only cache management)
    """
    container = get_container()
    cache = container.cache_storage()
    
    if key:
        cache.delete(key)
        return {"message": f"Cleared cache key: {key}"}
    else:
        cache.clear()
        return {"message": "Cleared all cache"}


@app.post("/api/v2/reset", tags=["Development"])
async def reset_dependencies():
    """
    Reset all dependencies (useful for testing).
    
    Demonstrates: Dependency Injection benefits (easy to reset/reconfigure)
    """
    reset_container()
    return {"message": "Container reset successfully", "timestamp": datetime.now().isoformat()}


# Error Handlers

@app.exception_handler(ValueError)
async def value_error_handler(request, exc):
    """Handle ValueError exceptions."""
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=str(exc)
    )


@app.exception_handler(RuntimeError)
async def runtime_error_handler(request, exc):
    """Handle RuntimeError exceptions."""
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=str(exc)
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
