"""
Example API Client

Demonstrates how to use the Tennis Predictions API.
"""

import requests
import json


def example_get_ratings():
    """Example: Get player ratings."""
    response = requests.get("http://localhost:8000/api/v2/ratings?sort_by=rating&surface=hard")
    ratings = response.json()
    print("Top 10 Players (Hard Court):")
    for i, rating in enumerate(ratings[:10], 1):
        print(f"{i}. {rating['player']}: {rating['rating']:.2f}")


def example_predict_match():
    """Example: Predict a match."""
    response = requests.get(
        "http://localhost:8000/api/v2/predict",
        params={
            "player1": "Novak Djokovic",
            "player2": "Rafael Nadal",
            "surface": "clay"
        }
    )
    prediction = response.json()
    print(f"\nPrediction: {prediction['player1']} vs {prediction['player2']}")
    print(f"Surface: {prediction['surface']}")
    print(f"Favorite: {prediction['favorite']}")
    print(f"Confidence: {prediction['confidence']*100:.2f}%")


def example_get_value_bets():
    """Example: Get value bets."""
    response = requests.get(
        "http://localhost:8000/api/v2/value-bets",
        params={
            "min_edge": 5.0,
            "sport": "tennis_atp"
        }
    )
    bets = response.json()
    print(f"\nFound {len(bets)} value bets:")
    for bet in bets:
        print(f"\n{bet['player1']} vs {bet['player2']}")
        print(f"  Bet on: {bet['bet_on_player']}")
        print(f"  Edge: {bet['edge_percentage']:.2f}%")
        print(f"  EV: {bet['expected_value_percentage']:.2f}%")


if __name__ == "__main__":
    print("Tennis Predictions API Examples")
    print("="*50)
    
    try:
        example_get_ratings()
        example_predict_match()
        example_get_value_bets()
    except requests.exceptions.ConnectionError:
        print("Error: Could not connect to API. Make sure the server is running:")
        print("  python run_api.py")
