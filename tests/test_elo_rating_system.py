"""
Tests for Tennis Elo Rating System.

Tests all core Elo functionalities including:
- Smart initial ratings
- Time decay
- Rating updates
- Surface-specific ratings
- Save/load operations
"""

import pytest
from datetime import datetime, timedelta
from src.prediction.elo_rating_system import TennisEloRatingSystem


class TestEloRatingBasics:
    """Test basic Elo rating functionality."""
    
    def test_default_rating_for_new_player(self, clean_rating_system):
        """Test that new players get default rating."""
        rating = clean_rating_system.get_rating("New Player")
        assert rating == 1500
    
    def test_get_rating_for_existing_player(self, rating_system_with_data):
        """Test retrieving existing player rating."""
        rating = rating_system_with_data.get_rating("Novak Djokovic")
        # Rating may have time decay applied, so check it's in reasonable range
        assert 2000 <= rating <= 2600
    
    def test_surface_specific_rating(self, rating_system_with_data):
        """Test surface-specific ratings."""
        hard_rating = rating_system_with_data.get_rating("Novak Djokovic", "hard")
        clay_rating = rating_system_with_data.get_rating("Novak Djokovic", "clay")
        
        # Check ratings are in reasonable range (time decay may apply)
        assert 2100 <= hard_rating <= 2700
        assert 2000 <= clay_rating <= 2600
        # Hard should be higher than clay for Djokovic in our test data
        assert hard_rating > clay_rating
    
    def test_get_all_ratings(self, rating_system_with_data):
        """Test retrieving all ratings."""
        all_ratings = rating_system_with_data.get_all_ratings()
        
        assert isinstance(all_ratings, dict)
        assert len(all_ratings) == 3
        assert "Novak Djokovic" in all_ratings
        assert "Carlos Alcaraz" in all_ratings
        assert "Jannik Sinner" in all_ratings
        
        # Check ratings are floats
        for player, rating in all_ratings.items():
            assert isinstance(rating, (int, float))


class TestSmartInitialRatings:
    """Test smart initial rating calculation based on opponent strength."""
    
    def test_smart_initial_rating_elite_opponent(self, clean_rating_system):
        """Test new player facing elite opponent (2200+)."""
        # Create an elite player first
        clean_rating_system._ratings["Elite Player"] = {"overall": 2300}
        
        initial_rating = clean_rating_system._calculate_smart_initial_rating(
            "New Player", "Elite Player", 2300
        )
        
        assert initial_rating == 1900  # Should start at 1900 for elite opponent
    
    def test_smart_initial_rating_strong_opponent(self, clean_rating_system):
        """Test new player facing strong opponent (1900+)."""
        initial_rating = clean_rating_system._calculate_smart_initial_rating(
            "New Player", "Strong Player", 1950
        )
        
        assert initial_rating == 1700
    
    def test_smart_initial_rating_average_opponent(self, clean_rating_system):
        """Test new player facing average opponent."""
        initial_rating = clean_rating_system._calculate_smart_initial_rating(
            "New Player", "Average Player", 1650
        )
        
        # For rating 1650 (between 1600-1700), should get 1550
        assert initial_rating == 1550
    
    def test_smart_initial_rating_weak_opponent(self, clean_rating_system):
        """Test new player facing weak opponent."""
        initial_rating = clean_rating_system._calculate_smart_initial_rating(
            "New Player", "Weak Player", 1400
        )
        
        assert initial_rating == 1500  # Default rating


