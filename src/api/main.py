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
from src.core.constants import (
    DEFAULT_MIN_EDGE,
    DEFAULT_RATINGS_FILE,
    SportKey
)
from src.core.exceptions import RepositoryError, ValidationError
from src.infrastructure.repositories import CsvMatchDataRepository

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


def update_match_data():
    """Scheduled job to update match data - downloads current year's data."""
    try:
        # Import from project root
        downloader_module_path = project_root / "download_match_data.py"
        if downloader_module_path.exists():
            import importlib.util
            import io
            import contextlib
            
            spec = importlib.util.spec_from_file_location("download_match_data", downloader_module_path)
            download_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(download_module)
            tennis_data_downloader_class = download_module.TennisDataDownloader
            
            data_dir = project_root / "data"
            downloader = tennis_data_downloader_class(data_dir=str(data_dir))
            
            # Download current year's data (updates existing file) for both tours
            from datetime import datetime
            current_year = datetime.now().year
            logger.info(f"Scheduled job: Updating match data for year {current_year}")
            
            # Suppress print statements from downloader
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                downloader.download_matches(current_year, tour="atp")
                downloader.download_matches(current_year, tour="wta")
            
            logger.info(f"Scheduled job: Match data update completed for year {current_year}")
        else:
            logger.warning("download_match_data.py not found, cannot update match data")
    except Exception as e:
        logger.error(f"Scheduled job failed to update match data: {e}")


def run_startup_update():
    """Run data download and training on application startup."""
    try:
        logger.info("="*70)
        logger.info("Starting startup data update and training...")
        logger.info("="*70)
        
        # Import here to avoid circular imports
        import subprocess
        from pathlib import Path
        from datetime import datetime
        
        project_root = Path(__file__).resolve().parent.parent.parent
        os.chdir(project_root)
        
        # Get current tennis year
        current_year = datetime.now().year
        logger.info(f"Current tennis year: {current_year}")
        
        # Determine Python executable (prefer venv/bin/python, fallback to python)
        python_cmd = "python"
        venv_python = project_root / "bin" / "python"
        if venv_python.exists():
            python_cmd = str(venv_python)
        else:
            venv_python = project_root / "venv" / "bin" / "python"
            if venv_python.exists():
                python_cmd = str(venv_python)
        
        # Step 1: Download new match data (both ATP and WTA)
        logger.info("Step 1: Downloading latest match data...")
        try:
            downloader_module_path = project_root / "download_match_data.py"
            if downloader_module_path.exists():
                import importlib.util
                import io
                import contextlib
                
                spec = importlib.util.spec_from_file_location("download_match_data", downloader_module_path)
                download_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(download_module)
                tennis_data_downloader_class = download_module.TennisDataDownloader
                
                data_dir = project_root / "data"
                downloader = tennis_data_downloader_class(data_dir=str(data_dir))
                
                # Suppress print statements from downloader during startup
                # Try downloading for current year, but don't fail if it doesn't exist yet
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    atp_result = downloader.download_matches(current_year, tour="atp")
                    wta_result = downloader.download_matches(current_year, tour="wta")
                
                # Check if downloads were successful
                atp_success = atp_result is not None
                wta_success = wta_result is not None
                
                if atp_success or wta_success:
                    success_msg = []
                    if atp_success:
                        success_msg.append(f"ATP ({len(atp_result)} matches)")
                    if wta_success:
                        success_msg.append(f"WTA ({len(wta_result)} matches)")
                    logger.info(f"✓ Match data download completed: {', '.join(success_msg)}")
                else:
                    logger.warning(f"⚠ Could not download match data for {current_year} (data may not be available yet)")
                    logger.info("Continuing with existing data...")
            else:
                logger.warning("download_match_data.py not found, skipping download")
        except Exception as e:
            logger.warning(f"⚠ Could not download match data: {e}")
            logger.info("Continuing with existing data...")
            import traceback
            logger.debug(f"Download error details: {traceback.format_exc()}")
        
        # Step 2: Update player ratings (training)
        # Process all available years to ensure ratings are loaded
        logger.info("Step 2: Updating player ratings with latest matches...")
        try:
            # First, try to update with current year only (faster)
            # If no ratings exist, this will create them
            result = subprocess.run(
                [python_cmd, "src/data/update_data.py", "--years", str(current_year)],
                check=False,  # Don't fail if this doesn't work
                capture_output=True,
                text=True,
                cwd=project_root
            )
            
            if result.returncode == 0:
                if result.stdout:
                    logger.info(result.stdout)
                logger.info("✓ Player ratings updated successfully")
            else:
                # If update failed, try processing all available years
                logger.warning("⚠ Current year update had issues, trying all available years...")
                logger.info(f"Error: {result.stderr}")
                
                # Try without year restriction to process all available data
                result = subprocess.run(
                    [python_cmd, "src/data/update_data.py"],
                    check=False,
                    capture_output=True,
                    text=True,
                    cwd=project_root
                )
                
                if result.returncode == 0:
                    if result.stdout:
                        logger.info(result.stdout)
                    logger.info("✓ Player ratings updated successfully (all years)")
                else:
                    logger.warning("⚠ Could not update ratings, but continuing with existing data...")
                    if result.stderr:
                        logger.warning(f"Error details: {result.stderr}")
        except Exception as e:
            logger.warning(f"⚠ Error updating player ratings: {e}")
            logger.info("Continuing with existing ratings (if any)...")
        
        logger.info("="*70)
        logger.info("Startup data update and training completed")
        logger.info("="*70)
    except Exception as e:
        logger.error(f"Error in startup update: {e}", exc_info=True)
        # Don't raise - allow app to start even if update fails
        logger.warning("Application will continue to start despite update errors")


