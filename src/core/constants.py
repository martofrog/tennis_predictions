"""
Constants and Enums for Tennis Predictions (ATP & WTA)

Centralizes all magic strings, numbers, and configuration values.
Follows Python best practices by using enums and constants.
"""

from enum import Enum
from typing import Final


class OddsFormat(str, Enum):
    """Odds format enumeration."""
    DECIMAL = "decimal"
    AMERICAN = "american"


class SportKey(str, Enum):
    """Sport key enumeration."""
    TENNIS_ATP = "tennis_atp"
    TENNIS_WTA = "tennis_wta"


class MarketType(str, Enum):
    """Betting market type enumeration."""
    H2H = "h2h"
    SPREADS = "spreads"
    TOTALS = "totals"


class Region(str, Enum):
    """Bookmaker region enumeration."""
    US = "us"
    UK = "uk"
    AU = "au"
    EU = "eu"


class Surface(str, Enum):
    """Tennis court surface types."""
    HARD = "hard"
    CLAY = "clay"
    GRASS = "grass"
    CARPET = "carpet"  # Rarely used now, but historical data may include it


class Tour(str, Enum):
    """Tennis tour types."""
    ATP = "atp"
    WTA = "wta"


# Default values
DEFAULT_MIN_EDGE: Final[float] = 5.0
DEFAULT_SURFACE_ADVANTAGE: Final[float] = 50.0  # Elo points for surface specialization
DEFAULT_K_FACTOR: Final[float] = 32.0  # Higher than NBA due to individual sport
DEFAULT_CACHE_TTL_MINUTES: Final[int] = 60
DEFAULT_REGIONS: Final[str] = "uk"

# API Configuration
ODDS_API_BASE_URL: Final[str] = "https://api.the-odds-api.com/v4"
DEFAULT_REQUEST_TIMEOUT: Final[int] = 30

# File paths
DEFAULT_RATINGS_FILE: Final[str] = "data/ratings.json"
DEFAULT_DATA_DIR: Final[str] = "data"
DEFAULT_CACHE_FILE: Final[str] = "cache/cache.json"

# Date formats
DATE_FORMAT_ISO: Final[str] = "iso"
DATE_FORMAT_UNIX: Final[str] = "unix"

# Tennis Season configuration
TENNIS_SEASON_START_MONTH: Final[int] = 1  # January (though tennis is year-round)

# Match data column names (flexible parsing)
POSSIBLE_DATE_COLUMNS: Final[tuple] = ("date", "Date", "tourney_date", "match_date")
POSSIBLE_PLAYER1_COLUMNS: Final[tuple] = ("player1", "winner", "player_1", "player")
POSSIBLE_PLAYER2_COLUMNS: Final[tuple] = ("player2", "loser", "player_2", "opponent")
POSSIBLE_WINNER_COLUMNS: Final[tuple] = ("winner", "winner_name", "winner_id")
POSSIBLE_LOSER_COLUMNS: Final[tuple] = ("loser", "loser_name", "loser_id")
POSSIBLE_SURFACE_COLUMNS: Final[tuple] = ("surface", "Surface", "court_surface")
POSSIBLE_TOUR_COLUMNS: Final[tuple] = ("tour", "Tour", "circuit", "tour_type")

# Betting edge thresholds
STRONG_BET_THRESHOLD: Final[float] = 10.0
BET_THRESHOLD: Final[float] = 5.0

# Kelly Criterion
KELLY_FRACTION: Final[float] = 0.25  # Fractional Kelly (25% for safety)

# Surface-specific adjustments (multipliers for K-factor)
SURFACE_K_FACTOR_MULTIPLIERS: Final[dict] = {
    Surface.HARD.value: 1.0,
    Surface.CLAY.value: 1.0,
    Surface.GRASS.value: 1.0,
    Surface.CARPET.value: 1.0
}