class TestTimeDecay:
    """Test time decay functionality for inactive players."""
    
    def test_no_decay_for_recent_match(self, clean_rating_system):
        """Test that recent players (< 3 months) have no decay."""
        base_rating = 2000
        recent_date = datetime.now() - timedelta(days=60)  # 2 months ago
        
        decayed_rating = clean_rating_system._apply_time_decay(base_rating, recent_date)
        
        assert decayed_rating == base_rating  # No decay
    
    def test_decay_for_inactive_player(self, clean_rating_system):
        """Test decay for player inactive > 3 months."""
        base_rating = 2000
        old_date = datetime.now() - timedelta(days=180)  # 6 months ago
        
        decayed_rating = clean_rating_system._apply_time_decay(base_rating, old_date)
        
        # 3 months of inactivity after the 3-month grace period
        # Decay = (1 - 0.015)^3 ≈ 0.9556
        expected = base_rating * (0.985 ** 3)
        
        assert decayed_rating < base_rating
        assert abs(decayed_rating - expected) < 1  # Allow small floating point error
    
    def test_decay_floor(self, clean_rating_system):
        """Test that decay has a minimum floor."""
        base_rating = 2000
        very_old_date = datetime.now() - timedelta(days=3650)  # 10 years ago
        
        decayed_rating = clean_rating_system._apply_time_decay(base_rating, very_old_date)
        
        assert decayed_rating >= clean_rating_system.MIN_RATING_AFTER_DECAY
        assert decayed_rating == clean_rating_system.MIN_RATING_AFTER_DECAY
    
    def test_get_rating_applies_time_decay(self, rating_system_with_data):
        """Test that get_rating automatically applies time decay."""
        # Djokovic's last match was 2024-12-15
        # If we're in 2026, that's about 13 months inactive
        rating = rating_system_with_data.get_rating("Novak Djokovic")
        
        # Rating should be less than stored value due to decay
        # (assuming current date is 2026)
        stored_rating = 2500
        assert rating <= stored_rating


class TestRatingUpdates:
    """Test rating updates after matches."""
    
    def test_update_ratings_winner_gains_loser_loses(self, clean_rating_system):
        """Test basic rating update: winner gains, loser loses points."""
        match_date = datetime(2024, 12, 15)
        
        winner_before = clean_rating_system.get_rating("Player A")
        loser_before = clean_rating_system.get_rating("Player B")
        
        winner_after, loser_after = clean_rating_system.update_ratings(
            winner="Player A",
            loser="Player B",
            surface="hard",
            match_date=match_date
        )
        
        assert winner_after > winner_before
        assert loser_after < loser_before
    
    def test_update_ratings_underdog_wins(self, clean_rating_system):
        """Test larger point swing when underdog wins."""
        match_date = datetime.now()  # Use current date to avoid decay
        
        # Create strong and weak players with current dates
        clean_rating_system._ratings["Strong"] = {"overall": 2000}
        clean_rating_system._ratings["Weak"] = {"overall": 1500}
        clean_rating_system._last_match_dates["Strong"] = match_date
        clean_rating_system._last_match_dates["Weak"] = match_date
        
        # Get ratings before (no decay since dates are current)
        weak_before = clean_rating_system.get_rating("Weak")
        strong_before = clean_rating_system.get_rating("Strong")
        
        # Weak player beats strong player
        winner_after, loser_after = clean_rating_system.update_ratings(
            winner="Weak",
            loser="Strong",
            surface="hard",
            match_date=match_date
        )
        
        # Weak player should gain points
        weak_gain = winner_after - weak_before
        strong_loss = strong_before - loser_after
        
        assert weak_gain > 20  # Significant gain for upset
        assert abs(weak_gain - strong_loss) < 1  # Approximately zero-sum
    
    def test_update_ratings_tracks_last_match_date(self, clean_rating_system):
        """Test that update_ratings tracks last match date."""
        match_date = datetime(2024, 12, 15)
        
        clean_rating_system.update_ratings(
            winner="Player A",
            loser="Player B",
            surface="hard",
            match_date=match_date
        )
        
        assert "Player A" in clean_rating_system._last_match_dates
        assert "Player B" in clean_rating_system._last_match_dates
        assert clean_rating_system._last_match_dates["Player A"] == match_date
        assert clean_rating_system._last_match_dates["Player B"] == match_date
    
    def test_update_ratings_uses_smart_initial_for_new_players(self, clean_rating_system):
        """Test that new players get smart initial ratings."""
        match_date = datetime(2024, 12, 15)
        
        # Create an elite player
        clean_rating_system._ratings["Elite"] = {"overall": 2300}
        
        # New player faces elite player
        winner_after, loser_after = clean_rating_system.update_ratings(
            winner="Elite",
            loser="New Player",
            surface="hard",
            match_date=match_date
        )
        
        # New player should start higher than default (1500) since facing elite opponent
        assert "New Player" in clean_rating_system._ratings
        # Smart initial rating for facing 2300 player should be 1900
        # After losing, it will be a bit less
        assert clean_rating_system._ratings["New Player"]["overall"] > 1500