def run_daily_update():
    """Run the daily update job using unified update process."""
    try:
        from src.scripts.unified_update import run_unified_update
        
        logger.info("Starting scheduled daily update...")
        results = run_unified_update(force_historical=False)
        
        if results['success']:
            # Reload ratings in container if model was updated
            if results['total_players'] > 0:
                logger.info("Reloading ratings in container...")
                reset_container()
                get_container()
                logger.info("✓ Container reloaded with updated ratings")
        else:
            logger.error("Daily update completed with errors")
            
    except Exception as e:
        logger.error(f"Error in scheduled daily update: {e}", exc_info=True)


def startup_event():
    """Startup event - run unified update and initialize scheduler."""
    logger.info("Starting Tennis Predictions API with SofaScore...")
    
    # Run unified update on startup (downloads historical if missing + last 7 days + trains model)
    try:
        logger.info("Running startup data update...")
        from src.scripts.unified_update import run_unified_update
        
        results = run_unified_update(force_historical=False)
        
        if results['success']:
            logger.info(f"✓ Startup update completed - {results['total_players']} players rated")
        else:
            logger.warning("⚠ Startup update completed with errors")
    except Exception as e:
        logger.error(f"Error during startup update: {e}", exc_info=True)
        logger.info("Continuing with existing data...")
    
    # Load ratings into container
    try:
        logger.info("Loading player ratings into container...")
        container = get_container()
        rating_system = container.rating_system()
        ratings_count = len(rating_system.get_all_ratings())
        logger.info(f"✓ Loaded {ratings_count} player ratings")
    except Exception as e:
        logger.warning(f"⚠ Could not load ratings: {e}")
    
    # Schedule daily update at 6:00 AM every day
    scheduler.add_job(
        run_daily_update,
        trigger=CronTrigger(hour=6, minute=0),
        id="daily_update",
        name="Daily Tennis Data Update",
        replace_existing=True
    )
    scheduler.start()
    logger.info("✓ API started - Daily update scheduled for 6:00 AM")
    logger.info("✓ Using unified update process (historical + SofaScore)")


def shutdown_event():
    """Shutdown event - stop scheduler."""
    scheduler.shutdown()
    logger.info("Background scheduler stopped")


# API Models (DTOs)

class PlayerRatingDTO(BaseModel):
    """Data Transfer Object for player rating."""
    player: str
    rating: float
    surface: Optional[str] = None


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
    api_key_configured: bool
    ratings_loaded: bool
    architecture: str


class CacheStatusDTO(BaseModel):
    """Cache status response."""
    cache_enabled: bool
    cached_keys: List[str]
    cache_details: Dict[str, Any]


class MatchResultDTO(BaseModel):
    """Data Transfer Object for match result."""
    date: str
    player1: str
    player2: str
    winner: str
    loser: str
    player1_score: Optional[str]
    player2_score: Optional[str]
    surface: Optional[str]
    tour: Optional[str]


# Dependency Injection Helpers

def get_rating_service() -> RatingService:
    """Get rating service instance from container."""
    container = get_container()
    return container.rating_service()


def get_betting_service() -> BettingService:
    """Get betting service instance from container."""
    container = get_container()
    return container.betting_service()


def get_match_data_repository():
    """Get match data repository instance from container."""
    container = get_container()
    return container.match_data_repository()


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
            "matches_yesterday": "/api/v2/matches/yesterday",
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


@app.get("/health", response_model=HealthResponseDTO, tags=["General"])
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
        api_key_configured=bool(api_key),
        ratings_loaded=rating_service.ratings_exist(),
        architecture="SOLID"
    )


