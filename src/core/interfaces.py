"""
Core Interfaces - Abstract base classes defining contracts (SOLID: DIP, ISP)

These interfaces allow for:
- Dependency Inversion: High-level modules depend on abstractions
- Interface Segregation: Small, focused interfaces
- Open/Closed: Easy to extend with new implementations
- Liskov Substitution: All implementations are interchangeable
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime


class IRatingSystem(ABC):
    """
    Interface for player rating systems.
    
    Allows multiple rating implementations (Elo, Glicko, custom) to be
    used interchangeably throughout the application.
    """
    
    @abstractmethod
    def get_rating(self, player: str, surface: Optional[str] = None) -> float:
        """Get current rating for a player (optionally surface-specific)."""
        pass
    
    @abstractmethod
    def predict_match(
        self,
        player1: str,
        player2: str,
        surface: str = "hard"
    ) -> Tuple[float, float]:
        """
        Predict match outcome probabilities.
        
        Returns:
            Tuple of (prob_player1_wins, prob_player2_wins)
        """
        pass
    
    @abstractmethod
    def update_ratings(
        self,
        winner: str,
        loser: str,
        winner_score: Optional[str] = None,
        loser_score: Optional[str] = None,
        surface: str = "hard"
    ) -> Tuple[float, float]:
        """
        Update ratings after a match.
        
        Returns:
            Tuple of (new_winner_rating, new_loser_rating)
        """
        pass
    
    @abstractmethod
    def get_all_ratings(self, surface: Optional[str] = None) -> Dict[str, float]:
        """Get all player ratings (optionally filtered by surface)."""
        pass


class IRatingRepository(ABC):
    """
    Interface for rating persistence (SOLID: SRP).
    
    Separates rating storage concerns from rating calculation logic.
    """
    
    @abstractmethod
    def load(self) -> Dict[str, Any]:
        """Load ratings from storage."""
        pass
    
    @abstractmethod
    def save(self, ratings: Dict[str, Any]) -> None:
        """Save ratings to storage."""
        pass
    
    @abstractmethod
    def exists(self) -> bool:
        """Check if ratings storage exists."""
        pass


class IOddsProvider(ABC):
    """
    Interface for odds data providers.
    
    Allows swapping between different odds APIs or mock data.
    """
    
    @abstractmethod
    def get_odds(
        self,
        sport: str,
        regions: str,
        markets: str,
        odds_format: str
    ) -> List[Dict[str, Any]]:
        """Fetch odds for a sport."""
        pass
    
    @abstractmethod
    def get_available_sports(self) -> List[str]:
        """Get list of available sports."""
        pass
    
    @abstractmethod
    def get_usage_stats(self) -> Dict[str, Any]:
        """Get API usage statistics."""
        pass


class IMatchDataRepository(ABC):
    """
    Interface for match data persistence.
    
    Handles loading/saving historical match data.
    """
    
    @abstractmethod
    def load_matches(self, years: Optional[List[int]] = None, tour: Optional[str] = None) -> Any:
        """Load match data for specified years and tour."""
        pass
    
    @abstractmethod
    def save_matches(self, data: Any, year: int, tour: str) -> None:
        """Save match data for a year and tour."""
        pass
    
    @abstractmethod
    def match_data_exists(self, year: int, tour: str) -> bool:
        """Check if data exists for a year and tour."""
        pass
    
    @abstractmethod
    def get_matches_by_date(self, target_date: datetime, tour: Optional[str] = None) -> Any:
        """
        Get matches for a specific date.
        
        Args:
            target_date: Date to get matches for
            tour: Optional tour filter ('atp' or 'wta')
            
        Returns:
            Match data for the specified date
        """
        pass


class ICacheStorage(ABC):
    """
    Interface for cache storage.
    
    Allows different cache backends (file, Redis, memory).
    """
    
    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """Get cached value."""
        pass
    
    @abstractmethod
    def set(self, key: str, value: Any, ttl_minutes: Optional[int] = None) -> None:
        """Set cached value with optional TTL."""
        pass
    
    @abstractmethod
    def delete(self, key: str) -> None:
        """Delete cached value."""
        pass
    
    @abstractmethod
    def clear(self) -> None:
        """Clear all cached values."""
        pass
    
    @abstractmethod
    def keys(self) -> List[str]:
        """Get all cache keys."""
        pass
    
    @abstractmethod
    def is_valid(self, key: str) -> bool:
        """Check if cached value is still valid."""
        pass


class IOddsConverter(ABC):
    """
    Interface for odds format conversion.
    
    Separates odds conversion logic from calculator.
    """
    
    @abstractmethod
    def decimal_to_probability(self, odds: float) -> float:
        """Convert decimal odds to implied probability."""
        pass
    
    @abstractmethod
    def american_to_probability(self, odds: float) -> float:
        """Convert American odds to implied probability."""
        pass
    
    @abstractmethod
    def probability_to_decimal(self, probability: float) -> float:
        """Convert probability to decimal odds."""
        pass
    
    @abstractmethod
    def probability_to_american(self, probability: float) -> float:
        """Convert probability to American odds."""
        pass


class IBettingEdgeCalculator(ABC):
    """
    Interface for betting edge calculation.
    
    Allows different edge calculation strategies.
    """
    
    @abstractmethod
    def calculate_edge(
        self,
        player1: str,
        player2: str,
        odds_player1: float,
        odds_player2: Optional[float],
        odds_format: str,
        surface: str
    ) -> Dict[str, Any]:
        """Calculate betting edge for a matchup."""
        pass
    
    @abstractmethod
    def find_value_bets(
        self,
        matches: List[Dict[str, Any]],
        min_edge: float
    ) -> List[Dict[str, Any]]:
        """Find value bets from a list of matches."""
        pass
