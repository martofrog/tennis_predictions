"""
Tennis Elo Rating System - Implementation of IRatingSystem (SOLID: SRP, OCP, LSP)

Refactored to separate rating calculation logic from persistence.
Implements IRatingSystem interface for interchangeability.
Adapted for tennis with surface-specific ratings.
"""

import math
from typing import Dict, Tuple, Optional

from src.core.interfaces import IRatingSystem, IRatingRepository
from src.core.constants import Surface, DEFAULT_SURFACE_ADVANTAGE


class TennisEloRatingSystem(IRatingSystem):
    """
    Tennis Elo rating system implementation following SOLID principles.
    
    Single Responsibility: Rating calculations only (no I/O).
    Open/Closed: Extends IRatingSystem without modifying it.
    Liskov Substitution: Can replace any IRatingSystem implementation.
    Dependency Inversion: Depends on IRatingRepository abstraction.
    
    Features:
    - Surface-specific ratings (hard, clay, grass)
    - Surface specialization adjustments
    - Set-based margin of victory
    """
    
    DEFAULT_RATING = 1500
    BASE_K_FACTOR = 32  # Higher than team sports due to individual nature
    SURFACE_ADVANTAGE = DEFAULT_SURFACE_ADVANTAGE
    
    def __init__(
        self,
        repository: IRatingRepository,
        surface_advantage: float = DEFAULT_SURFACE_ADVANTAGE,
        k_factor: float = 32,
        default_rating: float = 1500
    ):
        """
        Initialize Tennis Elo rating system with dependency injection.
        
        Args:
            repository: Repository for loading/saving ratings
            surface_advantage: Elo points for surface specialization
            k_factor: Base K-factor for rating updates
            default_rating: Default rating for new players
        """
        self.repository = repository
        self.surface_advantage = surface_advantage
        self.k_factor = k_factor
        self.default_rating = default_rating
        self.SURFACE_ADVANTAGE = surface_advantage
        
        # Load ratings from repository
        ratings_data = self.repository.load()
        
        # Handle both old format (flat dict) and new format (with surface ratings)
        if isinstance(ratings_data, dict) and ratings_data:
            # Check if it's the new format with surface ratings
            first_key = list(ratings_data.keys())[0]
            if isinstance(ratings_data[first_key], dict) and 'rating' in ratings_data[first_key]:
                # New format: {"player": {"rating": 1500, "surface_ratings": {...}}}
                self._ratings: Dict[str, Dict[str, float]] = {
                    player: {
                        'overall': data.get('rating', default_rating),
                        **data.get('surface_ratings', {})
                    }
                    for player, data in ratings_data.items()
                }
            else:
                # Old format: {"player": 1500} - convert to new format
                self._ratings: Dict[str, Dict[str, float]] = {
                    player: {'overall': rating}
                    for player, rating in ratings_data.items()
                }
        else:
            self._ratings: Dict[str, Dict[str, float]] = {}
    
    def get_rating(self, player: str, surface: Optional[str] = None) -> float:
        """
        Get current Elo rating for a player.
        
        Args:
            player: Player name
            surface: Optional surface ('hard', 'clay', 'grass') for surface-specific rating
            
        Returns:
            Player's rating (surface-specific if surface provided, otherwise overall)
        """
        if player not in self._ratings:
            return self.default_rating
        
        player_ratings = self._ratings[player]
        
        if surface and surface in player_ratings:
            # Return surface-specific rating
            return player_ratings[surface]
        elif 'overall' in player_ratings:
            # Return overall rating
            return player_ratings['overall']
        else:
            # Fallback to default
            return self.default_rating
    
    def get_all_ratings(self, surface: Optional[str] = None) -> Dict[str, float]:
        """
        Get all player ratings.
        
        Args:
            surface: Optional surface filter
            
        Returns:
            Dictionary of player -> rating
        """
        if surface:
            return {
                player: self.get_rating(player, surface)
                for player in self._ratings.keys()
            }
        else:
            return {
                player: self.get_rating(player)
                for player in self._ratings.keys()
            }
    
    def predict_match(
        self,
        player1: str,
        player2: str,
        surface: str = "hard"
    ) -> Tuple[float, float]:
        """
        Predict match outcome probabilities.
        
        Args:
            player1: Name of player 1
            player2: Name of player 2
            surface: Court surface ('hard', 'clay', 'grass')
            
        Returns:
            Tuple of (prob_player1_wins, prob_player2_wins)
        """
        rating1 = self.get_rating(player1, surface)
        rating2 = self.get_rating(player2, surface)
        
        # Apply surface specialization adjustment
        # If a player has a surface-specific rating, they get a small boost
        player1_has_surface_rating = (
            player1 in self._ratings and 
            surface in self._ratings[player1]
        )
        player2_has_surface_rating = (
            player2 in self._ratings and 
            surface in self._ratings[player2]
        )
        
        if player1_has_surface_rating and not player2_has_surface_rating:
            rating1 += self.surface_advantage * 0.5
        elif player2_has_surface_rating and not player1_has_surface_rating:
            rating2 += self.surface_advantage * 0.5
        
        # Calculate expected score using Elo formula
        expected1 = self._calculate_expected_score(rating1, rating2)
        expected2 = 1 - expected1
        
        return expected1, expected2
    
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
        
        Args:
            winner: Winning player name
            loser: Losing player name
            winner_score: Winner's score string (e.g., "6-4 6-3") - optional
            loser_score: Loser's score string - optional
            surface: Court surface
            
        Returns:
            Tuple of (new_winner_rating, new_loser_rating)
        """
        rating_winner = self.get_rating(winner, surface)
        rating_loser = self.get_rating(loser, surface)
        
        # Calculate margin of victory multiplier based on sets
        sets_multiplier = self._calculate_sets_multiplier(winner_score, loser_score)
        
        # Calculate expected scores
        expected_winner = self._calculate_expected_score(rating_winner, rating_loser)
        expected_loser = 1 - expected_winner
        
        # Actual scores (winner gets 1, loser gets 0)
        actual_winner = 1.0
        actual_loser = 0.0
        
        # Calculate rating changes with sets multiplier
        k_adjusted = self.k_factor * sets_multiplier
        
        change_winner = k_adjusted * (actual_winner - expected_winner)
        change_loser = k_adjusted * (actual_loser - expected_loser)
        
        # Update ratings (both overall and surface-specific)
        new_rating_winner = rating_winner + change_winner
        new_rating_loser = rating_loser + change_loser
        
        # Update overall rating
        if winner not in self._ratings:
            self._ratings[winner] = {'overall': self.default_rating}
        if 'overall' not in self._ratings[winner]:
            self._ratings[winner]['overall'] = self.default_rating
        
        if loser not in self._ratings:
            self._ratings[loser] = {'overall': self.default_rating}
        if 'overall' not in self._ratings[loser]:
            self._ratings[loser]['overall'] = self.default_rating
        
        # Update overall ratings
        self._ratings[winner]['overall'] += change_winner
        self._ratings[loser]['overall'] += change_loser
        
        # Update surface-specific ratings
        if surface not in self._ratings[winner]:
            self._ratings[winner][surface] = self._ratings[winner]['overall']
        if surface not in self._ratings[loser]:
            self._ratings[loser][surface] = self._ratings[loser]['overall']
        
        self._ratings[winner][surface] = new_rating_winner
        self._ratings[loser][surface] = new_rating_loser
        
        return new_rating_winner, new_rating_loser
    
    def _calculate_expected_score(self, rating_a: float, rating_b: float) -> float:
        """
        Calculate expected score using Elo formula.
        
        Args:
            rating_a: Rating of player A
            rating_b: Rating of player B
            
        Returns:
            Expected score for player A (0.0 to 1.0)
        """
        exponent = (rating_b - rating_a) / 400
        return 1 / (1 + 10 ** exponent)
    
    def _calculate_sets_multiplier(
        self,
        winner_score: Optional[str],
        loser_score: Optional[str]
    ) -> float:
        """
        Calculate margin of victory multiplier based on sets won.
        
        Straight-set wins (2-0 or 3-0) get higher multiplier than close matches.
        
        Args:
            winner_score: Winner's score string (e.g., "6-4 6-3")
            loser_score: Loser's score string
            
        Returns:
            Multiplier for K-factor
        """
        if not winner_score:
            return 1.0  # Default multiplier
        
        try:
            # Count sets won by winner
            sets = winner_score.strip().split()
            sets_won = 0
            
            for set_score in sets:
                if '-' in set_score:
                    parts = set_score.split('-')
                    if len(parts) == 2:
                        try:
                            winner_games = int(parts[0])
                            loser_games = int(parts[1])
                            if winner_games > loser_games:
                                sets_won += 1
                        except ValueError:
                            continue
            
            # Multiplier based on dominance
            # Straight sets (2-0 or 3-0): higher multiplier
            # Close match (3-2): lower multiplier
            if sets_won == 2:  # Best of 3, won 2-0
                return 1.2
            elif sets_won == 3:  # Best of 5, won 3-0
                return 1.3
            else:  # Won in 3 sets (2-1) or 5 sets (3-2)
                return 1.0
            
        except Exception:
            return 1.0
    
    def save_ratings(self, last_update_date: str = None) -> None:
        """
        Save current ratings to repository with metadata.
        
        Args:
            last_update_date: ISO format date string of last processed match
        """
        from datetime import datetime
        
        # Convert to format expected by repository
        ratings_to_save = {
            player: {
                'rating': ratings.get('overall', self.default_rating),
                'surface_ratings': {
                    surface: rating
                    for surface, rating in ratings.items()
                    if surface != 'overall'
                }
            }
            for player, ratings in self._ratings.items()
        }
        
        # Add metadata
        metadata = {
            '_metadata': {
                'last_update': last_update_date or datetime.now().isoformat(),
                'total_players': len(ratings_to_save),
                'version': '2.0'
            }
        }
        ratings_to_save.update(metadata)
        
        self.repository.save(ratings_to_save)
    
    def reload_ratings(self) -> None:
        """Reload ratings from repository."""
        ratings_data = self.repository.load()
        
        # Remove metadata if present
        if isinstance(ratings_data, dict) and '_metadata' in ratings_data:
            ratings_data = {k: v for k, v in ratings_data.items() if k != '_metadata'}
        
        if isinstance(ratings_data, dict) and ratings_data:
            first_key = list(ratings_data.keys())[0]
            if isinstance(ratings_data[first_key], dict) and 'rating' in ratings_data[first_key]:
                self._ratings = {
                    player: {
                        'overall': data.get('rating', self.default_rating),
                        **data.get('surface_ratings', {})
                    }
                    for player, data in ratings_data.items()
                }
            else:
                self._ratings = {
                    player: {'overall': rating}
                    for player, rating in ratings_data.items()
                }
        else:
            self._ratings = {}
    
    def get_last_update_date(self) -> str:
        """
        Get the last update date from ratings metadata.
        
        Returns:
            ISO format date string, or None if not found
        """
        ratings_data = self.repository.load()
        if isinstance(ratings_data, dict) and '_metadata' in ratings_data:
            return ratings_data['_metadata'].get('last_update')
        return None