@app.get("/api/v2/ratings", response_model=List[PlayerRatingDTO], tags=["Ratings"])
async def get_ratings(
    sort_by: str = Query("rating", pattern="^(rating|player)$"),
    player: Optional[str] = Query(None, description="Filter by specific player"),
    surface: Optional[str] = Query(None, description="Filter by surface (hard, clay, grass)"),
    tour: Optional[str] = Query(None, description="Filter by tour (atp or wta)")
):
    """
    Get player ratings.
    
    Demonstrates: Dependency Inversion (depends on IRatingSystem via service)
    """
    rating_service = get_rating_service()
    
    if player:
        player_rating = rating_service.get_player_rating(player, surface)
        return [PlayerRatingDTO(
            player=player_rating.player,
            rating=player_rating.rating,
            surface=surface
        )]
    
    all_ratings = rating_service.get_all_ratings(sort_by=sort_by, surface=surface)
    
    # Filter by tour if specified
    if tour:
        from src.data.data_loader import load_match_data
        
        # Get players from the specified tour (use recent data)
        tour_matches = load_match_data(years=[2024, 2023], tour=tour.lower())
        tour_players = set()
        
        for col in ['winner_name', 'loser_name']:
            if col in tour_matches.columns:
                tour_players.update(tour_matches[col].dropna().unique())
        
        # Filter ratings to only include players from this tour
        all_ratings = [r for r in all_ratings if r.player in tour_players]
    
    return [
        PlayerRatingDTO(player=r.player, rating=r.rating, surface=surface)
        for r in all_ratings
    ]


