"""
Predict tennis match outcomes using trained Elo ratings with surface adjustments.
"""

import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.services.dependency_container import get_container


def predict_match(
    player1: str,
    player2: str,
    surface: str = "hard",
    ratings_file: str = "data/ratings.json"
):
    """
    Predict match outcome between two players with surface consideration.
    
    Args:
        player1: Name of player 1
        player2: Name of player 2
        surface: Court surface ('hard', 'clay', 'grass')
        ratings_file: Path to ratings JSON file
    """
    container = get_container(ratings_file=ratings_file)
    rating_service = container.rating_service()
    
    prediction = rating_service.predict_match(player1, player2, surface)
    
    # Display results
    print("=" * 60)
    print("Tennis Match Prediction (Adjusted Elo with Surface Adjustments)")
    print("=" * 60)
    
    print(f"\n{player1:30s} vs {player2:30s}")
    print("-" * 60)
    print(f"{player1:30s} Rating: {prediction.player1_rating:7.2f}  Win Prob: {prediction.player1_win_probability*100:5.2f}%")
    print(f"{player2:30s} Rating: {prediction.player2_rating:7.2f}  Win Prob: {prediction.player2_win_probability*100:5.2f}%")
    print("=" * 60)
    
    # Prediction
    if prediction.player1_win_probability > prediction.player2_win_probability:
        print(f"\nPredicted Winner: {player1} ({prediction.player1_win_probability*100:.2f}%)")
    elif prediction.player2_win_probability > prediction.player1_win_probability:
        print(f"\nPredicted Winner: {player2} ({prediction.player2_win_probability*100:.2f}%)")
    else:
        print("\nPrediction: Too close to call (50/50)")
    
    print(f"\nSurface: {surface}")
    print(f"Surface Adjustment: {prediction.surface_adjustment} Elo points")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python predict.py <player1> <player2> [--surface hard|clay|grass]")
        print("\nExamples:")
        print("  python predict.py 'Novak Djokovic' 'Rafael Nadal' --surface clay")
        print("  python predict.py 'Serena Williams' 'Maria Sharapova' --surface hard")
        sys.exit(1)
    
    player1 = sys.argv[1]
    player2 = sys.argv[2]
    surface = "hard"  # Default
    
    if "--surface" in sys.argv:
        idx = sys.argv.index("--surface")
        if idx + 1 < len(sys.argv):
            surface = sys.argv[idx + 1].lower()
    
    predict_match(player1, player2, surface)
