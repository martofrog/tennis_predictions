"""
Rating Service - Manages player ratings with dependency injection (SOLID: DIP, SRP)

This service depends on abstractions (IRatingSystem, IRatingRepository)
rather than concrete implementations, following Dependency Inversion Principle.
"""

from typing import Dict, Tuple, List, Optional, Any
from datetime import datetime

from src.core.interfaces import IRatingSystem, IRatingRepository
from src.core.domain_models import PlayerRating, MatchPrediction


class RatingService:
    """
    Service for managing player ratings.
    
    Single Responsibility: Coordinating rating operations.
    Dependency Inversion: Depends on interfaces, not implementations.
    """
    
    def __init__(
        self,
        rating_system: IRatingSystem,
        repository: IRatingRepository
    ):
        """
        Initialize rating service with dependency injection.
        
        Args:
            rating_system: Rating system implementation
            repository: Rating repository implementation
        """
        self.rating_system = rating_system
        self.repository = repository
    
    def get_player_rating(self, player: str, surface: Optional[str] = None) -> PlayerRating:
        """
        Get rating for a specific player.
        
        Args:
            player: Player name
            surface: Optional surface for surface-specific rating
            
        Returns:
            PlayerRating domain model
        """
        rating = self.rating_system.get_rating(player, surface)
        return PlayerRating(
            player=player,
            rating=rating,
            last_updated=datetime.now()
        )
    
    def get_all_ratings(self, sort_by: str = "rating", surface: Optional[str] = None) -> List[PlayerRating]:
        """
        Get all player ratings, optionally sorted.
        
        Args:
            sort_by: Sort key ('rating' or 'player')
            surface: Optional surface filter
            
        Returns:
            List of PlayerRating objects
        """
        ratings_dict = self.rating_system.get_all_ratings(surface)
        
        ratings = [
            PlayerRating(player=player, rating=rating)
            for player, rating in ratings_dict.items()
        ]
        
        if sort_by == "rating":
            ratings.sort(key=lambda x: x.rating, reverse=True)
        elif sort_by == "player":
            ratings.sort(key=lambda x: x.player)
        
        return ratings
    
    def predict_match(
        self,
        player1: str,
        player2: str,
        surface: str = "hard"
    ) -> MatchPrediction:
        """
        Predict match outcome.
        
        Args:
            player1: Player 1 name
            player2: Player 2 name
            surface: Court surface ('hard', 'clay', 'grass')
            
        Returns:
            MatchPrediction domain model
        """
        player1_prob, player2_prob = self.rating_system.predict_match(
            player1, player2, surface
        )
        
        player1_rating = self.rating_system.get_rating(player1, surface)
        player2_rating = self.rating_system.get_rating(player2, surface)
        
        surface_adv = getattr(
            self.rating_system,
            'surface_advantage',
            getattr(self.rating_system, 'SURFACE_ADVANTAGE', 0)
        )
        
        return MatchPrediction(
            player1=player1,
            player2=player2,
            player1_win_probability=player1_prob,
            player2_win_probability=player2_prob,
            player1_rating=player1_rating,
            player2_rating=player2_rating,
            surface=surface,
            surface_adjustment=surface_adv
        )
    
    def update_ratings_from_match(
        self,
        winner: str,
        loser: str,
        winner_score: Optional[str] = None,
        loser_score: Optional[str] = None,
        surface: str = "hard"
    ) -> Tuple[float, float]:
        """
        Update ratings after a match.
        
        Args:
            winner: Winning player name
            loser: Losing player name
            winner_score: Winner's score string (optional)
            loser_score: Loser's score string (optional)
            surface: Court surface
            
        Returns:
            Tuple of (new_winner_rating, new_loser_rating)
        """
        new_winner_rating, new_loser_rating = self.rating_system.update_ratings(
            winner, loser, winner_score, loser_score, surface
        )
        
        # Save updated ratings
        self.save_ratings()
        
        return new_winner_rating, new_loser_rating
    
    def load_ratings(self) -> Dict[str, Any]:
        """Load ratings from repository."""
        return self.repository.load()
    
    def save_ratings(self) -> None:
        """Save current ratings to repository."""
        # Get ratings from rating system and save
        if hasattr(self.rating_system, 'save_ratings'):
            self.rating_system.save_ratings()
        else:
            # Fallback: get all ratings and save via repository
            ratings = self.rating_system.get_all_ratings()
            self.repository.save(ratings)
    
    def ratings_exist(self) -> bool:
        """Check if ratings have been saved."""
        return self.repository.exists()
