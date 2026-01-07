"""
Tests for Tennis Predictions API Endpoints.

Tests all API endpoints including:
- Health checks
- Player ratings
- Match results
- Predictions
- Value bets
- Cache management
"""

import pytest
from fastapi import status


class TestGeneralEndpoints:
    """Test general API endpoints."""
    
    def test_root_endpoint(self, client):
        """Test root endpoint returns HTML."""
        response = client.get("/")
        
        assert response.status_code == status.HTTP_200_OK
        assert "text/html" in response.headers["content-type"]
    
    def test_health_endpoint(self, client):
        """Test health check endpoint."""
        response = client.get("/api/v2/health")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert "status" in data
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "service" in data
        assert data["service"] == "tennis-predictions"


class TestRatingsEndpoint:
    """Test player ratings endpoint."""
    
    def test_get_all_ratings(self, client):
        """Test getting all player ratings."""
        response = client.get("/api/v2/ratings")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert isinstance(data, list)
        if len(data) > 0:
            # Check structure of rating objects
            rating = data[0]
            assert "player_name" in rating
            assert "rating" in rating
            assert "tour" in rating
            assert isinstance(rating["rating"], (int, float))
            assert rating["tour"] in ["atp", "wta"]
    
    def test_get_ratings_filtered_by_tour(self, client):
        """Test filtering ratings by tour."""
        response = client.get("/api/v2/ratings?tour=atp")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert isinstance(data, list)
        # All ratings should be ATP
        for rating in data:
            assert rating["tour"] == "atp"
    
    def test_get_ratings_top_n(self, client):
        """Test limiting ratings to top N players."""
        response = client.get("/api/v2/ratings?limit=10")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) <= 10
    
    def test_get_ratings_by_surface(self, client):
        """Test getting ratings for specific surface."""
        response = client.get("/api/v2/ratings?surface=clay")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert isinstance(data, list)
    
    def test_get_ratings_invalid_tour(self, client):
        """Test that invalid tour parameter returns error."""
        response = client.get("/api/v2/ratings?tour=invalid")
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_ratings_sorted_descending(self, client):
        """Test that ratings are sorted by rating descending."""
        response = client.get("/api/v2/ratings?limit=10")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        if len(data) > 1:
            ratings = [r["rating"] for r in data]
            assert ratings == sorted(ratings, reverse=True)


class TestMatchResultsEndpoint:
    """Test yesterday's match results endpoint."""
    
    def test_get_yesterday_matches(self, client):
        """Test getting yesterday's matches."""
        response = client.get("/api/v2/matches/yesterday")
        
        # Note: This might return 200 with empty list or 503 if no data
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_503_SERVICE_UNAVAILABLE]
        
        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            assert isinstance(data, list)
            
            if len(data) > 0:
                match = data[0]
                assert "player1" in match
                assert "player2" in match
                assert "player1_score" in match
                assert "player2_score" in match
                assert "winner" in match
                assert "tournament" in match
                assert "surface" in match
    
    def test_get_yesterday_matches_filtered_by_tour(self, client):
        """Test filtering yesterday's matches by tour."""
        response = client.get("/api/v2/matches/yesterday?tour=atp")
        
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_503_SERVICE_UNAVAILABLE]
        
        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            assert isinstance(data, list)
    
    def test_matches_no_doubles(self, client):
        """Test that doubles matches are filtered out."""
        response = client.get("/api/v2/matches/yesterday")
        
        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            
            # Check no player names contain '/'
            for match in data:
                assert "/" not in match["player1"]
                assert "/" not in match["player2"]
    
    def test_get_latest_matches(self, client):
        """Test getting latest matches for last N days."""
        response = client.get("/api/v2/matches/latest?days=1")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        
        if len(data) > 0:
            match = data[0]
            assert "player1" in match
            assert "player2" in match
            assert "date" in match
            assert "tour" in match
    
    def test_get_latest_matches_multiple_days(self, client):
        """Test getting latest matches for multiple days."""
        response = client.get("/api/v2/matches/latest?days=3&tour=atp")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        
        # All matches should be ATP
        for match in data:
            assert match["tour"] == "atp"
    
    def test_get_latest_matches_max_days(self, client):
        """Test that days parameter is limited to max 7."""
        response = client.get("/api/v2/matches/latest?days=10")
        
        # Should return 422 for validation error
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_get_latest_matches_min_days(self, client):
        """Test that days parameter must be at least 1."""
        response = client.get("/api/v2/matches/latest?days=0")
        
        # Should return 422 for validation error
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestPredictionEndpoint:
    """Test match prediction endpoint."""
    
    def test_predict_match_success(self, client):
        """Test successful match prediction."""
        response = client.get(
            "/api/v2/predict",
            params={
                "player1": "Novak Djokovic",
                "player2": "Carlos Alcaraz",
                "surface": "hard"
            }
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert "player1" in data
        assert "player2" in data
        assert "surface" in data
        assert "player1_win_probability" in data
        assert "player2_win_probability" in data
        assert "player1_rating" in data
        assert "player2_rating" in data
        
        # Probabilities should sum to ~1.0
        prob_sum = data["player1_win_probability"] + data["player2_win_probability"]
        assert abs(prob_sum - 1.0) < 0.01
        
        # Each probability should be between 0 and 1
        assert 0 < data["player1_win_probability"] < 1
        assert 0 < data["player2_win_probability"] < 1
    
    def test_predict_match_missing_player(self, client):
        """Test prediction fails with missing player parameter."""
        response = client.get(
            "/api/v2/predict",
            params={
                "player1": "Novak Djokovic",
                "surface": "hard"
            }
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_predict_match_invalid_surface(self, client):
        """Test prediction with invalid surface."""
        response = client.get(
            "/api/v2/predict",
            params={
                "player1": "Novak Djokovic",
                "player2": "Carlos Alcaraz",
                "surface": "invalid"
            }
        )
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestValueBetsEndpoint:
    """Test value bets endpoint."""
    
    def test_get_value_bets(self, client):
        """Test getting value bets."""
        response = client.get("/api/v2/value-bets")
        
        # May return 200 with empty list or 503 if odds service unavailable
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_503_SERVICE_UNAVAILABLE
        ]
        
        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            assert isinstance(data, list)
            
            if len(data) > 0:
                bet = data[0]
                assert "player1" in bet
                assert "player2" in bet
                assert "surface" in bet
                assert "predicted_prob" in bet
                assert "market_prob" in bet
                assert "edge" in bet
                assert "recommended_bet" in bet
                assert "odds" in bet
                assert "tournament" in bet
    
    def test_get_value_bets_with_min_edge(self, client):
        """Test filtering value bets by minimum edge."""
        response = client.get("/api/v2/value-bets?min_edge=0.10")
        
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_503_SERVICE_UNAVAILABLE
        ]
        
        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            
            # All bets should have edge >= 0.10
            for bet in data:
                assert bet["edge"] >= 0.10
    
    def test_get_value_bets_filtered_by_tour(self, client):
        """Test filtering value bets by tour."""
        response = client.get("/api/v2/value-bets?tour=atp")
        
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_503_SERVICE_UNAVAILABLE
        ]


