"""
Domain Models - Pure business entities (SOLID: SRP)

These models represent core business concepts without infrastructure concerns.
They follow Single Responsibility Principle.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from src.core.constants import KELLY_FRACTION, OddsFormat, Surface


@dataclass
class PlayerRating:
    """Represents a player's rating at a point in time."""
    player: str
    rating: float
    matches_played: int = 0
    last_updated: Optional[datetime] = None
    surface_ratings: Optional[dict] = None  # Surface-specific ratings
    
    def __post_init__(self):
        if self.last_updated is None:
            self.last_updated = datetime.now()
        if self.surface_ratings is None:
            self.surface_ratings = {}


@dataclass
class MatchPrediction:
    """Represents a prediction for a tennis match."""
    player1: str
    player2: str
    player1_win_probability: float
    player2_win_probability: float
    player1_rating: float
    player2_rating: float
    surface: str
    surface_adjustment: float
    predicted_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.predicted_at is None:
            self.predicted_at = datetime.now()
    
    @property
    def favorite(self) -> str:
        """Get the favored player."""
        return self.player1 if self.player1_win_probability > self.player2_win_probability else self.player2
    
    @property
    def confidence(self) -> float:
        """Get prediction confidence (distance from 50/50)."""
        return abs(self.player1_win_probability - 0.5)


@dataclass
class BookmakerOdds:
    """Represents odds from a single bookmaker."""
    bookmaker: str
    player1_odds: float
    player2_odds: float
    odds_format: str  # 'decimal' or 'american'
    last_updated: Optional[datetime] = None
    
    def __post_init__(self):
        if self.last_updated is None:
            self.last_updated = datetime.now()


@dataclass
class ValueBet:
    """Represents a value betting opportunity."""
    match_id: str
    player1: str
    player2: str
    bet_on_player: str
    is_player1_bet: bool
    bookmaker: str
    odds: float
    odds_format: str
    our_probability: float
    bookmaker_probability: float
    edge_percentage: float
    expected_value_percentage: float
    commence_time: datetime
    surface: str
    tour: str  # 'atp' or 'wta'
    
    @property
    def recommended_stake(self) -> Optional[float]:
        """Calculate recommended stake using Kelly Criterion (fractional)."""
        if self.edge_percentage <= 0:
            return None
        
        # Fractional Kelly for safety
        decimal_odds = (
            self.odds
            if self.odds_format == OddsFormat.DECIMAL.value
            else self._american_to_decimal(self.odds)
        )
        
        # Kelly formula: (bp - q) / b
        # b = decimal odds - 1, p = our probability, q = 1 - p
        b = decimal_odds - 1
        p = self.our_probability
        q = 1 - p
        
        kelly = (b * p - q) / b
        return max(0, kelly * KELLY_FRACTION)
    
    def _american_to_decimal(self, american_odds: float) -> float:
        """Convert American odds to decimal."""
        if american_odds > 0:
            return 1 + (american_odds / 100)
        else:
            return 1 + (100 / abs(american_odds))


@dataclass
class Match:
    """Represents a tennis match."""
    id: str
    player1: str
    player2: str
    commence_time: datetime
    surface: str
    tour: str  # 'atp' or 'wta'
    player1_score: Optional[str] = None  # e.g., "6-4 6-3"
    player2_score: Optional[str] = None
    completed: bool = False
    winner: Optional[str] = None
    sets_played: Optional[int] = None
    
    @property
    def winner(self) -> Optional[str]:
        """Get the winning player if match is completed."""
        if not self.completed:
            return None
        return self.winner
    
    @property
    def sets_score(self) -> Optional[dict]:
        """Get sets score if match is completed."""
        if not self.completed or not self.player1_score or not self.player2_score:
            return None
        # Parse score strings (simplified - would need more parsing logic)
        return {
            "player1": self.player1_score,
            "player2": self.player2_score
        }


@dataclass
class BettingEdge:
    """Represents the calculated edge for a betting opportunity."""
    player: str
    probability_edge: float
    expected_value: float
    recommendation: str  # 'strong_bet', 'bet', 'pass'
    
    @classmethod
    def from_probabilities(
        cls,
        player: str,
        our_prob: float,
        bookie_prob: float,
        odds: float
    ) -> 'BettingEdge':
        """Create BettingEdge from probabilities."""
        from src.core.constants import STRONG_BET_THRESHOLD, BET_THRESHOLD
        
        prob_edge = (our_prob - bookie_prob) * 100
        expected_value = (our_prob * odds - 1) * 100
        
        if expected_value >= STRONG_BET_THRESHOLD:
            recommendation = 'strong_bet'
        elif expected_value >= BET_THRESHOLD:
            recommendation = 'bet'
        else:
            recommendation = 'pass'
        
        return cls(
            player=player,
            probability_edge=prob_edge,
            expected_value=expected_value,
            recommendation=recommendation
        )
