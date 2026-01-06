"""
Betting Service - Business logic for value betting (SOLID: SRP, DIP)

Coordinates between rating system, odds provider, and betting calculations.
Adapted for tennis matches.
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone, timedelta

from src.core.interfaces import (
    IRatingSystem,
    IOddsProvider,
    IOddsConverter,
    ICacheStorage
)
from src.core.domain_models import ValueBet, BettingEdge
from src.core.constants import (
    DEFAULT_MIN_EDGE,
    DEFAULT_REGIONS,
    DEFAULT_CACHE_TTL_MINUTES,
    SportKey,
    MarketType,
    OddsFormat
)
from src.core.exceptions import OddsProviderError, ValidationError


class BettingService:
    """
    Service for finding and analyzing value bets.
    
    Single Responsibility: Value betting analysis.
    Dependency Inversion: Depends on interfaces.
    """
    
    def __init__(
        self,
        rating_system: IRatingSystem,
        odds_provider: IOddsProvider,
        odds_converter: IOddsConverter,
        cache_storage: Optional[ICacheStorage] = None
    ):
        """
        Initialize betting service with dependency injection.
        
        Args:
            rating_system: Rating system for predictions
            odds_provider: Provider for odds data
            odds_converter: Converter for odds formats
            cache_storage: Optional cache storage
        """
        self.rating_system = rating_system
        self.odds_provider = odds_provider
        self.odds_converter = odds_converter
        self.cache_storage = cache_storage
    
    def calculate_betting_edge(
        self,
        player1: str,
        player2: str,
        player1_odds: float,
        player2_odds: float,
        surface: str = "hard",
        odds_format: str = OddsFormat.DECIMAL.value
    ) -> Dict[str, BettingEdge]:
        """
        Calculate betting edge for both players.
        
        Args:
            player1: Player 1 name
            player2: Player 2 name
            player1_odds: Odds for player 1
            player2_odds: Odds for player 2
            surface: Court surface ('hard', 'clay', 'grass')
            odds_format: Format of odds (OddsFormat.DECIMAL or OddsFormat.AMERICAN)
            
        Returns:
            Dictionary with 'player1' and 'player2' BettingEdge objects
        """
        # Get our predictions
        player1_prob, player2_prob = self.rating_system.predict_match(
            player1, player2, surface
        )
        
        # Convert odds to probabilities
        if odds_format == OddsFormat.DECIMAL.value:
            player1_implied_prob = self.odds_converter.decimal_to_probability(player1_odds)
            player2_implied_prob = self.odds_converter.decimal_to_probability(player2_odds)
        else:
            player1_implied_prob = self.odds_converter.american_to_probability(player1_odds)
            player2_implied_prob = self.odds_converter.american_to_probability(player2_odds)
        
        # Calculate edges
        player1_edge = BettingEdge.from_probabilities(
            player=player1,
            our_prob=player1_prob,
            bookie_prob=player1_implied_prob,
            odds=player1_odds
        )
        
        player2_edge = BettingEdge.from_probabilities(
            player=player2,
            our_prob=player2_prob,
            bookie_prob=player2_implied_prob,
            odds=player2_odds
        )
        
        return {
            "player1": player1_edge,
            "player2": player2_edge
        }
    
    def find_value_bets(
        self,
        min_edge: float = DEFAULT_MIN_EDGE,
        regions: str = DEFAULT_REGIONS,
        sport: str = SportKey.TENNIS_ATP.value,
        use_cache: bool = True
    ) -> List[ValueBet]:
        """
        Find value bets from current odds.
        
        Filters bets by edge percentage (probability edge) >= min_edge.
        Only returns bets that meet the minimum edge threshold.
        
        Args:
            min_edge: Minimum edge percentage (probability edge) to consider
            regions: Bookmaker regions
            sport: Sport key ('tennis_atp' or 'tennis_wta')
            use_cache: Whether to use cached data
            
        Returns:
            List of ValueBet objects with edge_percentage >= min_edge
            
        Raises:
            OddsProviderError: If odds cannot be fetched
            ValidationError: If invalid parameters provided
        """
        if min_edge < 0:
            raise ValidationError("min_edge must be non-negative")
        
        cache_key = f"value_bets_{sport}_{regions}_{min_edge}"
        
        # Check cache first
        cached_bets = self._get_cached_value_bets(cache_key) if use_cache else None
        if cached_bets is not None:
            return cached_bets
        
        # Fetch odds
        try:
            matches = self.odds_provider.get_odds(
                sport=sport,
                regions=regions,
                markets=MarketType.H2H.value,
                odds_format=OddsFormat.DECIMAL.value
            )
        except Exception as e:
            raise OddsProviderError(f"Failed to fetch odds: {e}") from e
        
        value_bets = self._process_matches_for_value_bets(matches, min_edge, sport)
        
        # Cache results
        self._cache_value_bets(cache_key, value_bets)
        
        return value_bets
    
    def _get_cached_value_bets(self, cache_key: str) -> Optional[List[ValueBet]]:
        """Get value bets from cache if available."""
        if not self.cache_storage:
            return None
        
        cached = self.cache_storage.get(cache_key)
        if not cached:
            return None
        
        # Convert commence_time from string back to datetime
        value_bets = []
        for vb in cached:
            vb_dict = dict(vb) if isinstance(vb, dict) else vb.__dict__
            vb_dict["commence_time"] = datetime.fromisoformat(vb_dict["commence_time"])
            value_bets.append(ValueBet(**vb_dict))
        
        return value_bets
    
    def _process_matches_for_value_bets(
        self,
        matches: List[Dict[str, Any]],
        min_edge: float,
        sport: str
    ) -> List[ValueBet]:
        """Process matches and extract value bets."""
        value_bets = []
        
        for match in matches:
            match_bets = self._extract_value_bets_from_match(match, min_edge, sport)
            value_bets.extend(match_bets)
        
        return value_bets
    
    def _extract_value_bets_from_match(
        self,
        match: Dict[str, Any],
        min_edge: float,
        sport: str
    ) -> List[ValueBet]:
        """Extract value bets from a single match."""
        # Extract player names from match data
        # The Odds API uses 'home_team' and 'away_team' for tennis matches
        player1 = match.get("home_team") or match.get("player1")
        player2 = match.get("away_team") or match.get("player2")
        
        if not player1 or not player2:
            return []
        
        # Extract surface from match data (if available)
        surface = match.get("surface", "hard")
        
        value_bets = []
        
        for bookmaker in match.get("bookmakers", []):
            bookmaker_bets = self._process_bookmaker(
                bookmaker, player1, player2, match, min_edge, surface, sport
            )
            value_bets.extend(bookmaker_bets)
        
        return value_bets
    
    def _process_bookmaker(
        self,
        bookmaker: Dict[str, Any],
        player1: str,
        player2: str,
        match: Dict[str, Any],
        min_edge: float,
        surface: str,
        sport: str
    ) -> List[ValueBet]:
        """Process a single bookmaker's markets."""
        value_bets = []
        
        for market in bookmaker.get("markets", []):
            if market.get("key") != MarketType.H2H.value:
                continue
            
            odds = self._extract_odds_from_market(market, player1, player2)
            if not odds:
                continue
            
            player1_odds, player2_odds = odds
            bets = self._calculate_and_filter_value_bets(
                player1, player2, player1_odds, player2_odds,
                match, bookmaker, min_edge, surface, sport
            )
            value_bets.extend(bets)
        
        return value_bets
    
    def _extract_odds_from_market(
        self,
        market: Dict[str, Any],
        player1: str,
        player2: str
    ) -> Optional[Tuple[float, float]]:
        """Extract odds for both players from market outcomes."""
        outcomes = market.get("outcomes", [])
        if len(outcomes) < 2:
            return None
        
        player1_odds = None
        player2_odds = None
        
        for outcome in outcomes:
            name = outcome.get("name")
            price = outcome.get("price")
            
            if name == player1 or name == player1.split()[-1]:  # Try full name or last name
                player1_odds = price
            elif name == player2 or name == player2.split()[-1]:
                player2_odds = price
        
        if player1_odds is None or player2_odds is None:
            return None
        
        return player1_odds, player2_odds
    
    def _calculate_and_filter_value_bets(
        self,
        player1: str,
        player2: str,
        player1_odds: float,
        player2_odds: float,
        match: Dict[str, Any],
        bookmaker: Dict[str, Any],
        min_edge: float,
        surface: str,
        sport: str
    ) -> List[ValueBet]:
        """Calculate edges and create value bet objects."""
        edges = self.calculate_betting_edge(
            player1, player2, player1_odds, player2_odds, surface, OddsFormat.DECIMAL.value
        )
        
        commence_time = self._parse_commence_time(match.get("commence_time", ""))
        tour = "atp" if "atp" in sport.lower() else "wta"
        value_bets = []
        
        for player_type, edge in edges.items():
            if edge.probability_edge >= min_edge:
                is_player1 = (player_type == "player1")
                value_bet = self._create_value_bet(
                    match, bookmaker, player1, player2,
                    player1_odds, player2_odds, edge, edges, is_player1, commence_time, surface, tour
                )
                value_bets.append(value_bet)
        
        return value_bets
    
    def _create_value_bet(
        self,
        match: Dict[str, Any],
        bookmaker: Dict[str, Any],
        player1: str,
        player2: str,
        player1_odds: float,
        player2_odds: float,
        edge: BettingEdge,
        edges: Dict[str, BettingEdge],
        is_player1: bool,
        commence_time: datetime,
        surface: str,
        tour: str
    ) -> ValueBet:
        """Create a ValueBet object from calculated edge."""
        selected_odds = player1_odds if is_player1 else player2_odds
        selected_edge = edges["player1" if is_player1 else "player2"]
        
        our_probability = (
            selected_edge.probability_edge / 100 +
            self.odds_converter.decimal_to_probability(selected_odds)
        )
        bookmaker_probability = self.odds_converter.decimal_to_probability(selected_odds)
        
        return ValueBet(
            match_id=match.get("id", ""),
            player1=player1,
            player2=player2,
            bet_on_player=edge.player,
            is_player1_bet=is_player1,
            bookmaker=bookmaker.get("title", ""),
            odds=selected_odds,
            odds_format=OddsFormat.DECIMAL.value,
            our_probability=our_probability,
            bookmaker_probability=bookmaker_probability,
            edge_percentage=edge.probability_edge,
            expected_value_percentage=edge.expected_value,
            commence_time=commence_time,
            surface=surface,
            tour=tour
        )
    
    def _parse_commence_time(self, commence_time_str: str) -> datetime:
        """Parse commence time string to datetime."""
        try:
            return datetime.fromisoformat(commence_time_str.replace("Z", "+00:00"))
        except ValueError as e:
            raise ValidationError(f"Invalid commence_time format: {commence_time_str}") from e
    
    def _cache_value_bets(self, cache_key: str, value_bets: List[ValueBet]) -> None:
        """Cache value bets results."""
        if not self.cache_storage:
            return
        
        cache_data = [
            {**vb.__dict__, "commence_time": vb.commence_time.isoformat()}
            for vb in value_bets
        ]
        self.cache_storage.set(cache_key, cache_data, ttl_minutes=DEFAULT_CACHE_TTL_MINUTES)
    
    def get_todays_value_bets(
        self,
        min_edge: float = DEFAULT_MIN_EDGE,
        regions: str = DEFAULT_REGIONS,
        sport: str = SportKey.TENNIS_ATP.value
    ) -> List[ValueBet]:
        """
        Get value bets for matches in the next 24 hours.
        
        Returns only the BEST value bet per match (highest EV across all bookmakers).
        
        Args:
            min_edge: Minimum edge percentage
            regions: Bookmaker regions
            sport: Sport key ('tennis_atp' or 'tennis_wta')
            
        Returns:
            List of ValueBet objects for next 24 hours (one per match)
        """
        all_value_bets = self.find_value_bets(min_edge, regions, sport)
        
        now = datetime.now(timezone.utc)
        next_24h = now + timedelta(hours=24)
        
        # Filter for matches in the next 24 hours (upcoming matches only)
        next_24h_bets = [
            vb for vb in all_value_bets
            if now <= vb.commence_time <= next_24h
        ]
        
        # Group by match and keep only the best bet per match
        return self._select_best_bet_per_match(next_24h_bets)
    
    def _select_best_bet_per_match(self, bets: List[ValueBet]) -> List[ValueBet]:
        """Select the best value bet (highest EV) for each match."""
        best_bets_by_match: Dict[str, ValueBet] = {}
        
        for bet in bets:
            match_key = f"{bet.player1}_{bet.player2}"
            
            if match_key not in best_bets_by_match:
                best_bets_by_match[match_key] = bet
            else:
                # Keep the bet with higher expected value
                current_best = best_bets_by_match[match_key]
                if bet.expected_value_percentage > current_best.expected_value_percentage:
                    best_bets_by_match[match_key] = bet
        
        return list(best_bets_by_match.values())