class TestCacheEndpoints:
    """Test cache management endpoints."""
    
    def test_get_cache_status(self, client):
        """Test getting cache status."""
        response = client.get("/api/v2/cache/status")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert "enabled" in data
        assert "size" in data
        assert "ttl_seconds" in data
        assert isinstance(data["enabled"], bool)
        assert isinstance(data["size"], int)
        assert isinstance(data["ttl_seconds"], int)
    
    def test_clear_cache(self, client):
        """Test clearing cache."""
        response = client.delete("/api/v2/cache/clear")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert "message" in data
        assert "cleared" in data["message"].lower()


class TestDevelopmentEndpoints:
    """Test development/admin endpoints."""
    
    def test_reset_endpoint(self, client):
        """Test reset endpoint."""
        response = client.post("/api/v2/reset")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert "message" in data
        assert "container" in data["message"].lower()


class TestErrorHandling:
    """Test API error handling."""
    
    def test_404_for_invalid_endpoint(self, client):
        """Test that invalid endpoints return 404."""
        response = client.get("/api/v2/invalid-endpoint")
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_method_not_allowed(self, client):
        """Test that wrong HTTP methods return 405."""
        response = client.post("/api/v2/ratings")
        
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


class TestResponseHeaders:
    """Test API response headers."""
    
    def test_cors_headers(self, client):
        """Test that CORS headers are present."""
        # Send request with Origin header to trigger CORS
        response = client.get("/api/v2/health", headers={"Origin": "http://localhost:3000"})
        
        # CORS middleware should add these headers
        assert "access-control-allow-origin" in response.headers
    
    def test_content_type_json(self, client):
        """Test that API endpoints return JSON."""
        response = client.get("/api/v2/health")
        
        assert "application/json" in response.headers["content-type"]


class TestQueryParameterValidation:
    """Test query parameter validation."""
    
    def test_negative_limit_rejected(self, client):
        """Test that negative limit is rejected."""
        response = client.get("/api/v2/ratings?limit=-1")
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_limit_too_large_accepted(self, client):
        """Test that very large limit is handled."""
        response = client.get("/api/v2/ratings?limit=10000")
        
        # Should accept but may cap internally
        assert response.status_code == status.HTTP_200_OK
    
    def test_invalid_surface_rejected(self, client):
        """Test that invalid surface is rejected."""
        response = client.get("/api/v2/ratings?surface=invalid")
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY



