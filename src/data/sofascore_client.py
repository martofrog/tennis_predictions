"""
SofaScore API Client for Real-Time Tennis Match Results

Provides access to live and recent tennis match data from SofaScore.
Handles rate limiting, retries, and data conversion to Jeff Sackmann format.

IMPORTANT NOTES:
- SofaScore has anti-bot protection (403 errors are common)
- For production use, consider:
  1. Using a proxy service (e.g., ScraperAPI, Bright Data)
  2. Implementing browser automation (Selenium/Playwright)
  3. Using official APIs where available
  4. Rate limiting to 10-20 requests per minute
  
- This client works best when:
  1. Used sparingly (not in tight loops)
  2. Rate limited appropriately
  3. Combined with fallback data sources
"""

import requests
import time
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import pandas as pd
from pathlib import Path

logger = logging.getLogger(__name__)


class SofaScoreClient:
    """Client for fetching tennis match data from SofaScore API."""
    
    BASE_URL = "https://www.sofascore.com/api/v1"
    
    # Sport IDs
    TENNIS_SPORT_ID = 5
    
    # Tournament category IDs (ATP/WTA)
    ATP_CATEGORY_ID = 3  # ATP
    WTA_CATEGORY_ID = 4  # WTA
    
    def __init__(self, requests_per_minute: int = 20):
        """
        Initialize SofaScore client.
        
        Args:
            requests_per_minute: Rate limit for API requests
        """
        self.requests_per_minute = requests_per_minute
        self.min_request_interval = 60.0 / requests_per_minute
        self.last_request_time = 0
        
        # Headers to mimic browser requests
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': 'https://www.sofascore.com/',
            'Origin': 'https://www.sofascore.com',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin'
        }
        
        # Session for connection pooling and cookie persistence
        self.session = requests.Session()
        self.session.headers.update(self.headers)
    
    def _rate_limit(self):
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_request_interval:
            sleep_time = self.min_request_interval - elapsed
            time.sleep(sleep_time)
        self.last_request_time = time.time()
    
    def _make_request(self, endpoint: str, max_retries: int = 3) -> Optional[Dict[str, Any]]:
        """
        Make a rate-limited API request with retries.
        
        Args:
            endpoint: API endpoint (without base URL)
            max_retries: Maximum number of retry attempts
            
        Returns:
            JSON response or None if failed
        """
        url = f"{self.BASE_URL}/{endpoint}"
        
        for attempt in range(max_retries):
            try:
                self._rate_limit()
                response = self.session.get(url, timeout=15)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 429:  # Rate limited
                    wait_time = 60 * (attempt + 1)
                    logger.warning(f"Rate limited, waiting {wait_time}s before retry {attempt + 1}/{max_retries}")
                    time.sleep(wait_time)
                elif e.response.status_code == 404:
                    logger.debug(f"Resource not found: {endpoint}")
                    return None
                elif e.response.status_code == 403:
                    logger.warning(f"Access forbidden (403) - SofaScore anti-bot protection triggered")
                    logger.warning(f"This usually means: 1) Too many requests, 2) IP blocked, or 3) Captcha required")
                    return None
                else:
                    logger.error(f"HTTP error {e.response.status_code}: {e}")
                    if attempt < max_retries - 1:
                        time.sleep(5 * (attempt + 1))
            except Exception as e:
                logger.error(f"Request failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(5 * (attempt + 1))
        
        return None
    
    def get_matches_by_date(self, date: datetime, tour: str = "atp") -> List[Dict[str, Any]]:
        """
        Get all matches for a specific date and tour.
        
        Args:
            date: Date to fetch matches for
            tour: 'atp' or 'wta'
            
        Returns:
            List of match dictionaries
        """
        date_str = date.strftime("%Y-%m-%d")
        category_id = self.ATP_CATEGORY_ID if tour.lower() == "atp" else self.WTA_CATEGORY_ID
        
        # Get scheduled events for the date
        endpoint = f"sport/tennis/scheduled-events/{date_str}"
        data = self._make_request(endpoint)
        
        if not data or 'events' not in data:
            logger.debug(f"No events found for {date_str}")
            return []
        
        matches = []
        for event in data['events']:
            try:
                # Filter by tour (ATP/WTA)
                tournament = event.get('tournament', {})
                category = tournament.get('category', {})
                
                if category.get('id') != category_id:
                    continue
                
                # Only include completed matches
                status = event.get('status', {})
                if status.get('type') != 'finished':
                    continue
                
                match_info = self._parse_match(event)
                if match_info:
                    matches.append(match_info)
                    
            except Exception as e:
                logger.warning(f"Failed to parse match: {e}")
                continue
        
        return matches
    
    def get_recent_matches(self, days: int = 7, tour: str = "atp") -> List[Dict[str, Any]]:
        """
        Get matches from the last N days.
        
        Args:
            days: Number of days to look back
            tour: 'atp' or 'wta'
            
        Returns:
            List of match dictionaries
        """
        all_matches = []
        today = datetime.now()
        
        for day_offset in range(days):
            date = today - timedelta(days=day_offset)
            logger.info(f"Fetching {tour.upper()} matches for {date.strftime('%Y-%m-%d')}")
            
            matches = self.get_matches_by_date(date, tour)
            all_matches.extend(matches)
            
            if matches:
                logger.info(f"  Found {len(matches)} completed matches")
        
        return all_matches
    
    def _parse_match(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse a SofaScore event into our match format.
        
        Args:
            event: SofaScore event dictionary
            
        Returns:
            Parsed match dictionary or None if invalid
        """
        try:
            # Extract basic info
            home_team = event.get('homeTeam', {})
            away_team = event.get('awayTeam', {})
            tournament = event.get('tournament', {})
            
            # Determine winner/loser
            home_score = event.get('homeScore', {})
            away_score = event.get('awayScore', {})
            
            # Get set scores
            home_sets = home_score.get('display', 0)
            away_sets = away_score.get('display', 0)
            
            if home_sets > away_sets:
                winner_name = home_team.get('name', '')
                loser_name = away_team.get('name', '')
                winner_score_obj = home_score
                loser_score_obj = away_score
            else:
                winner_name = away_team.get('name', '')
                loser_name = home_team.get('name', '')
                winner_score_obj = away_score
                loser_score_obj = home_score
            
            # Skip if no valid names
            if not winner_name or not loser_name:
                return None
            
            # Skip doubles (names with '/')
            if '/' in winner_name or '/' in loser_name:
                return None
            
            # Parse date
            start_timestamp = event.get('startTimestamp')
            if start_timestamp:
                match_date = datetime.fromtimestamp(start_timestamp)
                tourney_date = match_date.strftime('%Y%m%d')
            else:
                tourney_date = datetime.now().strftime('%Y%m%d')
            
            # Build score string
            score_parts = []
            periods = event.get('homeScore', {}).get('period1')
            if periods:
                for i in range(1, 6):  # Up to 5 sets
                    home_set = event.get('homeScore', {}).get(f'period{i}')
                    away_set = event.get('awayScore', {}).get(f'period{i}')
                    
                    if home_set is not None and away_set is not None:
                        if home_sets > away_sets:
                            score_parts.append(f"{home_set}-{away_set}")
                        else:
                            score_parts.append(f"{away_set}-{home_set}")
            
            score = " ".join(score_parts) if score_parts else ""
            
            # Determine surface (default to Hard if not specified)
            surface = tournament.get('groundType', 'Hard')
            if surface:
                surface = surface.capitalize()
            else:
                surface = 'Hard'
            
            return {
                'tourney_date': tourney_date,
                'tourney_name': tournament.get('name', ''),
                'surface': surface,
                'winner_name': winner_name,
                'loser_name': loser_name,
                'score': score,
                'round': event.get('roundInfo', {}).get('name', ''),
                'best_of': 3  # Most ATP/WTA matches are best of 3
            }
            
        except Exception as e:
            logger.warning(f"Failed to parse match: {e}")
            return None
    
    def to_dataframe(self, matches: List[Dict[str, Any]]) -> pd.DataFrame:
        """
        Convert matches to DataFrame in Jeff Sackmann format.
        
        Args:
            matches: List of match dictionaries
            
        Returns:
            DataFrame with matches
        """
        if not matches:
            return pd.DataFrame()
        
        # Convert to Jeff Sackmann format
        records = []
        for match in matches:
            record = {
                'tourney_id': f"SS-{match['tourney_date']}-{match['tourney_name'].replace(' ', '')}",
                'tourney_name': match['tourney_name'],
                'surface': match['surface'],
                'draw_size': '',
                'tourney_level': '',
                'tourney_date': match['tourney_date'],
                'match_num': '',
                'winner_id': '',
                'winner_seed': '',
                'winner_entry': '',
                'winner_name': match['winner_name'],
                'winner_hand': '',
                'winner_ht': '',
                'winner_ioc': '',
                'winner_age': '',
                'winner_rank': '',
                'winner_rank_points': '',
                'loser_id': '',
                'loser_seed': '',
                'loser_entry': '',
                'loser_name': match['loser_name'],
                'loser_hand': '',
                'loser_ht': '',
                'loser_ioc': '',
                'loser_age': '',
                'loser_rank': '',
                'loser_rank_points': '',
                'score': match['score'],
                'best_of': match['best_of'],
                'round': match['round'],
                'minutes': '',
                'w_ace': '',
                'w_df': '',
                'w_svpt': '',
                'w_1stIn': '',
                'w_1stWon': '',
                'w_2ndWon': '',
                'w_SvGms': '',
                'w_bpSaved': '',
                'w_bpFaced': '',
                'l_ace': '',
                'l_df': '',
                'l_svpt': '',
                'l_1stIn': '',
                'l_1stWon': '',
                'l_2ndWon': '',
                'l_SvGms': '',
                'l_bpSaved': '',
                'l_bpFaced': '',
            }
            records.append(record)
        
        return pd.DataFrame(records)


def fetch_recent_matches_from_sofascore(days: int = 7, tour: str = "atp", 
                                       save_to_file: Optional[Path] = None) -> pd.DataFrame:
    """
    Fetch recent matches from SofaScore and convert to DataFrame.
    
    Args:
        days: Number of days to look back
        tour: 'atp' or 'wta'
        save_to_file: Optional path to save CSV file
        
    Returns:
        DataFrame with matches in Jeff Sackmann format
    """
    client = SofaScoreClient(requests_per_minute=20)
    matches = client.get_recent_matches(days=days, tour=tour)
    
    logger.info(f"Retrieved {len(matches)} matches from SofaScore")
    
    df = client.to_dataframe(matches)
    
    if save_to_file and not df.empty:
        save_to_file.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(save_to_file, index=False)
        logger.info(f"Saved {len(df)} matches to {save_to_file}")
    
    return df

