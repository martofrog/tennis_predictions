"""
Odds Fetcher for Tennis Matches

Fetches live odds from The Odds API for tennis matches.
"""

import os
import logging
from typing import List, Dict, Any, Optional

from src.infrastructure.adapters import TheOddsApiAdapter
from src.core.constants import SportKey, MarketType, OddsFormat, Region
from src.core.exceptions import OddsProviderError, ConfigurationError

logger = logging.getLogger(__name__)


def fetch_tennis_odds(
    sport: str = SportKey.TENNIS_ATP.value,
    regions: str = f"{Region.US.value},{Region.UK.value}",
    markets: str = MarketType.H2H.value
) -> List[Dict[str, Any]]:
    """
    Fetch tennis odds from The Odds API.
    
    Args:
        sport: Sport key ('tennis_atp' or 'tennis_wta')
        regions: Comma-separated regions
        markets: Market type (default: h2h)
        
    Returns:
        List of match dictionaries with odds
        
    Raises:
        OddsProviderError: If odds cannot be fetched
        ConfigurationError: If API key is not configured
    """
    api_key = os.getenv("ODDS_API_KEY")
    if not api_key:
        raise ConfigurationError(
            "ODDS_API_KEY environment variable not set. "
            "Please set it in your .env file or environment."
        )
    
    adapter = TheOddsApiAdapter(api_key)
    
    try:
        odds = adapter.get_odds(
            sport=sport,
            regions=regions,
            markets=markets,
            odds_format=OddsFormat.DECIMAL.value
        )
        return odds
    except Exception as e:
        logger.error(f"Failed to fetch odds: {e}")
        raise OddsProviderError(f"Failed to fetch odds: {e}") from e
