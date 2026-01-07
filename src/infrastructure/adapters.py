"""
Adapter Implementations (SOLID: OCP, DIP)

Adapters for external services and APIs.
Each adapter implements an interface, making them interchangeable.
"""

import os
import logging
import requests
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from src.core.interfaces import IOddsProvider, IOddsConverter, IMatchResultsProvider
from src.core.constants import (
    ODDS_API_BASE_URL,
    DEFAULT_REQUEST_TIMEOUT,
    SportKey,
    MarketType,
    OddsFormat,
    Region
)
from src.core.exceptions import OddsProviderError, ConfigurationError

logger = logging.getLogger(__name__)


class TheOddsApiAdapter(IOddsProvider):
    """
    Adapter for The Odds API service.
    
    Open/Closed: New odds providers can be added without modifying existing code.
    Dependency Inversion: Depends on IOddsProvider interface.
    """
    
    BASE_URL = ODDS_API_BASE_URL
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize The Odds API adapter.
        
        Args:
            api_key: API key for The Odds API
            
        Raises:
            ConfigurationError: If API key is not provided
        """
        self.api_key = api_key or os.getenv("ODDS_API_KEY")
        if not self.api_key:
            raise ConfigurationError(
                "API key required. Set ODDS_API_KEY environment variable "
                "or pass api_key parameter."
            )
        self._last_usage_stats: Dict[str, Any] = {}
    
    def get_odds(
        self,
        sport: str = SportKey.TENNIS_ATP.value,
        regions: str = f"{Region.US.value},{Region.UK.value},{Region.AU.value}",
        markets: str = MarketType.H2H.value,
        odds_format: str = OddsFormat.DECIMAL.value
    ) -> List[Dict[str, Any]]:
        """
        Fetch odds for a sport.
        
        Args:
            sport: Sport key (default: tennis_atp)
            regions: Comma-separated regions
            markets: Market type (default: h2h)
            odds_format: Odds format (default: decimal)
            
        Returns:
            List of match dictionaries with odds
            
        Raises:
            OddsProviderError: If request fails
        """
        url = f"{self.BASE_URL}/sports/{sport}/odds"
        params = {
            "apiKey": self.api_key,
            "regions": regions,
            "markets": markets,
            "oddsFormat": odds_format,
            "dateFormat": "iso"
        }
        
        try:
            response = requests.get(url, params=params, timeout=DEFAULT_REQUEST_TIMEOUT)
            
            self._last_usage_stats = {
                "requests_used": response.headers.get("x-requests-used"),
                "requests_remaining": response.headers.get("x-requests-remaining"),
                "last_request": response.headers.get("date")
            }
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch odds: {e}")
            raise OddsProviderError(f"Failed to fetch odds: {e}") from e
    
    def get_available_sports(self) -> List[str]:
        """Get list of available sports."""
        url = f"{self.BASE_URL}/sports"
        params = {"apiKey": self.api_key}
        
        try:
            response = requests.get(url, params=params, timeout=DEFAULT_REQUEST_TIMEOUT)
            response.raise_for_status()
            sports = response.json()
            return [sport["key"] for sport in sports]
        except requests.exceptions.RequestException as e:
            logger.warning(f"Failed to fetch sports: {e}")
            raise OddsProviderError(f"Failed to fetch available sports: {e}") from e
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """Get API usage statistics."""
        return self._last_usage_stats.copy()


class StandardOddsConverter(IOddsConverter):
    """
    Standard implementation of odds format conversion.
    
    Single Responsibility: Converting between odds formats only.
    """
    
    def decimal_to_probability(self, odds: float) -> float:
        """Convert decimal odds to implied probability."""
        if odds <= 0:
            raise ValueError("Decimal odds must be positive")
        return 1.0 / odds
    
    def american_to_probability(self, odds: float) -> float:
        """Convert American odds to implied probability."""
        if odds == 0:
            raise ValueError("American odds cannot be zero")
        
        if odds > 0:
            return 100 / (odds + 100)
        else:
            return abs(odds) / (abs(odds) + 100)
    
    def probability_to_decimal(self, probability: float) -> float:
        """Convert probability to decimal odds."""
        if not 0 < probability < 1:
            raise ValueError("Probability must be between 0 and 1")
        return 1.0 / probability
    
    def probability_to_american(self, probability: float) -> float:
        """Convert probability to American odds."""
        if not 0 < probability < 1:
            raise ValueError("Probability must be between 0 and 1")
        
        if probability >= 0.5:
            return -100 * probability / (1 - probability)
        else:
            return 100 * (1 - probability) / probability


class MockOddsProvider(IOddsProvider):
    """
    Mock odds provider for testing.
    
    Demonstrates Liskov Substitution: Can replace real provider in tests.
    """
    
    def __init__(self, mock_data: Optional[List[Dict[str, Any]]] = None):
        """Initialize mock provider with optional test data."""
        self.mock_data = mock_data or []
        self._usage_stats = {
            "requests_used": "0",
            "requests_remaining": "999",
            "last_request": "mock"
        }
    
    def get_odds(
        self,
        sport: str = "tennis_atp",
        regions: str = "us,uk,au",
        markets: str = "h2h",
        odds_format: str = "decimal"
    ) -> List[Dict[str, Any]]:
        """Return mock odds data."""
        return self.mock_data
    
    def get_available_sports(self) -> List[str]:
        """Return mock sports list."""
        return ["tennis_atp", "tennis_wta"]
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """Return mock usage stats."""
        return self._usage_stats.copy()


class RapidApiTennisAdapter(IOddsProvider):
    """
    Adapter for RapidAPI Tennis Odds.
    
    Uses api-sports tennis odds API from RapidAPI.
    Falls back when The Odds API doesn't have tennis coverage.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize RapidAPI adapter.
        
        Args:
            api_key: RapidAPI key (from RAPID_API_KEY env var if not provided)
            
        Raises:
            ConfigurationError: If API key is not provided
        """
        self.api_key = api_key or os.getenv("RAPID_API_KEY")
        if not self.api_key:
            raise ConfigurationError(
                "RAPID_API_KEY not found in environment variables"
            )
        
        self.base_url = "https://api-tennis.p.rapidapi.com/v1"
        self.session = requests.Session()
        self.session.headers.update({
            "X-RapidAPI-Key": self.api_key,
            "X-RapidAPI-Host": "api-tennis.p.rapidapi.com"
        })
        
        self._usage_stats = {
            "requests_used": "0",
            "requests_remaining": "unknown",
            "last_request": None
        }
    
    def get_odds(
        self,
        sport: str = "tennis_atp",
        regions: str = "us,uk,au",
        markets: str = "h2h",
        odds_format: str = "decimal"
    ) -> List[Dict[str, Any]]:
        """
        Fetch tennis odds from RapidAPI.
        
        Args:
            sport: Sport key ('tennis_atp' or 'tennis_wta')
            regions: Bookmaker regions (not used in RapidAPI)
            markets: Betting markets (default h2h)
            odds_format: Odds format (default decimal)
            
        Returns:
            List of matches with odds in The Odds API format
            
        Raises:
            OddsProviderError: If request fails
        """
        try:
            # Determine league (ATP or WTA)
            league_id = 1 if "atp" in sport.lower() else 2  # 1=ATP, 2=WTA
            
            # Get upcoming matches with odds
            response = self.session.get(
                f"{self.base_url}/odds",
                params={
                    "league": league_id,
                    "timezone": "UTC"
                },
                timeout=DEFAULT_REQUEST_TIMEOUT
            )
            
            response.raise_for_status()
            data = response.json()
            
            # Update usage stats
            self._usage_stats["requests_used"] = str(int(self._usage_stats["requests_used"]) + 1)
            self._usage_stats["last_request"] = datetime.now(timezone.utc).isoformat()
            
            # Transform to The Odds API format
            return self._transform_to_odds_api_format(data, sport, odds_format)
            
        except requests.exceptions.RequestException as e:
            logger.error(f"RapidAPI request failed: {e}")
            raise OddsProviderError(f"Failed to fetch odds from RapidAPI: {e}") from e
    
    def _transform_to_odds_api_format(
        self,
        rapid_data: Dict[str, Any],
        sport_key: str,
        odds_format: str
    ) -> List[Dict[str, Any]]:
        """Transform RapidAPI response to The Odds API format."""
        matches = []
        
        results = rapid_data.get("results", [])
        
        for match_data in results:
            # Extract match info
            match_id = match_data.get("id")
            commence_time = match_data.get("date")
            
            # Get players
            home_team = match_data.get("home", {}).get("name", "Unknown")
            away_team = match_data.get("away", {}).get("name", "Unknown")
            
            # Get odds from bookmakers
            bookmakers = []
            odds_data = match_data.get("odds", {})
            
            for bookmaker_key, bookmaker_odds in odds_data.items():
                if not bookmaker_odds:
                    continue
                
                # Extract h2h odds
                home_odds = bookmaker_odds.get("home")
                away_odds = bookmaker_odds.get("away")
                
                if home_odds and away_odds:
                    # Convert to decimal if needed
                    if odds_format == "decimal":
                        if home_odds < 0:  # American odds
                            home_odds = self._american_to_decimal(home_odds)
                        if away_odds < 0:
                            away_odds = self._american_to_decimal(away_odds)
                    
                    bookmaker = {
                        "key": bookmaker_key.lower(),
                        "title": bookmaker_key.replace("_", " ").title(),
                        "last_update": commence_time,
                        "markets": [
                            {
                                "key": "h2h",
                                "last_update": commence_time,
                                "outcomes": [
                                    {
                                        "name": home_team,
                                        "price": home_odds
                                    },
                                    {
                                        "name": away_team,
                                        "price": away_odds
                                    }
                                ]
                            }
                        ]
                    }
                    bookmakers.append(bookmaker)
            
            if bookmakers:  # Only include matches with odds
                match = {
                    "id": str(match_id),
                    "sport_key": sport_key,
                    "sport_title": "Tennis ATP" if "atp" in sport_key else "Tennis WTA",
                    "commence_time": commence_time,
                    "home_team": home_team,
                    "away_team": away_team,
                    "bookmakers": bookmakers
                }
                matches.append(match)
        
        return matches
    
    def _american_to_decimal(self, american_odds: float) -> float:
        """Convert American odds to decimal."""
        if american_odds > 0:
            return (american_odds / 100) + 1
        else:
            return (100 / abs(american_odds)) + 1
    
    def get_available_sports(self) -> List[str]:
        """Return available tennis sports."""
        return ["tennis_atp", "tennis_wta"]
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """Return API usage statistics."""
        return self._usage_stats.copy()


class FallbackOddsProvider(IOddsProvider):
    """
    Fallback odds provider that tries The Odds API first, then RapidAPI.
    
    Automatically switches to RapidAPI if The Odds API doesn't have tennis.
    """
    
    def __init__(
        self,
        primary_provider: IOddsProvider,
        fallback_provider: IOddsProvider
    ):
        """
        Initialize fallback provider.
        
        Args:
            primary_provider: Primary provider (e.g., The Odds API)
            fallback_provider: Fallback provider (e.g., RapidAPI)
        """
        self.primary_provider = primary_provider
        self.fallback_provider = fallback_provider
        self._last_used_provider = "primary"
    
    def get_odds(
        self,
        sport: str = "tennis_atp",
        regions: str = "us,uk,au",
        markets: str = "h2h",
        odds_format: str = "decimal"
    ) -> List[Dict[str, Any]]:
        """
        Get odds, trying primary provider first, then fallback.
        
        Returns:
            List of matches with odds
        """
        # Try primary provider first
        try:
            logger.info(f"Attempting to fetch odds from primary provider for {sport}")
            matches = self.primary_provider.get_odds(sport, regions, markets, odds_format)
            
            if matches:
                self._last_used_provider = "primary"
                logger.info(f"✓ Primary provider returned {len(matches)} matches")
                return matches
            else:
                logger.info("Primary provider returned no matches, trying fallback...")
                
        except (OddsProviderError, Exception) as e:
            logger.warning(f"Primary provider failed: {e}, trying fallback...")
        
        # Try fallback provider
        try:
            logger.info(f"Fetching odds from fallback provider for {sport}")
            matches = self.fallback_provider.get_odds(sport, regions, markets, odds_format)
            self._last_used_provider = "fallback"
            logger.info(f"✓ Fallback provider returned {len(matches)} matches")
            return matches
            
        except Exception as e:
            logger.error(f"Fallback provider also failed: {e}")
            raise OddsProviderError(f"Both primary and fallback providers failed: {e}") from e
    
    def get_available_sports(self) -> List[str]:
        """Return combined list of available sports."""
        try:
            return self.primary_provider.get_available_sports()
        except Exception:
            return self.fallback_provider.get_available_sports()
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """Return usage stats from the last used provider."""
        if self._last_used_provider == "primary":
            return self.primary_provider.get_usage_stats()
        else:
            return self.fallback_provider.get_usage_stats()


class ApiTennisAdapter(IMatchResultsProvider):
    """
    Adapter for API-Tennis.com service.
    
    Fetches match results and transforms them to Jeff Sackmann format.
    """
    
    BASE_URL = "https://api.api-tennis.com/tennis/"
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize API-Tennis adapter.
        
        Args:
            api_key: API key for API-Tennis.com
        """
        self.api_key = api_key or os.getenv("API_TENNIS_KEY")
        if not self.api_key:
            raise ConfigurationError(
                "API_TENNIS_KEY not found in environment variables"
            )

    def get_results_by_date(self, date: datetime, tour: str) -> List[Dict[str, Any]]:
        """
        Fetch results for a specific date and tour.
        
        Args:
            date: Date to fetch results for
            tour: Tour type ('atp' or 'wta')
            
        Returns:
            List of match dictionaries in Jeff Sackmann format
        """
        date_str = date.strftime("%Y-%m-%d")
        params = {
            "method": "get_results",
            "APIkey": self.api_key,
            "date_start": date_str,
            "date_stop": date_str
        }
        
        try:
            logger.info(f"Fetching {tour.upper()} results for {date_str} from API-Tennis...")
            response = requests.get(self.BASE_URL, params=params, timeout=DEFAULT_REQUEST_TIMEOUT)
            response.raise_for_status()
            data = response.json()
            
            if "result" not in data:
                logger.warning(f"No results found in API response for {date_str}")
                return []
                
            results = data["result"]
            matches = []
            
            for res in results:
                # Filter by tour if possible
                # API-Tennis returns all matches, so we might need to filter by tournament name
                tourney_name = res.get("tournament_name", "")
                if tour.lower() == "atp" and "WTA" in tourney_name:
                    continue
                if tour.lower() == "wta" and "ATP" in tourney_name:
                    continue
                
                match = self._transform_to_sackmann_format(res, date, tour)
                if match:
                    matches.append(match)
                    
            return matches
            
        except Exception as e:
            logger.error(f"Failed to fetch results from API-Tennis: {e}")
            return []

    def _transform_to_sackmann_format(self, res: Dict[str, Any], date: datetime, tour: str) -> Optional[Dict[str, Any]]:
        """Transform API-Tennis result to Jeff Sackmann format."""
        try:
            winner_name = res.get("event_winner_team")
            home_team = res.get("event_home_team")
            away_team = res.get("event_away_team")
            
            if not winner_name or not home_team or not away_team:
                return None
                
            if winner_name == home_team:
                loser_name = away_team
            else:
                loser_name = home_team
                
            # Score parsing (API-Tennis returns "2 - 0" or similar)
            score = res.get("event_final_result", "")
            
            return {
                "tourney_id": f"API-{date.year}-{res.get('tournament_name', '')[:20].replace(' ', '')}",
                "tourney_name": res.get("tournament_name", "Unknown"),
                "surface": "Hard",  # API-Tennis often doesn't provide surface, default to Hard
                "draw_size": "",
                "tourney_level": "",
                "tourney_date": date.strftime("%Y%m%d"),
                "match_num": "",
                "winner_id": "",
                "winner_seed": "",
                "winner_entry": "",
                "winner_name": winner_name,
                "winner_hand": "",
                "winner_ht": "",
                "winner_ioc": "",
                "winner_age": "",
                "winner_rank": "",
                "winner_rank_points": "",
                "loser_id": "",
                "loser_seed": "",
                "loser_entry": "",
                "loser_name": loser_name,
                "loser_hand": "",
                "loser_ht": "",
                "loser_ioc": "",
                "loser_age": "",
                "loser_rank": "",
                "loser_rank_points": "",
                "score": score,
                "best_of": 3,
                "round": "",
                "minutes": "",
                "w_ace": "",
                "w_df": "",
                "w_svpt": "",
                "w_1stIn": "",
                "w_1stWon": "",
                "w_2ndWon": "",
                "w_SvGms": "",
                "w_bpSaved": "",
                "w_bpFaced": "",
                "l_ace": "",
                "l_df": "",
                "l_svpt": "",
                "l_1stIn": "",
                "l_1stWon": "",
                "l_2ndWon": "",
                "l_SvGms": "",
                "l_bpSaved": "",
                "l_bpFaced": "",
            }
        except Exception:
            return None
