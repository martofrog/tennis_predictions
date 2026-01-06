"""
Adapter Implementations (SOLID: OCP, DIP)

Adapters for external services and APIs.
Each adapter implements an interface, making them interchangeable.
"""

import os
import logging
import requests
from typing import List, Dict, Any, Optional

from src.core.interfaces import IOddsProvider, IOddsConverter
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