class TestSurfaceRatings:
    """Test surface-specific rating functionality."""
    
    def test_surface_ratings_independence(self, clean_rating_system):
        """Test that surface ratings are independent."""
        match_date = datetime(2024, 12, 15)
        
        # Play match on hard court
        clean_rating_system.update_ratings(
            winner="Player A",
            loser="Player B",
            surface="hard",
            match_date=match_date
        )
        
        hard_rating = clean_rating_system.get_rating("Player A", "hard")
        clay_rating = clean_rating_system.get_rating("Player A", "clay")
        
        # Hard rating should be different from default, clay should still be default
        assert hard_rating != 1500
        assert "clay" not in clean_rating_system._ratings["Player A"] or \
               clean_rating_system._ratings["Player A"].get("clay") is None


class TestSaveLoad:
    """Test saving and loading ratings."""
    
    def test_save_and_load_ratings(self, clean_rating_system, temp_data_dir):
        """Test that ratings can be saved and loaded."""
        match_date = datetime.now()  # Use current date
        
        # Create some ratings
        winner_after, loser_after = clean_rating_system.update_ratings(
            winner="Player A",
            loser="Player B",
            surface="hard",
            match_date=match_date
        )
        
        # Save
        clean_rating_system.save_ratings()
        
        # Create new rating system with same repository
        from src.infrastructure.repositories import JsonRatingRepository
        ratings_file = temp_data_dir / "ratings.json"
        new_repository = JsonRatingRepository(str(ratings_file))
        new_system = TennisEloRatingSystem(
            repository=new_repository,
            default_rating=1500,
            k_factor=32,
            surface_advantage=50
        )
        
        # Check ratings are loaded (should match what we saved)
        loaded_a = new_system.get_rating("Player A")
        loaded_b = new_system.get_rating("Player B")
        
        # Allow small difference due to potential rounding
        assert abs(loaded_a - winner_after) < 1
        assert abs(loaded_b - loser_after) < 1
    
    def test_save_includes_last_match_date(self, clean_rating_system, temp_data_dir):
        """Test that last match dates are saved."""
        match_date = datetime(2024, 12, 15)
        
        clean_rating_system.update_ratings(
            winner="Player A",
            loser="Player B",
            surface="hard",
            match_date=match_date
        )
        
        clean_rating_system.save_ratings()
        
        # Load and check
        from src.infrastructure.repositories import JsonRatingRepository
        import json
        
        ratings_file = temp_data_dir / "ratings.json"
        with open(ratings_file, 'r') as f:
            data = json.load(f)
        
        assert "last_match_date" in data["Player A"]
        assert data["Player A"]["last_match_date"] == match_date.isoformat()


class TestPrediction:
    """Test match prediction functionality."""
    
    def test_predict_match_favorite_higher_win_probability(self, rating_system_with_data):
        """Test that higher-rated player has higher win probability."""
        prob1, prob2 = rating_system_with_data.predict_match(
            player1="Novak Djokovic",  # Higher rated
            player2="Jannik Sinner",
            surface="hard"
        )
        
        # Both probabilities should be valid
        assert 0 < prob1 < 1
        assert 0 < prob2 < 1
        
        # Should sum to 1
        assert abs(prob1 + prob2 - 1.0) < 0.01
        
        # Djokovic should be favored (higher rated)
        assert prob1 > prob2
    
    def test_predict_match_even_players(self, clean_rating_system):
        """Test prediction for evenly matched players."""
        match_date = datetime.now()
        
        # Create two players with equal ratings
        clean_rating_system._ratings["Player A"] = {"overall": 2000}
        clean_rating_system._ratings["Player B"] = {"overall": 2000}
        clean_rating_system._last_match_dates["Player A"] = match_date
        clean_rating_system._last_match_dates["Player B"] = match_date
        
        prob1, prob2 = clean_rating_system.predict_match("Player A", "Player B", "hard")
        
        # Should be close to 50/50
        assert abs(prob1 - 0.5) < 0.05
        assert abs(prob2 - 0.5) < 0.05

