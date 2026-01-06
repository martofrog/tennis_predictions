"""
Daily Value Bets Script

Find today's value betting opportunities.
"""

import sys
from pathlib import Path
import logging

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.services.dependency_container import get_container
from src.core.constants import DEFAULT_MIN_EDGE, SportKey

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """Find and display today's value bets."""
    container = get_container()
    betting_service = container.betting_service()
    
    print("="*70)
    print("Tennis Value Bets - Today's Opportunities")
    print("="*70)
    
    # Get value bets for ATP
    print("\nATP Tour:")
    print("-"*70)
    try:
        atp_bets = betting_service.get_todays_value_bets(
            min_edge=DEFAULT_MIN_EDGE,
            sport=SportKey.TENNIS_ATP.value
        )
        
        if atp_bets:
            for bet in atp_bets:
                print(f"\nMatch: {bet.player1} vs {bet.player2}")
                print(f"  Surface: {bet.surface}")
                print(f"  Bet on: {bet.bet_on_player}")
                print(f"  Bookmaker: {bet.bookmaker}")
                print(f"  Odds: {bet.odds:.2f}")
                print(f"  Edge: {bet.edge_percentage:.2f}%")
                print(f"  Expected Value: {bet.expected_value_percentage:.2f}%")
                if bet.recommended_stake:
                    print(f"  Recommended Stake: {bet.recommended_stake*100:.2f}%")
                print(f"  Start Time: {bet.commence_time}")
        else:
            print("No value bets found for ATP matches today.")
    except Exception as e:
        print(f"Error fetching ATP value bets: {e}")
    
    # Get value bets for WTA
    print("\n\nWTA Tour:")
    print("-"*70)
    try:
        wta_bets = betting_service.get_todays_value_bets(
            min_edge=DEFAULT_MIN_EDGE,
            sport=SportKey.TENNIS_WTA.value
        )
        
        if wta_bets:
            for bet in wta_bets:
                print(f"\nMatch: {bet.player1} vs {bet.player2}")
                print(f"  Surface: {bet.surface}")
                print(f"  Bet on: {bet.bet_on_player}")
                print(f"  Bookmaker: {bet.bookmaker}")
                print(f"  Odds: {bet.odds:.2f}")
                print(f"  Edge: {bet.edge_percentage:.2f}%")
                print(f"  Expected Value: {bet.expected_value_percentage:.2f}%")
                if bet.recommended_stake:
                    print(f"  Recommended Stake: {bet.recommended_stake*100:.2f}%")
                print(f"  Start Time: {bet.commence_time}")
        else:
            print("No value bets found for WTA matches today.")
    except Exception as e:
        print(f"Error fetching WTA value bets: {e}")
    
    print("\n" + "="*70)


if __name__ == "__main__":
    main()
