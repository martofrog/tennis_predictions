"""
FlashScore Client for Real-Time Tennis Match Results

Uses Playwright browser automation to access match data from FlashScore.
FlashScore loads data dynamically with JavaScript, so we need a real browser.
"""

import time
import logging
import re
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import pandas as pd
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class FlashScoreClient:
    """Client for fetching tennis match data from FlashScore using Playwright."""
    
    BASE_URL = "https://www.flashscore.com"
    
    def __init__(self, requests_per_minute: int = 10, headless: bool = True):
        """
        Initialize FlashScore client with Playwright.
        
        Args:
            requests_per_minute: Rate limit for page requests
            headless: Whether to run browser in headless mode
        """
        self.requests_per_minute = requests_per_minute
        self.min_request_interval = 60.0 / requests_per_minute
        self.last_request_time = 0
        self.headless = headless
    
    def _rate_limit(self):
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_request_interval:
            sleep_time = self.min_request_interval - elapsed
            time.sleep(sleep_time)
        self.last_request_time = time.time()
    
    def _fetch_page_with_browser(self, url: str, wait_selector: str = None, max_retries: int = 2) -> Optional[str]:
        """
        Fetch page using Playwright browser automation.
        
        Args:
            url: URL to fetch
            wait_selector: Optional CSS selector to wait for
            max_retries: Maximum retry attempts
            
        Returns:
            Page HTML or None if failed
        """
        for attempt in range(max_retries):
            try:
                self._rate_limit()
                
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=self.headless)
                    context = browser.new_context(
                        viewport={'width': 1920, 'height': 1080},
                        user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
                    )
                    page = context.new_page()
                    
                    # Navigate to URL
                    page.goto(url, wait_until='domcontentloaded', timeout=30000)
                    
                    # Wait for content to load
                    if wait_selector:
                        try:
                            page.wait_for_selector(wait_selector, timeout=10000)
                        except PlaywrightTimeout:
                            logger.debug(f"Timeout waiting for selector: {wait_selector}")
                    else:
                        # Wait for network to be idle
                        page.wait_for_load_state('networkidle', timeout=10000)
                    
                    # Small additional wait for JS rendering
                    page.wait_for_timeout(2000)
                    
                    html = page.content()
                    browser.close()
                    return html
                    
            except Exception as e:
                logger.error(f"Browser request failed (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(5 * (attempt + 1))
        
        return None
    
    def get_matches_by_date(self, date: datetime, tour: str = "atp") -> List[Dict[str, Any]]:
        """
        Get all finished matches for a specific date.
        
        Args:
            date: Date to fetch matches for
            tour: 'atp' or 'wta'
            
        Returns:
            List of match dictionaries
        """
        # FlashScore uses date format YYYYMMDD
        date_str = date.strftime("%Y%m%d")
        
        # URL for tennis ATP results
        if tour.lower() == 'atp':
            url = f"{self.BASE_URL}/tennis/atp-singles/results/"
        else:
            url = f"{self.BASE_URL}/tennis/wta-singles/results/"
        
        logger.info(f"  Fetching {tour.upper()} from FlashScore (browser automation)...")
        
        # #region agent log
        import json; open('/Users/nmartorana/dev/playground/tennis_predictions/.cursor/debug.log', 'a').write(json.dumps({"sessionId":"debug-session","runId":"startup","hypothesisId":"H1,H5","location":"flashscore_client.py:151","message":"About to call _fetch_page_with_browser","data":{"url":url,"tour":tour},"timestamp":datetime.now().timestamp()*1000})+'\n')
        # #endregion
        
        html = self._fetch_page_with_browser(url, wait_selector='.sportName.tennis')
        
        # #region agent log
        import json; open('/Users/nmartorana/dev/playground/tennis_predictions/.cursor/debug.log', 'a').write(json.dumps({"sessionId":"debug-session","runId":"startup","hypothesisId":"H1,H5","location":"flashscore_client.py:160","message":"_fetch_page_with_browser completed","data":{"html_length":len(html) if html else 0,"success":html is not None},"timestamp":datetime.now().timestamp()*1000})+'\n')
        # #endregion
        
        if not html:
            logger.debug(f"No data retrieved for {date_str}")
            return []
        
        try:
            matches = self._parse_results_page(html, date, tour)
            return matches
        except Exception as e:
            logger.error(f"Failed to parse FlashScore results for {date_str}: {e}")
            return []
    
    def _parse_results_page(self, html: str, date: datetime, tour: str) -> List[Dict[str, Any]]:
        """
        Parse FlashScore results page HTML.
        
        Args:
            html: HTML content
            date: Match date
            tour: 'atp' or 'wta'
            
        Returns:
            List of match dictionaries
        """
        soup = BeautifulSoup(html, 'html.parser')
        matches = []
        
        # FlashScore structure: matches are in div elements with specific classes
        # Look for match containers
        match_elements = soup.find_all('div', class_=re.compile(r'event__match'))
        
        if not match_elements:
            # Try alternative structure
            match_elements = soup.find_all('div', attrs={'id': re.compile(r'^g_1_')})
        
        logger.info(f"Found {len(match_elements)} potential match elements")
        
        for element in match_elements:
            try:
                match_data = self._parse_match_element(element, date, tour)
                if match_data:
                    matches.append(match_data)
            except Exception as e:
                logger.debug(f"Failed to parse match element: {e}")
                continue
        
        return matches
    
    def _parse_match_element(self, element, date: datetime, tour: str) -> Optional[Dict[str, Any]]:
        """
        Parse a single match element from FlashScore HTML.
        
        Args:
            element: BeautifulSoup element
            date: Match date
            tour: Tournament tour type
            
        Returns:
            Match dictionary or None
        """
        try:
            # Extract player names
            participants = element.find_all(class_=re.compile(r'participant'))
            if len(participants) < 2:
                return None
            
            player1_elem = participants[0]
            player2_elem = participants[1]
            
            player1_name = player1_elem.get_text(strip=True) if player1_elem else None
            player2_name = player2_elem.get_text(strip=True) if player2_elem else None
            
            if not player1_name or not player2_name:
                return None
            
            # Skip doubles (names contain '/')
            if '/' in player1_name or '/' in player2_name:
                return None
            
            # Extract scores
            score_elements = element.find_all(class_=re.compile(r'score'))
            scores = [s.get_text(strip=True) for s in score_elements if s.get_text(strip=True)]
            
            if not scores or len(scores) < 2:
                return None
            
            # Determine winner (higher total score typically)
            # FlashScore shows scores for each player
            player1_sets = 0
            player2_sets = 0
            
            # Try to parse set scores
            score_parts = []
            for i in range(0, min(len(scores), 10), 2):  # Process pairs of scores
                if i+1 < len(scores):
                    p1_score = scores[i]
                    p2_score = scores[i+1]
                    
                    # Parse numeric scores
                    try:
                        p1_val = int(re.search(r'\d+', p1_score).group())
                        p2_val = int(re.search(r'\d+', p2_score).group())
                        
                        if p1_val > p2_val:
                            player1_sets += 1
                            score_parts.append(f"{p1_val}-{p2_val}")
                        else:
                            player2_sets += 1
                            score_parts.append(f"{p2_val}-{p1_val}")
                    except:
                        continue
            
            # Determine winner/loser
            if player1_sets > player2_sets:
                winner_name = player1_name
                loser_name = player2_name
            elif player2_sets > player1_sets:
                winner_name = player2_name
                loser_name = player1_name
            else:
                # Can't determine winner
                return None
            
            score_str = " ".join(score_parts) if score_parts else ""
            
            # Extract tournament name
            tournament_elem = element.find_previous(class_=re.compile(r'event__title'))
            if not tournament_elem:
                tournament_elem = element.find_previous('div', class_=re.compile(r'category'))
            
            tournament_name = tournament_elem.get_text(strip=True) if tournament_elem else "Unknown Tournament"
            
            # Filter by tour if possible (check tournament name)
            tour_upper = tour.upper()
            if tour_upper == 'ATP':
                # Skip if clearly WTA
                if any(keyword in tournament_name.upper() for keyword in ['WTA', 'WOMEN']):
                    return None
            elif tour_upper == 'WTA':
                # Skip if clearly ATP/men's
                if 'ATP' in tournament_name.upper() and 'WTA' not in tournament_name.upper():
                    return None
            
            return {
                'tourney_date': date.strftime('%Y%m%d'),
                'tourney_name': tournament_name,
                'surface': 'Hard',  # Default, not provided by FlashScore
                'winner_name': winner_name,
                'loser_name': loser_name,
                'score': score_str,
                'round': '',
                'best_of': 3
            }
            
        except Exception as e:
            logger.debug(f"Error parsing match element: {e}")
            return None
    
    def get_recent_matches(self, days: int = 7, tour: str = "atp") -> List[Dict[str, Any]]:
        """
        Get matches from the last N days.
        
        Args:
            days: Number of days to look back
            tour: 'atp' or 'wta'
            
        Returns:
            List of match dictionaries
        """
        # #region agent log
        import json; open('/Users/nmartorana/dev/playground/tennis_predictions/.cursor/debug.log', 'a').write(json.dumps({"sessionId":"debug-session","runId":"startup","hypothesisId":"H1","location":"flashscore_client.py:272","message":"get_recent_matches called","data":{"days":days,"tour":tour},"timestamp":datetime.now().timestamp()*1000})+'\n')
        # #endregion
        
        all_matches = []
        # Use real date 2025, not system date
        base_date = datetime(2025, 1, 7)
        
        for day_offset in range(days):
            date = base_date - timedelta(days=day_offset)
            # #region agent log
            import json; open('/Users/nmartorana/dev/playground/tennis_predictions/.cursor/debug.log', 'a').write(json.dumps({"sessionId":"debug-session","runId":"startup","hypothesisId":"H1,H5","location":"flashscore_client.py:284","message":"About to fetch matches for date","data":{"day_offset":day_offset,"date":date.strftime('%Y-%m-%d'),"tour":tour},"timestamp":datetime.now().timestamp()*1000})+'\n')
            # #endregion
            
            logger.info(f"Fetching {tour.upper()} matches for {date.strftime('%Y-%m-%d')}")
            
            matches = self.get_matches_by_date(date, tour)
            
            # #region agent log
            import json; open('/Users/nmartorana/dev/playground/tennis_predictions/.cursor/debug.log', 'a').write(json.dumps({"sessionId":"debug-session","runId":"startup","hypothesisId":"H1,H5","location":"flashscore_client.py:293","message":"Completed fetch for date","data":{"day_offset":day_offset,"date":date.strftime('%Y-%m-%d'),"matches_found":len(matches)},"timestamp":datetime.now().timestamp()*1000})+'\n')
            # #endregion
            
            all_matches.extend(matches)
            
            if matches:
                logger.info(f"  Found {len(matches)} matches")
        
        return all_matches
    
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
                'tourney_id': f"FS-{match['tourney_date']}-{match['tourney_name'].replace(' ', '')}",
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


def fetch_recent_matches_from_flashscore(days: int = 3, tour: str = "atp", 
                                         save_to_file: Optional[Path] = None) -> pd.DataFrame:
    """
    Fetch recent matches from FlashScore and convert to DataFrame.
    
    Note: Uses browser automation (slower than API calls).
    Limit to 3-5 days to avoid long processing times.
    
    Args:
        days: Number of days to look back (default: 3, max recommended: 5)
        tour: 'atp' or 'wta'
        save_to_file: Optional path to save CSV file
        
    Returns:
        DataFrame with matches in Jeff Sackmann format
    """
    # Lower rate limit for browser automation (slower)
    client = FlashScoreClient(requests_per_minute=6, headless=True)
    matches = client.get_recent_matches(days=days, tour=tour)
    
    logger.info(f"Retrieved {len(matches)} matches from FlashScore")
    
    df = client.to_dataframe(matches)
    
    if save_to_file and not df.empty:
        save_to_file.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(save_to_file, index=False)
        logger.info(f"Saved {len(df)} matches to {save_to_file}")
    
    return df

