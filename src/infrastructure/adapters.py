"""
Adapter Implementations (SOLID: OCP, DIP)

Adapters for external services and APIs.
Each adapter implements an interface, making them interchangeable.
"""

import os
import logging
import requests
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from io import BytesIO

from src.core.interfaces import IOddsProvider, IOddsConverter, IMatchResultsProvider
from src.core.constants import (
    ODDS_API_BASE_URL,
    DEFAULT_REQUEST_TIMEOUT,
    SportKey,
    MarketType,
    OddsFormat,
    Region
)
from src.core.exceptions import OddsProviderError, ConfigurationError, MatchResultsProviderError

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
        Fetch results for a specific date and tour using get_fixtures method.
        
        According to API-Tennis.com documentation, get_fixtures returns matches
        for a date range. Completed matches have event_final_result populated.
        
        Args:
            date: Date to fetch results for
            tour: Tour type ('atp' or 'wta')
            
        Returns:
            List of match dictionaries in Jeff Sackmann format
            
        Raises:
            MatchResultsProviderError: If the API request fails or returns an error
        """
        date_str = date.strftime("%Y-%m-%d")
        
        # Event type keys from API-Tennis.com documentation:
        # 265 = ATP Singles
        # 266 = WTA Singles
        event_type_key = "265" if tour.lower() == "atp" else "266"
        
        params = {
            "method": "get_fixtures",  # Use get_fixtures instead of get_results
            "APIkey": self.api_key,
            "date_start": date_str,
            "date_stop": date_str,
            "event_type_key": event_type_key  # Filter by tour type
        }
        
        try:
            logger.info(f"Fetching {tour.upper()} results for {date_str} from API-Tennis (get_fixtures)...")
            response = requests.get(self.BASE_URL, params=params, timeout=DEFAULT_REQUEST_TIMEOUT)
            
            # Check for HTTP errors
            if response.status_code != 200:
                error_msg = f"API-Tennis returned status {response.status_code}"
                if response.text:
                    error_msg += f": {response.text[:200]}"
                raise MatchResultsProviderError(error_msg)
            
            data = response.json()
            
            # Check for success field (per API-Tennis.com documentation)
            if isinstance(data, dict) and data.get("success") != 1:
                error_msg = data.get("error", "API request was not successful")
                raise MatchResultsProviderError(f"API-Tennis error: {error_msg}")
            
            # Check for API-level errors
            if isinstance(data, dict) and "error" in data and data.get("success") != 1:
                error_msg = data.get("error", "Unknown API error")
                raise MatchResultsProviderError(f"API-Tennis error: {error_msg}")
            
            if "result" not in data:
                logger.warning(f"No results found in API response for {date_str}")
                return []
                
            results = data["result"]
            matches = []
            
            for res in results:
                # Filter for completed matches only
                # get_fixtures returns both upcoming and completed matches
                # Completed matches have event_final_result populated (not "-" or empty)
                final_result = res.get("event_final_result", "")
                if final_result == "-" or not final_result or final_result.strip() == "":
                    continue  # Skip incomplete/upcoming matches
                
                # Additional check: ensure event_winner is set for completed matches
                event_winner = res.get("event_winner")
                if not event_winner:
                    continue  # Skip if no winner determined
                
                match = self._transform_to_sackmann_format(res, date, tour)
                if match:
                    matches.append(match)
                    
            return matches
            
        except MatchResultsProviderError:
            # Re-raise our custom exceptions
            raise
        except requests.exceptions.RequestException as e:
            error_msg = f"Network error connecting to API-Tennis: {e}"
            logger.error(error_msg)
            raise MatchResultsProviderError(error_msg) from e
        except Exception as e:
            error_msg = f"Unexpected error fetching results from API-Tennis: {e}"
            logger.error(error_msg)
            raise MatchResultsProviderError(error_msg) from e

    def _transform_to_sackmann_format(self, res: Dict[str, Any], date: datetime, tour: str) -> Optional[Dict[str, Any]]:
        """
        Transform API-Tennis get_fixtures result to Jeff Sackmann format.
        
        get_fixtures uses different field names:
        - event_first_player / event_second_player (instead of event_winner_team)
        - event_winner (contains winner name or "First Player"/"Second Player")
        - event_final_result (score)
        """
        try:
            # get_fixtures response structure
            first_player = res.get("event_first_player")
            second_player = res.get("event_second_player")
            event_winner = res.get("event_winner")
            
            if not first_player or not second_player:
                return None
            
            # Determine winner and loser
            # event_winner can be:
            # - Player name (string)
            # - "First Player" or "Second Player"
            # - first_player_key or second_player_key (numeric)
            winner_name = None
            loser_name = None
            
            if event_winner:
                # Check if event_winner is a player name
                if event_winner == first_player or event_winner == res.get("first_player_key"):
                    winner_name = first_player
                    loser_name = second_player
                elif event_winner == second_player or event_winner == res.get("second_player_key"):
                    winner_name = second_player
                    loser_name = first_player
                elif event_winner == "First Player" or str(event_winner) == str(res.get("first_player_key", "")):
                    winner_name = first_player
                    loser_name = second_player
                elif event_winner == "Second Player" or str(event_winner) == str(res.get("second_player_key", "")):
                    winner_name = second_player
                    loser_name = first_player
                else:
                    # event_winner might be the actual player name
                    if event_winner in [first_player, second_player]:
                        winner_name = event_winner
                        loser_name = second_player if event_winner == first_player else first_player
            
            # Fallback: if we can't determine winner, skip this match
            if not winner_name or not loser_name:
                logger.debug(f"Could not determine winner/loser from event_winner: {event_winner}")
                return None
            
            # Score parsing - use detailed set scores if available
            # scores format: [{'score_first': '4', 'score_second': '6', 'score_set': '1'}, ...]
            # score_first/second are from first_player/second_player perspective
            # We need to convert to winner/loser perspective
            scores_data = res.get("scores", [])
            if scores_data and isinstance(scores_data, list) and len(scores_data) > 0:
                # Determine if winner is first or second player
                is_first_player_winner = (winner_name == first_player)
                
                # Build score string from winner's perspective
                set_scores = []
                for set_data in sorted(scores_data, key=lambda x: int(x.get('score_set', 0))):
                    score_first = set_data.get('score_first', '0')
                    score_second = set_data.get('score_second', '0')
                    
                    if is_first_player_winner:
                        # Winner is first player: score is from first player's perspective
                        set_scores.append(f"{score_first}-{score_second}")
                    else:
                        # Winner is second player: swap to show from winner's perspective
                        set_scores.append(f"{score_second}-{score_first}")
                
                score = " ".join(set_scores) if set_scores else res.get("event_final_result", "")
            else:
                # Fallback to event_final_result if scores not available
                score = res.get("event_final_result", "")
            
            # Tournament info
            tournament_name = res.get("tournament_name", "Unknown")
            round_name = res.get("tournament_round", "")
            
            return {
                "tourney_id": f"API-{date.year}-{tournament_name[:20].replace(' ', '')}",
                "tourney_name": tournament_name,
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
                "round": round_name,
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
        except Exception as e:
            logger.debug(f"Error transforming API-Tennis result: {e}")
            return None


class TheOddsApiScoresAdapter(IMatchResultsProvider):
    """
    Adapter for The Odds API scores endpoint.
    
    Fetches completed match results from The Odds API and transforms them to Jeff Sackmann format.
    
    Note: The Odds API scores endpoint only supports data from the last 3 days.
    For older historical data, use tennis-data.co.uk or other sources.
    """
    
    BASE_URL = ODDS_API_BASE_URL
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize The Odds API scores adapter.
        
        Args:
            api_key: API key for The Odds API (from ODDS_API_KEY env var if not provided)
            
        Raises:
            ConfigurationError: If API key is not provided
        """
        self.api_key = api_key or os.getenv("ODDS_API_KEY")
        if not self.api_key:
            raise ConfigurationError(
                "ODDS_API_KEY not found in environment variables. "
                "Please set it in your .env file or environment."
            )
        self._last_usage_stats: Dict[str, Any] = {}
    
    def get_results_by_date(self, date: datetime, tour: str) -> List[Dict[str, Any]]:
        """
        Fetch completed match results for a specific date and tour.
        
        Args:
            date: Date to fetch results for
            tour: Tour type ('atp' or 'wta')
            
        Returns:
            List of match dictionaries in Jeff Sackmann format
            
        Raises:
            MatchResultsProviderError: If the API request fails, date is too old, or other errors
        """
        # Check if date is more than 3 days ago
        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        date_utc = date.replace(tzinfo=timezone.utc) if date.tzinfo is None else date
        date_utc = date_utc.replace(hour=0, minute=0, second=0, microsecond=0)
        
        days_ago = (today - date_utc).days
        
        if days_ago > 3:
            raise MatchResultsProviderError(
                f"The Odds API scores endpoint only supports data from the last 3 days. "
                f"Requested date {date.strftime('%Y-%m-%d')} is {days_ago} days ago. "
                f"For older data, please use tennis-data.co.uk or other sources."
            )
        
        if days_ago < 0:
            raise MatchResultsProviderError(
                f"Cannot fetch results for future date: {date.strftime('%Y-%m-%d')}"
            )
        
        # Map tour to sport key
        sport_key = SportKey.TENNIS_ATP.value if tour.lower() == "atp" else SportKey.TENNIS_WTA.value
        
        # Check available sports first to verify tennis keys
        try:
            # Query /sports endpoint to check available tennis sport keys
            sports_url = f"{self.BASE_URL}/sports"
            sports_params = {"apiKey": self.api_key}
            sports_response = requests.get(sports_url, params=sports_params, timeout=DEFAULT_REQUEST_TIMEOUT)
            sports_response.raise_for_status()
            available_sports = sports_response.json()
            
            # Check if requested sport key exists
            sport_keys = [s.get("key") for s in available_sports]
            if sport_key not in sport_keys:
                # Try alternative tennis keys
                alternative_keys = ["tennis", "tennis_atp_men", "tennis_wta_women", "tennis_atp", "tennis_wta"]
                found_key = None
                for alt_key in alternative_keys:
                    if alt_key in sport_keys:
                        found_key = alt_key
                        break
                
                if found_key:
                    sport_key = found_key
                    logger.info(f"Using alternative sport key: {sport_key}")
                else:
                    # Tennis is not available in The Odds API yet
                    # Return empty list gracefully instead of raising error
                    logger.debug(
                        f"Tennis ({tour.upper()}) is not currently available in The Odds API. "
                        f"No tennis sports found in available sports list. "
                        f"Tennis scores may become available during major tournaments. "
                        f"Returning empty results for {date.strftime('%Y-%m-%d')}."
                    )
                    return []
        except requests.exceptions.RequestException as e:
            logger.warning(f"Could not check available sports: {e}. Proceeding with requested sport key.")
        
        # Calculate daysFrom parameter (1-3)
        days_from = max(1, min(3, days_ago + 1))  # +1 to include the requested date
        
        url = f"{self.BASE_URL}/sports/{sport_key}/scores"
        params = {
            "apiKey": self.api_key,
            "daysFrom": days_from,
            "dateFormat": "iso"
        }
        
        try:
            logger.info(f"Fetching {tour.upper()} results for {date.strftime('%Y-%m-%d')} from The Odds API (sport={sport_key}, daysFrom={days_from})...")
            response = requests.get(url, params=params, timeout=DEFAULT_REQUEST_TIMEOUT)
            
            # Store usage stats
            self._last_usage_stats = {
                "requests_used": response.headers.get("x-requests-used"),
                "requests_remaining": response.headers.get("x-requests-remaining"),
                "last_request": response.headers.get("date")
            }
            
            response.raise_for_status()
            data = response.json()
            
            if not isinstance(data, list):
                logger.warning(f"Unexpected response format from The Odds API: {type(data)}")
                return []
            
            # Filter for completed matches on the requested date
            matches = []
            target_date_str = date.strftime("%Y-%m-%d")
            
            for match_data in data:
                # Only process completed matches
                if not match_data.get("completed", False):
                    continue
                
                # Check if match is on the requested date
                commence_time = match_data.get("commence_time")
                if commence_time:
                    try:
                        # Parse ISO 8601 datetime
                        match_datetime = datetime.fromisoformat(commence_time.replace('Z', '+00:00'))
                        match_date_str = match_datetime.strftime("%Y-%m-%d")
                        
                        # Only include matches from the requested date
                        if match_date_str != target_date_str:
                            continue
                    except (ValueError, AttributeError) as e:
                        logger.debug(f"Error parsing commence_time {commence_time}: {e}")
                        continue
                
                # Transform to Jeff Sackmann format
                transformed_match = self._transform_to_sackmann_format(match_data, date, tour)
                if transformed_match:
                    matches.append(transformed_match)
            
            logger.info(f"Found {len(matches)} completed {tour.upper()} matches for {date.strftime('%Y-%m-%d')}")
            return matches
            
        except MatchResultsProviderError:
            # Re-raise our custom exceptions
            raise
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                error_msg = "Rate limit exceeded for The Odds API. Please try again later."
            else:
                error_msg = f"The Odds API returned status {e.response.status_code}"
                if e.response.text:
                    error_msg += f": {e.response.text[:200]}"
            logger.error(error_msg)
            raise MatchResultsProviderError(error_msg) from e
        except requests.exceptions.RequestException as e:
            error_msg = f"Network error connecting to The Odds API: {e}"
            logger.error(error_msg)
            raise MatchResultsProviderError(error_msg) from e
        except Exception as e:
            error_msg = f"Unexpected error fetching results from The Odds API: {e}"
            logger.error(error_msg)
            raise MatchResultsProviderError(error_msg) from e
    
    def _transform_to_sackmann_format(
        self, 
        match_data: Dict[str, Any], 
        date: datetime, 
        tour: str
    ) -> Optional[Dict[str, Any]]:
        """
        Transform The Odds API scores response to Jeff Sackmann format.
        
        The Odds API scores format:
        {
            "id": "...",
            "sport_key": "tennis_atp",
            "commence_time": "2024-01-15T10:00:00Z",
            "completed": true,
            "home_team": "Player 1",
            "away_team": "Player 2",
            "scores": [
                {"name": "Player 1", "score": "6"},
                {"name": "Player 2", "score": "4"}
            ],
            "last_update": "..."
        }
        
        Args:
            match_data: Match data from The Odds API
            date: Date of the match
            tour: Tour type ('atp' or 'wta')
            
        Returns:
            Match dictionary in Jeff Sackmann format, or None if transformation fails
        """
        try:
            home_team = match_data.get("home_team")
            away_team = match_data.get("away_team")
            scores = match_data.get("scores", [])
            
            if not home_team or not away_team:
                logger.debug("Missing home_team or away_team in match data")
                return None
            
            if not scores or len(scores) < 2:
                logger.debug("Missing or incomplete scores in match data")
                return None
            
            # Determine winner and loser based on scores
            # Scores array contains objects with "name" and "score" fields
            # We need to parse the scores to determine who won
            winner_name = None
            loser_name = None
            
            # Parse scores to determine winner
            # The Odds API scores array contains final scores per player
            # We need to determine who won based on the scores
            player_scores = {}
            for score_entry in scores:
                player_name = score_entry.get("name")
                score_value = score_entry.get("score")
                if player_name and score_value:
                    # Try to parse score - might be a number or set score like "6-4"
                    try:
                        # If it's a simple number, it's likely a set count
                        player_scores[player_name] = int(score_value)
                    except ValueError:
                        # If it's not a number, it might be a set score string
                        # For now, we'll try to extract the first number
                        try:
                            # Extract first number from string (e.g., "6" from "6-4")
                            first_num = int(score_value.split('-')[0])
                            player_scores[player_name] = first_num
                        except (ValueError, IndexError):
                            logger.debug(f"Could not parse score value: {score_value}")
                            continue
            
            # Determine winner based on scores
            # In tennis, winner is the player with higher total score (sets won)
            if len(player_scores) >= 2:
                sorted_players = sorted(player_scores.items(), key=lambda x: x[1], reverse=True)
                winner_name = sorted_players[0][0]
                loser_name = sorted_players[1][0]
            else:
                # Fallback: use home_team as winner if we can't determine from scores
                # This is not ideal but handles edge cases
                logger.debug("Could not determine winner from scores, using home_team as winner")
                winner_name = home_team
                loser_name = away_team
            
            # Build score string
            # Try to extract set scores from the match data
            # The Odds API might provide set scores in a different format
            # For now, we'll create a simple score string from the scores we have
            score_parts = []
            if len(player_scores) >= 2:
                # Create score string from set scores
                # Format: "6-4 6-3" (winner-loser per set)
                # Since we don't have detailed set scores, we'll use a simplified format
                winner_score = player_scores.get(winner_name, 0)
                loser_score = player_scores.get(loser_name, 0)
                
                # If we have set-by-set data, use it
                # Otherwise, create a simple representation
                if winner_score > loser_score:
                    # Assume best-of-3 format for now
                    score_parts.append(f"{winner_score}-{loser_score}")
                else:
                    score_parts.append(f"{loser_score}-{winner_score}")
            
            score = " ".join(score_parts) if score_parts else ""
            
            # Extract tournament info if available
            # The Odds API might not provide tournament details in scores endpoint
            tournament_name = match_data.get("sport_title", f"{tour.upper()} Match")
            
            # Parse commence_time to get actual match date
            match_date = date
            commence_time = match_data.get("commence_time")
            if commence_time:
                try:
                    match_datetime = datetime.fromisoformat(commence_time.replace('Z', '+00:00'))
                    match_date = match_datetime
                except (ValueError, AttributeError):
                    pass
            
            return {
                "tourney_id": f"ODDS-{match_date.year}-{tournament_name[:20].replace(' ', '')}",
                "tourney_name": tournament_name,
                "surface": "Hard",  # The Odds API doesn't provide surface info, default to Hard
                "draw_size": "",
                "tourney_level": "",
                "tourney_date": match_date.strftime("%Y%m%d"),
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
                "best_of": 3,  # Default to best-of-3, might need adjustment
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
        except Exception as e:
            logger.debug(f"Error transforming The Odds API result: {e}")
            return None
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """Get API usage statistics."""
        return self._last_usage_stats.copy()


class JeffSackmannAdapter(IMatchResultsProvider):
    """
    Adapter for Jeff Sackmann's tennis data repository on GitHub.
    
    Fetches match results from GitHub CSV files and filters by date.
    Checks local files first to avoid unnecessary downloads.
    """
    
    BASE_URL_ATP = "https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master"
    BASE_URL_WTA = "https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master"
    
    def __init__(self, data_dir: Optional[str] = None):
        """
        Initialize Jeff Sackmann adapter.
        
        Args:
            data_dir: Data directory path (defaults to project_root/data)
        """
        if data_dir is None:
            # Default to project_root/data
            project_root = Path(__file__).resolve().parent.parent.parent
            self.data_dir = project_root / "data"
        else:
            self.data_dir = Path(data_dir)
        
        self.atp_dir = self.data_dir / "atp"
        self.wta_dir = self.data_dir / "wta"
        self.atp_dir.mkdir(parents=True, exist_ok=True)
        self.wta_dir.mkdir(parents=True, exist_ok=True)
    
    def get_results_by_date(self, date: datetime, tour: str) -> List[Dict[str, Any]]:
        """
        Fetch match results for a specific date and tour.
        
        Args:
            date: Date to fetch results for
            tour: Tour type ('atp' or 'wta')
            
        Returns:
            List of match dictionaries in Jeff Sackmann format
            
        Raises:
            MatchResultsProviderError: If the file cannot be downloaded or parsed
        """
        year = date.year
        tour_lower = tour.lower()
        
        if tour_lower == "atp":
            base_url = self.BASE_URL_ATP
            save_dir = self.atp_dir
        elif tour_lower == "wta":
            base_url = self.BASE_URL_WTA
            save_dir = self.wta_dir
        else:
            raise MatchResultsProviderError(f"Invalid tour: {tour}. Must be 'atp' or 'wta'")
        
        filename = f"{tour_lower}_matches_{year}.csv"
        filepath = save_dir / filename
        
        # Check if local file exists
        if not filepath.exists():
            # Download from GitHub
            url = f"{base_url}/{filename}"
            try:
                logger.info(f"Downloading {tour.upper()} {year} from Jeff Sackmann GitHub...")
                response = requests.get(url, timeout=30)
                
                if response.status_code == 404:
                    # For future years, 404 is expected - return empty instead of raising error
                    from datetime import datetime
                    current_year = datetime.now().year
                    if year > current_year:
                        logger.debug(
                            f"Jeff Sackmann data not available for {tour.upper()} {year} "
                            f"(404 Not Found) - expected for future year. URL: {url}"
                        )
                        return []
                    else:
                        raise MatchResultsProviderError(
                            f"Jeff Sackmann data not available for {tour.upper()} {year} "
                            f"(404 Not Found). URL: {url}"
                        )
                
                response.raise_for_status()
                
                # Save to local file
                filepath.parent.mkdir(parents=True, exist_ok=True)
                with open(filepath, 'wb') as f:
                    f.write(response.content)
                
                logger.info(f"Downloaded {filename} ({len(response.content)} bytes)")
            except requests.exceptions.RequestException as e:
                raise MatchResultsProviderError(
                    f"Failed to download {tour.upper()} {year} from Jeff Sackmann: {e}"
                ) from e
        
        # Load CSV file
        try:
            df = pd.read_csv(filepath)
            
            if df.empty:
                logger.debug(f"CSV file {filename} is empty")
                return []
            
            # Ensure tourney_date column exists
            if 'tourney_date' not in df.columns:
                raise MatchResultsProviderError(
                    f"CSV file {filename} missing required column 'tourney_date'"
                )
            
            # Convert tourney_date to string for comparison (format: YYYYMMDD)
            df['tourney_date'] = df['tourney_date'].astype(str)
            target_date_str = date.strftime("%Y%m%d")
            
            # Filter by date
            matches_df = df[df['tourney_date'] == target_date_str]
            
            if matches_df.empty:
                logger.debug(f"No matches found for {tour.upper()} on {date.strftime('%Y-%m-%d')}")
                return []
            
            # Convert DataFrame to list of dictionaries
            matches = matches_df.to_dict('records')
            
            logger.info(f"Found {len(matches)} {tour.upper()} matches for {date.strftime('%Y-%m-%d')} from Jeff Sackmann")
            return matches
            
        except pd.errors.EmptyDataError:
            raise MatchResultsProviderError(f"CSV file {filename} is empty or invalid")
        except Exception as e:
            raise MatchResultsProviderError(
                f"Error reading or parsing CSV file {filename}: {e}"
            ) from e


class TennisDataCoUkAdapter(IMatchResultsProvider):
    """
    Adapter for tennis-data.co.uk.
    
    Fetches match results from tennis-data.co.uk Excel files and filters by date.
    Checks local CSV files first to avoid unnecessary downloads.
    Converts Excel format to Jeff Sackmann format.
    """
    
    BASE_URL = "http://www.tennis-data.co.uk"
    
    def __init__(self, data_dir: Optional[str] = None):
        """
        Initialize tennis-data.co.uk adapter.
        
        Args:
            data_dir: Data directory path (defaults to project_root/data)
        """
        if data_dir is None:
            # Default to project_root/data
            project_root = Path(__file__).resolve().parent.parent.parent
            self.data_dir = project_root / "data"
        else:
            self.data_dir = Path(data_dir)
        
        self.atp_dir = self.data_dir / "atp"
        self.wta_dir = self.data_dir / "wta"
        self.atp_dir.mkdir(parents=True, exist_ok=True)
        self.wta_dir.mkdir(parents=True, exist_ok=True)
    
    def get_results_by_date(self, date: datetime, tour: str) -> List[Dict[str, Any]]:
        """
        Fetch match results for a specific date and tour.
        
        Args:
            date: Date to fetch results for
            tour: Tour type ('atp' or 'wta')
            
        Returns:
            List of match dictionaries in Jeff Sackmann format
            
        Raises:
            MatchResultsProviderError: If the file cannot be downloaded or parsed
        """
        year = date.year
        tour_lower = tour.lower()
        
        if tour_lower == "atp":
            url = f"{self.BASE_URL}/{year}/{year}.xlsx"
            save_dir = self.atp_dir
        elif tour_lower == "wta":
            url = f"{self.BASE_URL}/{year}w/{year}.xlsx"
            save_dir = self.wta_dir
        else:
            raise MatchResultsProviderError(f"Invalid tour: {tour}. Must be 'atp' or 'wta'")
        
        filename = f"{tour_lower}_matches_{year}.csv"
        csv_filepath = save_dir / filename
        
        # Check if local CSV file exists
        if not csv_filepath.exists():
            # Download Excel from tennis-data.co.uk
            try:
                logger.info(f"Downloading {tour.upper()} {year} from tennis-data.co.uk...")
                response = requests.get(url, timeout=30)
                
                if response.status_code == 404:
                    raise MatchResultsProviderError(
                        f"tennis-data.co.uk data not available for {tour.upper()} {year} "
                        f"(404 Not Found). URL: {url}"
                    )
                
                response.raise_for_status()
                
                # Check if file is too small (likely empty/invalid)
                # For future years (e.g., 2026), this is expected - don't raise error, just return empty
                if len(response.content) < 5000:
                    from datetime import datetime
                    current_year = datetime.now().year
                    if year > current_year:
                        # Future year - expected to have no data
                        logger.debug(
                            f"tennis-data.co.uk file for {tour.upper()} {year} is too small "
                            f"({len(response.content)} bytes) - likely no data available yet for future year"
                        )
                        return []
                    else:
                        raise MatchResultsProviderError(
                            f"Downloaded file from tennis-data.co.uk is too small "
                            f"({len(response.content)} bytes) - likely no data for {year}"
                        )
                
                # Parse Excel file
                try:
                    df_raw = pd.read_excel(BytesIO(response.content))
                except Exception as e:
                    raise MatchResultsProviderError(
                        f"Error parsing Excel file from tennis-data.co.uk: {e}"
                    ) from e
                
                # Convert to Jeff Sackmann format
                df = self._convert_to_sackmann_format(df_raw, year, tour_lower)
                
                if df.empty:
                    raise MatchResultsProviderError(
                        f"No valid match data found in tennis-data.co.uk file for {tour.upper()} {year}"
                    )
                
                # Save as CSV for future use
                csv_filepath.parent.mkdir(parents=True, exist_ok=True)
                df.to_csv(csv_filepath, index=False)
                
                logger.info(f"Downloaded and converted {filename} ({len(df)} matches)")
                
            except requests.exceptions.RequestException as e:
                raise MatchResultsProviderError(
                    f"Failed to download {tour.upper()} {year} from tennis-data.co.uk: {e}"
                ) from e
        
        # Load CSV file
        try:
            # Check if file exists and is not too small (might be from a previous failed download)
            if csv_filepath.exists() and csv_filepath.stat().st_size < 5000:
                from datetime import datetime
                current_year = datetime.now().year
                if year > current_year:
                    # Future year - expected to have no data
                    logger.debug(f"CSV file {filename} is too small ({csv_filepath.stat().st_size} bytes) - likely no data available yet for future year")
                    return []
            
            df = pd.read_csv(csv_filepath)
            
            if df.empty:
                logger.debug(f"CSV file {filename} is empty")
                return []
            
            # Ensure tourney_date column exists
            if 'tourney_date' not in df.columns:
                raise MatchResultsProviderError(
                    f"CSV file {filename} missing required column 'tourney_date'"
                )
            
            # Convert tourney_date to string for comparison (format: YYYYMMDD)
            df['tourney_date'] = df['tourney_date'].astype(str)
            target_date_str = date.strftime("%Y%m%d")
            
            # Filter by date
            matches_df = df[df['tourney_date'] == target_date_str]
            
            if matches_df.empty:
                logger.debug(f"No matches found for {tour.upper()} on {date.strftime('%Y-%m-%d')}")
                return []
            
            # Convert DataFrame to list of dictionaries
            matches = matches_df.to_dict('records')
            
            logger.info(f"Found {len(matches)} {tour.upper()} matches for {date.strftime('%Y-%m-%d')} from tennis-data.co.uk")
            return matches
            
        except pd.errors.EmptyDataError:
            raise MatchResultsProviderError(f"CSV file {filename} is empty or invalid")
        except Exception as e:
            raise MatchResultsProviderError(
                f"Error reading or parsing CSV file {filename}: {e}"
            ) from e
    
    def _convert_to_sackmann_format(
        self, 
        df: pd.DataFrame, 
        year: int,
        tour: str
    ) -> pd.DataFrame:
        """
        Convert tennis-data.co.uk format to Jeff Sackmann format.
        
        Reuses logic from TennisDataCoUkFetcher._convert_to_sackmann_format.
        
        Args:
            df: DataFrame from tennis-data.co.uk
            year: Year of the data
            tour: 'atp' or 'wta'
            
        Returns:
            DataFrame in Jeff Sackmann format
        """
        matches = []
        
        for _, row in df.iterrows():
            try:
                # Extract basic info
                winner_name = str(row.get('Winner', '')).strip()
                loser_name = str(row.get('Loser', '')).strip()
                
                # Skip if no player names
                if not winner_name or not loser_name or winner_name == 'nan' or loser_name == 'nan':
                    continue
                
                # Parse date
                date_val = row.get('Date')
                if pd.notna(date_val):
                    if isinstance(date_val, str):
                        try:
                            date_obj = datetime.strptime(date_val, '%Y-%m-%d')
                        except:
                            try:
                                date_obj = datetime.strptime(date_val, '%d/%m/%Y')
                            except:
                                date_obj = pd.to_datetime(date_val)
                    else:
                        date_obj = pd.to_datetime(date_val)
                    tourney_date = date_obj.strftime('%Y%m%d')
                else:
                    tourney_date = f"{year}0101"  # Default to Jan 1 if no date
                
                # Build set score
                sets = []
                for i in range(1, 6):  # Up to 5 sets
                    w_set = row.get(f'W{i}')
                    l_set = row.get(f'L{i}')
                    if pd.notna(w_set) and pd.notna(l_set):
                        sets.append(f"{int(w_set)}-{int(l_set)}")
                
                score = " ".join(sets) if sets else ""
                
                # Build match record in Jeff Sackmann format
                match_data = {
                    "tourney_id": f"TD-{year}-{str(row.get('Tournament', ''))[:20].replace(' ', '')}",
                    "tourney_name": str(row.get('Tournament', '')),
                    "surface": str(row.get('Surface', 'Hard')),
                    "draw_size": "",
                    "tourney_level": str(row.get('Series', '')),
                    "tourney_date": tourney_date,
                    "match_num": "",
                    "winner_id": "",
                    "winner_seed": "",
                    "winner_entry": "",
                    "winner_name": winner_name,
                    "winner_hand": "",
                    "winner_ht": "",
                    "winner_ioc": "",
                    "winner_age": "",
                    "winner_rank": int(row['WRank']) if pd.notna(row.get('WRank')) else "",
                    "winner_rank_points": int(row['WPts']) if pd.notna(row.get('WPts')) else "",
                    "loser_id": "",
                    "loser_seed": "",
                    "loser_entry": "",
                    "loser_name": loser_name,
                    "loser_hand": "",
                    "loser_ht": "",
                    "loser_ioc": "",
                    "loser_age": "",
                    "loser_rank": int(row['LRank']) if pd.notna(row.get('LRank')) else "",
                    "loser_rank_points": int(row['LPts']) if pd.notna(row.get('LPts')) else "",
                    "score": score,
                    "best_of": int(row['Best of']) if pd.notna(row.get('Best of')) else 3,
                    "round": str(row.get('Round', '')),
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
                
                matches.append(match_data)
                
            except (ValueError, KeyError, TypeError) as e:
                logger.debug(f"Error converting row: {e}")
                continue
        
        if not matches:
            return pd.DataFrame()
        
        return pd.DataFrame(matches)


class FallbackMatchResultsProvider(IMatchResultsProvider):
    """
    Fallback match results provider that tries multiple providers in sequence.
    
    Automatically switches to fallback providers if the primary fails.
    """
    
    def __init__(
        self,
        primary_provider: IMatchResultsProvider,
        fallback_providers: Optional[List[IMatchResultsProvider]] = None
    ):
        """
        Initialize fallback provider.
        
        Args:
            primary_provider: Primary provider (e.g., ApiTennisAdapter)
            fallback_providers: List of fallback providers to try in order
        """
        self.primary_provider = primary_provider
        self.fallback_providers = fallback_providers or []
        self._last_used_provider = "primary"
        self._provider_errors = []
    
    def get_results_by_date(self, date: datetime, tour: str) -> List[Dict[str, Any]]:
        """
        Get match results, trying providers in order until one succeeds.
        
        Args:
            date: Date to fetch results for
            tour: Tour type ('atp' or 'wta')
            
        Returns:
            List of match dictionaries in Jeff Sackmann format
            
        Raises:
            MatchResultsProviderError: If all providers fail
        """
        self._provider_errors = []
        
        # Try primary provider first
        try:
            logger.debug(f"Attempting to fetch {tour.upper()} results for {date.strftime('%Y-%m-%d')} from primary provider...")
            matches = self.primary_provider.get_results_by_date(date, tour)
            
            if matches:
                self._last_used_provider = "primary"
                logger.info(f"✓ Primary provider returned {len(matches)} matches")
                return matches
            else:
                logger.debug("Primary provider returned no matches, trying fallbacks...")
                self._provider_errors.append("Primary provider returned empty results")
                
        except MatchResultsProviderError as e:
            logger.debug(f"Primary provider failed: {e}")
            self._provider_errors.append(f"Primary: {str(e)}")
        except Exception as e:
            logger.debug(f"Primary provider error: {e}")
            self._provider_errors.append(f"Primary: {str(e)}")
        
        # Try fallback providers in order
        for i, fallback in enumerate(self.fallback_providers):
            try:
                logger.debug(f"Trying fallback provider {i+1}/{len(self.fallback_providers)}...")
                matches = fallback.get_results_by_date(date, tour)
                
                if matches:
                    self._last_used_provider = f"fallback_{i+1}"
                    logger.info(f"✓ Fallback provider {i+1} returned {len(matches)} matches")
                    return matches
                else:
                    logger.debug(f"Fallback provider {i+1} returned no matches")
                    self._provider_errors.append(f"Fallback {i+1}: returned empty results")
                    
            except MatchResultsProviderError as e:
                logger.debug(f"Fallback provider {i+1} failed: {e}")
                self._provider_errors.append(f"Fallback {i+1}: {str(e)}")
            except Exception as e:
                logger.debug(f"Fallback provider {i+1} error: {e}")
                self._provider_errors.append(f"Fallback {i+1}: {str(e)}")
        
        # All providers failed - check if this is a future date (expected) or actual error
        from datetime import datetime
        current_year = datetime.now().year
        is_future_date = date.year > current_year or (date.year == current_year and date > datetime.now())
        
        # Filter out expected errors for future dates
        actual_errors = []
        for err in self._provider_errors:
            # Skip "returned empty results" - these are expected
            if "returned empty results" in err:
                continue
            # For future dates, skip 404 errors and "too small" errors - these are expected
            if is_future_date and ("404" in err or "too small" in err or "not available" in err.lower()):
                continue
            actual_errors.append(err)
        
        if actual_errors:
            error_summary = "; ".join(actual_errors)
            error_msg = f"All match results providers failed. Errors: {error_summary}"
            logger.warning(error_msg)
            raise MatchResultsProviderError(error_msg)
        else:
            # All providers returned empty results or expected failures (no data available) - this is expected for future dates
            if is_future_date:
                logger.debug(f"No match results available for {tour.upper()} {date.strftime('%Y-%m-%d')} (future date)")
            else:
                logger.debug(f"No match results available for {tour.upper()} {date.strftime('%Y-%m-%d')} from any provider")
            return []
    
    def get_last_used_provider(self) -> str:
        """Return the name of the last successfully used provider."""
        return self._last_used_provider
    
    def get_provider_errors(self) -> List[str]:
        """Return list of errors from all attempted providers."""
        return self._provider_errors.copy()