@app.get("/api/v2/predict", response_model=PredictionDTO, tags=["Predictions"])
async def predict_match(
    player1: str = Query(..., description="Player 1 name"),
    player2: str = Query(..., description="Player 2 name"),
    surface: str = Query("hard", description="Court surface (hard, clay, grass)")
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
        cache_enabled=True,
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


@app.get("/api/v2/matches/yesterday", response_model=List[MatchResultDTO], tags=["Matches"])
async def get_yesterday_matches(
    tour: Optional[str] = Query(None, description="Filter by tour ('atp' or 'wta')"),
    days_ago: int = Query(1, description="Number of days ago (1=yesterday, 2=day before, etc.)", ge=1, le=30)
):
    """
    Get tennis match results from the previous day using SofaScore real-time data.
    
    Demonstrates:
    - Single Responsibility: Only fetches yesterday's results
    - Dependency Inversion: Uses SofaScore adapter with fallback to repository
    
    Data source: SofaScore API (real-time) with fallback to CSV files
    """
    from datetime import timedelta
    import pandas as pd
    from src.infrastructure.sofascore_adapter import SofaScoreAdapter
    
    target_date = datetime.now() - timedelta(days=days_ago)
    logger.info(f"Fetching matches for {target_date.strftime('%Y-%m-%d')} (tour={tour})")
    
    try:
        # Try SofaScore first (real-time data)
        sofascore = SofaScoreAdapter()
        matches_df = sofascore.get_matches_by_date(target_date, tour=tour)
        
        # Fallback to CSV repository if SofaScore fails
        if matches_df.empty:
            logger.info("No matches from SofaScore, trying CSV repository...")
            match_repo = get_match_data_repository()
            matches_df = match_repo.get_matches_by_date(target_date, tour=tour)
        
        if matches_df.empty:
            logger.warning(f"No matches found for {target_date.strftime('%Y-%m-%d')} (tour={tour})")
            return []
        
        # Normalize column names
        matches_df.columns = matches_df.columns.str.lower().str.strip()
        
        results = []
        for _, row in matches_df.iterrows():
            # Extract winner and loser (SofaScore format)
            winner = None
            loser = None
            player1 = None
            player2 = None
            
            # Try different column name variations
            for col in ['winner_name', 'winner', 'player1', 'home_team']:
                if col in row.index and pd.notna(row[col]):
                    if not winner:
                        winner = str(row[col]).strip()
                    if not player1:
                        player1 = str(row[col]).strip()
                    break
            
            for col in ['loser_name', 'loser', 'player2', 'away_team']:
                if col in row.index and pd.notna(row[col]):
                    if not loser:
                        loser = str(row[col]).strip()
                    if not player2:
                        player2 = str(row[col]).strip()
                    break
            
            # Set player1/player2 if not set
            if not player1:
                player1 = winner
            if not player2:
                player2 = loser
            
            # Extract scores
            player1_score = None
            player2_score = None
            
            # SofaScore returns a single 'score' field with winner's score first (e.g., "6-4 6-3")
            if 'score' in row.index and pd.notna(row['score']):
                score_str = str(row['score']).strip()
                
                if score_str:
                    # Parse the score and create both player scores
                    # Score format: "6-4 6-3" means winner won 6-4, 6-3
                    sets = score_str.split()
                    winner_sets = []
                    loser_sets = []
                    
                    for set_score in sets:
                        if '-' in set_score:
                            parts = set_score.split('-')
                            if len(parts) == 2:
                                winner_sets.append(parts[0])
                                loser_sets.append(parts[1])
                    
                    # Build score strings
                    winner_score_str = ' '.join(winner_sets) if winner_sets else score_str
                    loser_score_str = ' '.join(loser_sets) if loser_sets else None
                    
                    # Assign to correct player
                    if winner == player1:
                        player1_score = winner_score_str
                        player2_score = loser_score_str
                    elif winner == player2:
                        player2_score = winner_score_str
                        player1_score = loser_score_str
            
            # Try separate score columns (for CSV fallback)
            if not player1_score:
                for col in ['player1_score', 'winner_score']:
                    if col in row.index and pd.notna(row[col]):
                        player1_score = str(row[col]).strip()
                        break
            
            if not player2_score:
                for col in ['player2_score', 'loser_score']:
                    if col in row.index and pd.notna(row[col]):
                        player2_score = str(row[col]).strip()
                        break
            
            # Extract surface
            surface = None
            for col in ['surface', 'court_surface']:
                if col in row.index and pd.notna(row[col]):
                    surface = str(row[col]).strip()
            
            # Extract tour
            tour_value = None
            for col in ['tour', 'tour_type']:
                if col in row.index and pd.notna(row[col]):
                    tour_value = str(row[col]).strip().lower()
            
            # Extract date
            date_str = None
            for col in ['date', 'tourney_date', 'match_date']:
                if col in row.index and pd.notna(row[col]):
                    date_val = row[col]
                    if isinstance(date_val, str):
                        date_str = date_val
                    elif hasattr(date_val, 'strftime'):
                        date_str = date_val.strftime('%Y-%m-%d')
                    break
            
            if not date_str:
                date_str = target_date.strftime('%Y-%m-%d')
            
            if not player1 or not player2 or not winner or not loser:
                continue
            
            results.append(MatchResultDTO(
                date=date_str,
                player1=player1,
                player2=player2,
                winner=winner,
                loser=loser,
                player1_score=player1_score,
                player2_score=player2_score,
                surface=surface,
                tour=tour_value
            ))
        
        return results
        
    except RepositoryError as e:
        logger.error(f"Repository error fetching yesterday's matches: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching yesterday's matches: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error fetching yesterday's matches: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching yesterday's matches: {str(e)}"
        )


@app.get("/api/v2/data-status", tags=["General"])
async def get_data_status():
    """
    Get information about available data (dates, tours, etc.)
    """
    import pandas as pd
    from pathlib import Path
    
    data_dir = project_root / "data"
    status = {
        "tours": {},
        "overall": {}
    }
    
    for tour in ["atp", "wta"]:
        tour_dir = data_dir / tour
        if tour_dir.exists():
            csv_files = list(tour_dir.glob("*.csv"))
            if csv_files:
                # Load all data for this tour
                all_dfs = []
                for f in csv_files:
                    try:
                        df = pd.read_csv(f)
                        if 'tourney_date' in df.columns:
                            df['date'] = pd.to_datetime(df['tourney_date'], format='%Y%m%d', errors='coerce')
                            all_dfs.append(df)
                    except Exception:
                        continue
                
                if all_dfs:
                    combined = pd.concat(all_dfs, ignore_index=True)
                    status["tours"][tour] = {
                        "total_matches": len(combined),
                        "earliest_date": combined['date'].min().strftime('%Y-%m-%d') if pd.notna(combined['date'].min()) else None,
                        "latest_date": combined['date'].max().strftime('%Y-%m-%d') if pd.notna(combined['date'].max()) else None,
                        "files": [f.name for f in csv_files]
                    }
    
    # Add overall status
    status["overall"]["current_date"] = datetime.now().strftime('%Y-%m-%d')
    status["overall"]["note"] = "Data source (Jeff Sackmann) typically lags behind real-time by weeks/months"
    
    return status


@app.post("/api/v2/reset", tags=["Development"])
async def reset_dependencies():
    """
    Reset all dependencies (useful for testing).
    
    Demonstrates: Dependency Injection benefits (easy to reset/reconfigure)
    """
    reset_container()
    return {"message": "Dependencies reset", "timestamp": datetime.now().isoformat()}


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
