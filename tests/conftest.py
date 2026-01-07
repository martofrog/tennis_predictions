"""
Pytest configuration and shared fixtures for tennis predictions tests.
"""

import pytest
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any
import tempfile
import shutil
import json

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from fastapi.testclient import TestClient
from src.api.main import app
from src.prediction.elo_rating_system import TennisEloRatingSystem
from src.infrastructure.repositories import JsonRatingRepository
from src.services.dependency_container import get_container, reset_container


@pytest.fixture
def client():
    """FastAPI test client."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def temp_data_dir():
    """Create a temporary data directory for tests."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_ratings_data() -> Dict[str, Any]:
    """Sample ratings data for testing."""
    return {
        "Novak Djokovic": {
            "rating": 2500,
            "surface_ratings": {
                "hard": 2550,
                "clay": 2480,
                "grass": 2520
            },
            "last_match_date": "2024-12-15T00:00:00"
        },
        "Carlos Alcaraz": {
            "rating": 2400,
            "surface_ratings": {
                "hard": 2420,
                "clay": 2450,
                "grass": 2380
            },
            "last_match_date": "2024-12-10T00:00:00"
        },
        "Jannik Sinner": {
            "rating": 2380,
            "surface_ratings": {
                "hard": 2400,
                "clay": 2360,
                "grass": 2370
            },
            "last_match_date": "2024-12-12T00:00:00"
        }
    }


@pytest.fixture
def rating_system_with_data(temp_data_dir, sample_ratings_data):
    """Elo rating system with sample data."""
    ratings_file = temp_data_dir / "ratings.json"
    
    # Save sample ratings
    with open(ratings_file, 'w') as f:
        json.dump(sample_ratings_data, f)
    
    # Create repository and rating system
    repository = JsonRatingRepository(str(ratings_file))
    rating_system = TennisEloRatingSystem(
        repository=repository,
        default_rating=1500,
        k_factor=32,
        surface_advantage=50
    )
    
    return rating_system


@pytest.fixture
def clean_rating_system(temp_data_dir):
    """Fresh Elo rating system with no data."""
    ratings_file = temp_data_dir / "ratings.json"
    repository = JsonRatingRepository(str(ratings_file))
    rating_system = TennisEloRatingSystem(
        repository=repository,
        default_rating=1500,
        k_factor=32,
        surface_advantage=50
    )
    return rating_system


@pytest.fixture(autouse=True)
def reset_container_after_test():
    """Reset dependency container after each test."""
    yield
    reset_container()


@pytest.fixture
def sample_match_data():
    """Sample match data for testing."""
    return {
        "winner": "Novak Djokovic",
        "loser": "Carlos Alcaraz",
        "winner_score": "6-4 6-3",
        "loser_score": "4-6 3-6",
        "surface": "hard",
        "date": datetime(2024, 12, 15)
    }



