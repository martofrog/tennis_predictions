"""
Tennis Elo Rating System - Implementation of IRatingSystem (SOLID: SRP, OCP, LSP)

Refactored to separate rating calculation logic from persistence.
Implements IRatingSystem interface for interchangeability.
Adapted for tennis with surface-specific ratings.

Features:
- Smart initial ratings based on opponent strength
- Time decay for inactive players (1.5% per month)
- Surface-specific ratings
"""

import math
from typing import Dict, Tuple, Optional
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

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
    - Smart initial ratings based on opponent strength
    - Time decay for inactive players
    """
    
    DEFAULT_RATING = 1500
    BASE_K_FACTOR = 32  # Higher than team sports due to individual nature
    SURFACE_ADVANTAGE = DEFAULT_SURFACE_ADVANTAGE
    MONTHLY_DECAY_RATE = 0.015  # 1.5% decay per month of inactivity
    MIN_RATING_AFTER_DECAY = 1200  # Floor rating after decay
    
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
        
        # Track last match date for each player (for time decay)
        self._last_match_dates: Dict[str, datetime] = {}
        
        # Track player career stats (for smart initial ratings)
        self._player_stats: Dict[str, Dict[str, any]] = {}
        
        # Load ratings from repository
        ratings_data = self.repository.load()
        
        # Handle both old format (flat dict) and new format (with surface ratings)
        if isinstance(ratings_data, dict) and ratings_data:
            # Check if it's the new format with surface ratings
            first_key = list(ratings_data.keys())[0]
            if isinstance(ratings_data[first_key], dict) and 'rating' in ratings_data[first_key]:
                # New format: {"player": {"rating": 1500, "surface_ratings": {...}, "last_match_date": "..."}}
                self._ratings: Dict[str, Dict[str, float]] = {}
                for player, data in ratings_data.items():
                    self._ratings[player] = {
                        'overall': data.get('rating', default_rating),
                        **data.get('surface_ratings', {})
                    }
                    # Load last match date if available
                    if 'last_match_date' in data:
                        try:
                            self._last_match_dates[player] = datetime.fromisoformat(data['last_match_date'])
                        except (ValueError, TypeError):
                            pass
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
        Get current Elo rating for a player with time decay applied.
        
        Args:
            player: Player name
            surface: Optional surface ('hard', 'clay', 'grass') for surface-specific rating
            
        Returns:
            Player's rating (surface-specific if surface provided, otherwise overall)
            with time decay applied for inactive players
        """
        if player not in self._ratings:
            return self.default_rating
        
        player_ratings = self._ratings[player]
        
        # Get base rating (surface-specific or overall)
        if surface and surface in player_ratings:
            base_rating = player_ratings[surface]
        elif 'overall' in player_ratings:
            base_rating = player_ratings['overall']
        else:
            base_rating = self.default_rating
        
        # Apply time decay if player has been inactive
        if player in self._last_match_dates:
            return self._apply_time_decay(base_rating, self._last_match_dates[player])
        
        return base_rating
    
    def _apply_time_decay(self, rating: float, last_match_date: datetime) -> float:
        """
        Apply time decay to rating based on inactivity.
        
        Rating decays by MONTHLY_DECAY_RATE per month of inactivity.
        Has a floor of MIN_RATING_AFTER_DECAY.
        
        Args:
            rating: Base rating before decay
            last_match_date: Date of player's last match
            
        Returns:
            Rating with decay applied
        """
        now = datetime.now()
        months_inactive = (now.year - last_match_date.year) * 12 + now.month - last_match_date.month
        
        # Only apply decay if inactive for more than 3 months
        if months_inactive <= 3:
            return rating
        
        # Apply exponential decay
        decay_factor = (1 - self.MONTHLY_DECAY_RATE) ** (months_inactive - 3)
        decayed_rating = rating * decay_factor
        
        # Apply floor
        return max(decayed_rating, self.MIN_RATING_AFTER_DECAY)
    
    def _calculate_smart_initial_rating(self, player: str, opponent: str, opponent_rating: float) -> float:
        """
        Calculate smart initial rating for a new player based on their first opponent.
        
        Players entering the dataset at higher levels (facing strong opponents)
        start with higher ratings than the default 1500.
        
        Args:
            player: New player name
            opponent: First opponent name
            opponent_rating: Opponent's rating
            
        Returns:
            Estimated initial rating for the new player
        """
        # If opponent has a rating significantly different from default,
        # assume new player is roughly in same tier
        if opponent_rating >= 2200:  # Elite level
            return 1900  # Start new player at strong club level
        elif opponent_rating >= 1900:  # Strong level
            return 1700
        elif opponent_rating >= 1700:  # Above average
            return 1600
        elif opponent_rating >= 1600:  # Average
            return 1550
        else:
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
        surface: str = "hard",
        match_date: Optional[datetime] = None
    ) -> Tuple[float, float]:
        """
        Update ratings after a match with smart initial ratings and time tracking.
        
        Args:
            winner: Winning player name
            loser: Losing player name
            winner_score: Winner's score string (e.g., "6-4 6-3") - optional
            loser_score: Loser's score string - optional
            surface: Court surface
            match_date: Date of the match (for tracking last activity)
            
        Returns:
            Tuple of (new_winner_rating, new_loser_rating)
        """
        # Update last match dates
        if match_date is None:
            match_date = datetime.now()
        self._last_match_dates[winner] = match_date
        self._last_match_dates[loser] = match_date
        
        # Get current ratings (or calculate smart initial rating for new players)
        is_winner_new = winner not in self._ratings
        is_loser_new = loser not in self._ratings
        
        # For new players, use smart initial rating based on opponent
        if is_winner_new:
            opponent_rating = self.get_rating(loser, surface) if not is_loser_new else self.default_rating
            initial_rating = self._calculate_smart_initial_rating(winner, loser, opponent_rating)
            self._ratings[winner] = {'overall': initial_rating}
            rating_winner = initial_rating
        else:
            rating_winner = self.get_rating(winner, surface)
        
        if is_loser_new:
            opponent_rating = self.get_rating(winner, surface) if not is_winner_new else self.default_rating
            initial_rating = self._calculate_smart_initial_rating(loser, winner, opponent_rating)
            self._ratings[loser] = {'overall': initial_rating}
            rating_loser = initial_rating
        else:
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
    
    def save_ratings(self) -> None:
        """Save current ratings with last match dates to repository."""
        # Convert to format expected by repository
        ratings_to_save = {}
        for player, ratings in self._ratings.items():
            player_data = {
                'rating': ratings.get('overall', self.default_rating),
                'surface_ratings': {
                    surface: rating
                    for surface, rating in ratings.items()
                    if surface != 'overall'
                }
            }
            # Add last match date if available
            if player in self._last_match_dates:
                player_data['last_match_date'] = self._last_match_dates[player].isoformat()
            
            ratings_to_save[player] = player_data
        
        self.repository.save(ratings_to_save)
    
    def reload_ratings(self) -> None:
        """Reload ratings from repository."""
        ratings_data = self.repository.load()
        
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
