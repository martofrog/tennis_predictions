"""
SofaScore Data Adapter

Fetches real-time tennis match data from SofaScore API for both ATP and WTA.
Converts to CSV format compatible with Jeff Sackmann's structure.
"""

import requests
import pandas as pd
from typing import Optional, List, Dict, Tuple
from datetime import datetime, timedelta
import logging
import time

logger = logging.getLogger(__name__)


class SofaScoreAdapter:
    """Adapter for SofaScore tennis data API."""
    
    BASE_URL = "https://api.sofascore.com/api/v1"
    
    def __init__(self):
        """Initialize SofaScore adapter."""
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9'
        })
    
    def get_matches_by_date(
        self,
        date: datetime,
        tour: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Get tennis matches for a specific date.
        
        Args:
            date: Date to fetch matches for
            tour: Optional filter ('atp' or 'wta')
            
        Returns:
            DataFrame with matches in Jeff Sackmann CSV format
        """
        date_str = date.strftime('%Y-%m-%d')
        url = f"{self.BASE_URL}/sport/tennis/scheduled-events/{date_str}"
        
        try:
            logger.info(f"Fetching matches from SofaScore for {date_str}")
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            # Parse events
            matches = []
            if 'events' in data:
                for event in data['events']:
                    match = self._parse_event(event)
                    if match:
                        matches.append(match)
            
            if not matches:
                logger.info(f"No matches found for {date_str}")
                return pd.DataFrame()
            
            df = pd.DataFrame(matches)
            
            # Filter by tour if specified
            if tour:
                df = df[df['tour'].str.lower() == tour.lower()]
            
            logger.info(f"Found {len(df)} matches for {date_str} (tour={tour})")
            return df
            
        except Exception as e:
            logger.error(f"Error fetching from SofaScore: {e}")
            return pd.DataFrame()
    
    def get_yesterday_matches(self, tour: Optional[str] = None) -> pd.DataFrame:
        """Get matches from yesterday."""
        yesterday = datetime.now() - timedelta(days=1)
        return self.get_matches_by_date(yesterday, tour)
    
    def get_recent_matches(
        self,
        days_back: int = 7,
        tour: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Get matches from the last N days.
        
        Args:
            days_back: Number of days to look back
            tour: Optional filter ('atp' or 'wta')
            
        Returns:
            Combined DataFrame of all matches
        """
        all_matches = []
        
        for i in range(days_back):
            date = datetime.now() - timedelta(days=i)
            df = self.get_matches_by_date(date, tour)
            if not df.empty:
                all_matches.append(df)
            
            # Be nice to the API
            time.sleep(0.5)
        
        if not all_matches:
            return pd.DataFrame()
        
        return pd.concat(all_matches, ignore_index=True)
    
    def _parse_event(self, event: Dict) -> Optional[Dict]:
        """
        Parse a SofaScore event into Jeff Sackmann CSV format.
        
        Args:
            event: Event data from SofaScore API
            
        Returns:
            Dictionary with match data in standardized format
        """
        try:
            # Only process finished matches
            status = event.get('status', {})
            if status.get('type') != 'finished':
                return None
            
            # Extract basic info
            tournament = event.get('tournament', {})
            season = event.get('season', {})
            home_team = event.get('homeTeam', {})
            away_team = event.get('awayTeam', {})
            
            # Determine winner/loser
            winner_code = event.get('winnerCode')
            
            if winner_code == 1:  # Home team won
                winner_name = home_team.get('name', '')
                loser_name = away_team.get('name', '')
            elif winner_code == 2:  # Away team won
                winner_name = away_team.get('name', '')
                loser_name = home_team.get('name', '')
            else:
                # Fallback to score comparison
                home_score = event.get('homeScore', {}).get('current', 0)
                away_score = event.get('awayScore', {}).get('current', 0)
                
                if home_score > away_score:
                    winner_name = home_team.get('name', '')
                    loser_name = away_team.get('name', '')
                else:
                    winner_name = away_team.get('name', '')
                    loser_name = home_team.get('name', '')
            
            # Skip if no valid names
            if not winner_name or not loser_name:
                return None
            
            # Extract tournament info
            tourney_name = tournament.get('name', '')
            surface = self._get_surface(tournament)
            
            # Determine tour (ATP/WTA)
            tour = self._determine_tour(tournament, event)
            
            # Format date
            start_timestamp = event.get('startTimestamp', 0)
            date = datetime.fromtimestamp(start_timestamp)
            tourney_date = int(date.strftime('%Y%m%d'))
            
            # Format score
            score = self._format_score(event, winner_code)
            
            return {
                'tourney_id': f"{season.get('year', '')}-{tournament.get('id', '')}",
                'tourney_name': tourney_name,
                'surface': surface,
                'tourney_date': tourney_date,
                'match_num': event.get('id'),
                'winner_name': winner_name,
                'loser_name': loser_name,
                'score': score,
                'round': event.get('roundInfo', {}).get('name', ''),
                'tour': tour,
                'date': date.strftime('%Y-%m-%d'),
                'year': season.get('year', date.year)
            }
            
        except Exception as e:
            logger.debug(f"Error parsing event: {e}")
            return None
    
    def _format_score(self, event: Dict, winner_code: int) -> str:
        """
        Format score string from event data.
        Winner's score comes first in standard format.
        """
        try:
            home_score = event.get('homeScore', {})
            away_score = event.get('awayScore', {})
            
            scores = []
            
            # Get set scores (up to 5 sets)
            for i in range(1, 6):
                home_set = home_score.get(f'period{i}')
                away_set = away_score.get(f'period{i}')
                
                if home_set is not None and away_set is not None:
                    # If home team won, format as home-away
                    # If away team won, format as away-home (winner first)
                    if winner_code == 1:  # Home won
                        scores.append(f"{home_set}-{away_set}")
                    else:  # Away won
                        scores.append(f"{away_set}-{home_set}")
            
            return ' '.join(scores) if scores else ''
            
        except Exception:
            return ''
    
    def _get_surface(self, tournament: Dict) -> str:
        """Determine court surface from tournament data."""
        ground = tournament.get('groundType', '')
        
        surface_map = {
            'Hard': 'Hard',
            'Clay': 'Clay',
            'Grass': 'Grass',
            'Carpet': 'Carpet',
            'hard': 'Hard',
            'clay': 'Clay',
            'grass': 'Grass',
            'carpet': 'Carpet'
        }
        
        return surface_map.get(ground, 'Hard')
    
    def _determine_tour(self, tournament: Dict, event: Dict) -> str:
        """Determine if match is ATP or WTA."""
        # Check tournament category
        category = tournament.get('category', {})
        cat_name = category.get('name', '').lower()
        cat_slug = category.get('slug', '').lower()
        
        if 'wta' in cat_name or 'wta' in cat_slug:
            return 'wta'
        elif 'atp' in cat_name or 'atp' in cat_slug:
            return 'atp'
        
        # Check unique tournament name
        unique_tournament = tournament.get('uniqueTournament', {})
        ut_name = unique_tournament.get('name', '').lower()
        
        if 'wta' in ut_name or 'women' in ut_name:
            return 'wta'
        elif 'atp' in ut_name:
            return 'atp'
        
        # Default to ATP for mixed/unknown
        return 'atp'
    
    def save_to_csv(self, df: pd.DataFrame, filepath: str):
        """
        Save matches to CSV file in Jeff Sackmann format.
        
        Args:
            df: DataFrame with match data
            filepath: Path to save CSV file
        """
        if df.empty:
            logger.warning("No data to save")
            return
        
        # Ensure column order matches Sackmann format
        column_order = [
            'tourney_id', 'tourney_name', 'surface', 'tourney_date',
            'match_num', 'winner_name', 'loser_name', 'score', 'round',
            'tour', 'date', 'year'
        ]
        
        # Select available columns in order
        df_out = df[[col for col in column_order if col in df.columns]]
        
        # Save to CSV
        df_out.to_csv(filepath, index=False)
        logger.info(f"Saved {len(df_out)} matches to {filepath}")


# Convenience functions
def get_yesterday_matches_from_sofascore(tour: Optional[str] = None) -> pd.DataFrame:
    """Get yesterday's matches from SofaScore."""
    adapter = SofaScoreAdapter()
    return adapter.get_yesterday_matches(tour)


def update_csv_with_sofascore(
    csv_path: str,
    days_back: int = 7,
    tour: Optional[str] = None
) -> int:
    """
    Update existing CSV file with recent matches from SofaScore.
    
    Args:
        csv_path: Path to CSV file to update
        days_back: How many days back to fetch
        tour: Optional tour filter ('atp' or 'wta')
        
    Returns:
        Number of new matches added
    """
    from pathlib import Path
    
    adapter = SofaScoreAdapter()
    
    # Load existing CSV
    csv_file = Path(csv_path)
    try:
        df_existing = pd.read_csv(csv_path)
        logger.info(f"Loaded {len(df_existing)} existing matches from {csv_path}")
    except FileNotFoundError:
        df_existing = pd.DataFrame()
        logger.info(f"Creating new CSV file: {csv_path}")
        # Create directory if needed
        csv_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Fetch recent matches
    df_new = adapter.get_recent_matches(days_back, tour)
    
    if df_new.empty:
        logger.info("No new matches fetched from SofaScore")
        return 0
    
    # Combine and deduplicate
    if not df_existing.empty:
        # Track which matches are truly new (not in existing data)
        df_combined = pd.concat([df_existing, df_new], ignore_index=True)
        
        # Remove duplicates based on key fields, keeping last (most recent data)
        before_count = len(df_combined)
        df_combined = df_combined.drop_duplicates(
            subset=['tourney_date', 'winner_name', 'loser_name'],
            keep='last'
        )
        after_count = len(df_combined)
        duplicates_removed = before_count - after_count
        
        # Calculate truly new matches: final count minus original count
        new_matches = max(0, after_count - len(df_existing))
        
        if duplicates_removed > 0:
            logger.info(f"Removed {duplicates_removed} duplicate matches")
        logger.info(f"Net new matches: {new_matches}")
    else:
        df_combined = df_new
        new_matches = len(df_new)
    
    # Sort by date
    if 'tourney_date' in df_combined.columns:
        df_combined = df_combined.sort_values('tourney_date')
    
    # Save
    adapter.save_to_csv(df_combined, csv_path)
    logger.info(f"Added {new_matches} new matches to {csv_path}")
    
    return new_matches

