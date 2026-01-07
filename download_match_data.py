#!/usr/bin/env python3
"""
Script to download tennis match data from public sources.
Downloads ATP and WTA match data from Jeff Sackmann's tennis data repository.
"""

import os
import requests
import pandas as pd
from pathlib import Path
from typing import Optional
import argparse


class TennisDataDownloader:
    """Downloads tennis match data from public repositories."""
    
    BASE_URL = "https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master"
    WTA_BASE_URL = "https://raw.githubusercontent.com/JeffSackmann/tennis_wta/master"
    
    def __init__(self, data_dir: str = "data"):
        """
        Initialize the downloader.
        
        Args:
            data_dir: Directory to save downloaded data
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.atp_dir = self.data_dir / "atp"
        self.wta_dir = self.data_dir / "wta"
        self.atp_dir.mkdir(exist_ok=True)
        self.wta_dir.mkdir(exist_ok=True)
    
    def download_file(self, url: str, filepath: Path, silent_404: bool = True) -> bool:
        """
        Download a file from URL and save to filepath.
        
        Args:
            url: URL to download from
            filepath: Path to save the file
            silent_404: If True, don't print error message for 404s (they're expected)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            return True
        except requests.exceptions.HTTPError as e:
            # 404 errors are expected for years not yet published
            if e.response.status_code == 404 and silent_404:
                return False
            print(f"✗ Error downloading {url}: {e}")
            return False
        except requests.exceptions.RequestException as e:
            print(f"✗ Error downloading {url}: {e}")
            return False
    
    def download_matches(self, year: int, tour: str = "atp", verbose: bool = False, use_fallback: bool = True) -> Optional[pd.DataFrame]:
        """
        Download match data for a specific year and tour.
        Falls back to SofaScore if Jeff Sackmann data is unavailable.
        
        Args:
            year: Year to download (e.g., 2023)
            tour: 'atp' or 'wta'
            verbose: If True, print detailed messages
            use_fallback: If True, use SofaScore as fallback
            
        Returns:
            DataFrame with match data or None if download failed
        """
        base_url = self.BASE_URL if tour.lower() == "atp" else self.WTA_BASE_URL
        filename = f"{tour}_matches_{year}.csv"
        url = f"{base_url}/{filename}"
        
        if tour.lower() == "atp":
            save_dir = self.atp_dir
        else:
            save_dir = self.wta_dir
        
        filepath = save_dir / filename
        
        # Try Jeff Sackmann first
        if verbose:
            print(f"Attempting {tour.upper()} {year} from Jeff Sackmann...")
        
        if self.download_file(url, filepath, silent_404=not verbose):
            try:
                df = pd.read_csv(filepath)
                if verbose:
                    print(f"✓ Loaded {len(df)} matches from {filename}")
                return df
            except Exception as e:
                if verbose:
                    print(f"✗ Error reading CSV: {e}")
        
        # If Jeff Sackmann failed and fallback is enabled, try SofaScore
        if use_fallback:
            if verbose:
                print(f"Jeff Sackmann data not available, trying SofaScore fallback...")
            return self.download_matches_from_sofascore(year, tour)
        else:
            return None
    
    def download_matches_from_sofascore(self, year: int, tour: str = "atp") -> Optional[pd.DataFrame]:
        """
        Download match data from SofaScore as fallback for missing historical data.
        Fetches day-by-day for the entire year.
        
        Args:
            year: Year to download
            tour: 'atp' or 'wta'
            
        Returns:
            DataFrame with match data in Jeff Sackmann format, or None if failed
        """
        import time
        from datetime import datetime, timedelta
        
        print(f"  → Fallback: Fetching {tour.upper()} {year} from SofaScore...")
        
        all_matches = []
        start_date = datetime(year, 1, 1)
        end_date = min(datetime(year, 12, 31), datetime.now())  # Don't go beyond today
        
        current_date = start_date
        days_processed = 0
        days_with_matches = 0
        
        while current_date <= end_date:
            date_str = current_date.strftime("%Y-%m-%d")
            
            try:
                url = f"https://www.sofascore.com/api/v1/sport/tennis/scheduled-events/{date_str}"
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                }
                
                response = requests.get(url, headers=headers, timeout=10)
                response.raise_for_status()
                data = response.json()
                
                events = data.get("events", [])
                day_matches = 0
                
                for event in events:
                    # Only finished matches
                    if event.get("status", {}).get("type") != "finished":
                        continue
                    
                    match_data = self._parse_sofascore_event(event, tour, date_str)
                    if match_data:
                        all_matches.append(match_data)
                        day_matches += 1
                
                if day_matches > 0:
                    days_with_matches += 1
                
                days_processed += 1
                
                # Progress indicator every 30 days
                if days_processed % 30 == 0:
                    total_days = (end_date - start_date).days + 1
                    print(f"    Progress: {days_processed}/{total_days} days | "
                          f"{len(all_matches)} matches found")
                
                # Rate limiting: sleep 0.5 seconds between requests
                time.sleep(0.5)
                
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 429:  # Too many requests
                    print(f"    Rate limited, waiting 60 seconds...")
                    time.sleep(60)
                    continue
                # Skip other HTTP errors
            except Exception:
                # Skip days with errors
                pass
            
            current_date += timedelta(days=1)
        
        if all_matches:
            df = pd.DataFrame(all_matches)
            print(f"  ✓ SofaScore: Retrieved {len(all_matches)} matches from {days_with_matches} days")
            
            # Save to file
            if tour.lower() == "atp":
                save_dir = self.atp_dir
            else:
                save_dir = self.wta_dir
            
            filename = f"{tour}_matches_{year}.csv"
            filepath = save_dir / filename
            
            df.to_csv(filepath, index=False)
            print(f"  ✓ Saved to {filepath}")
            
            return df
        else:
            print(f"  ✗ SofaScore: No data retrieved for {tour.upper()} {year}")
            return None
    
    def _parse_sofascore_event(self, event: dict, tour: str, date_str: str) -> Optional[dict]:
        """
        Parse SofaScore event into Jeff Sackmann CSV format.
        
        Args:
            event: SofaScore event data
            tour: 'atp' or 'wta'
            date_str: Date in YYYY-MM-DD format
            
        Returns:
            Dictionary with match data in Jeff Sackmann format, or None if should be skipped
        """
        # Get player names
        player1 = event.get("homeTeam", {}).get("name", "")
        player2 = event.get("awayTeam", {}).get("name", "")
        
        # Skip doubles (names containing '/')
        if '/' in player1 or '/' in player2:
            return None
        
        # Skip if players are empty
        if not player1 or not player2:
            return None
        
        # Get scores
        home_score = event.get("homeScore", {})
        away_score = event.get("awayScore", {})
        
        # Parse sets (SofaScore uses period1, period2, etc.)
        sets = []
        for i in range(1, 6):  # Up to 5 sets
            p1_set = home_score.get(f"period{i}")
            p2_set = away_score.get(f"period{i}")
            if p1_set is not None and p2_set is not None:
                sets.append(f"{p1_set}-{p2_set}")
        
        if not sets:
            return None  # No score data
        
        score = " ".join(sets)
        
        # Determine winner
        winner_code = event.get("winnerCode")
        if winner_code == 1:
            winner_name = player1
            loser_name = player2
        elif winner_code == 2:
            winner_name = player2
            loser_name = player1
        else:
            return None  # No clear winner
        
        # Get tournament info
        tournament_name = event.get("tournament", {}).get("name", "")
        tournament_id = event.get("tournament", {}).get("uniqueTournament", {}).get("id", "")
        
        # Map surface (1=Hard, 2=Clay, 3=Grass, 4=Carpet)
        surface_id = event.get("groundType", "")
        surface_map = {"1": "Hard", "2": "Clay", "3": "Grass", "4": "Carpet"}
        surface = surface_map.get(str(surface_id), "Hard")
        
        # Get round info
        round_name = event.get("roundInfo", {}).get("name", "")
        
        # Convert date format YYYY-MM-DD to YYYYMMDD (Jeff Sackmann format)
        tourney_date = date_str.replace("-", "")
        
        # Build match record in Jeff Sackmann format
        # Include all standard columns, even if empty
        return {
            "tourney_id": f"SS-{tournament_id}-{tourney_date}",
            "tourney_name": tournament_name,
            "surface": surface,
            "draw_size": "",
            "tourney_level": "",
            "tourney_date": tourney_date,
            "match_num": "",
            "winner_id": "",
            "winner_seed": "",
            "winner_entry": "",
            "winner_name": winner_name,
            "winner_hand": "",
            "winner_ht": "",
            "winner_ioc": "",
            "winner_age": "",
            "loser_id": "",
            "loser_seed": "",
            "loser_entry": "",
            "loser_name": loser_name,
            "loser_hand": "",
            "loser_ht": "",
            "loser_ioc": "",
            "loser_age": "",
            "score": score,
            "best_of": "3",
            "round": round_name,
            "minutes": "",
            "w_ace": "",
            "w_df": "",
            "w_svpt": "",
            "w_1stIn": "",
            "w_1stWon": "",
            "w_2ndWon": "",
            "w_SvGms": "",
            "w_bpSaved": "",
            "w_bpFaced": "",
            "l_ace": "",
            "l_df": "",
            "l_svpt": "",
            "l_1stIn": "",
            "l_1stWon": "",
            "l_2ndWon": "",
            "l_SvGms": "",
            "l_bpSaved": "",
            "l_bpFaced": "",
            "winner_rank": "",
            "winner_rank_points": "",
            "loser_rank": "",
            "loser_rank_points": "",
        }
    
    def download_multiple_years(self, start_year: int, end_year: int, tour: str = "atp", verbose: bool = True) -> dict:
        """
        Download match data for multiple years.
        
        Args:
            start_year: Starting year
            end_year: Ending year (inclusive)
            tour: 'atp' or 'wta'
            verbose: If True, print detailed messages
            
        Returns:
            Dictionary mapping year to DataFrame
        """
        data = {}
        for year in range(start_year, end_year + 1):
            df = self.download_matches(year, tour, verbose=verbose)
            if df is not None:
                data[year] = df
        return data
    
    def download_recent_matches(self, years: int = 5, tour: str = "atp", verbose: bool = True) -> dict:
        """
        Download match data for recent years.
        
        Args:
            years: Number of recent years to download
            tour: 'atp' or 'wta'
            verbose: If True, print detailed messages
            
        Returns:
            Dictionary mapping year to DataFrame
        """
        from datetime import datetime
        current_year = datetime.now().year
        start_year = current_year - years + 1
        return self.download_multiple_years(start_year, current_year, tour, verbose=verbose)


def main():
    parser = argparse.ArgumentParser(description="Download tennis match data")
    parser.add_argument(
        "--years",
        type=int,
        default=5,
        help="Number of recent years to download (default: 5)"
    )
    parser.add_argument(
        "--tour",
        choices=["atp", "wta", "both"],
        default="atp",
        help="Tour to download: atp, wta, or both (default: atp)"
    )
    parser.add_argument(
        "--start-year",
        type=int,
        help="Start year (if specified, overrides --years)"
    )
    parser.add_argument(
        "--end-year",
        type=int,
        help="End year (if specified, overrides --years)"
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default="data",
        help="Directory to save data (default: data)"
    )
    
    args = parser.parse_args()
    
    downloader = TennisDataDownloader(data_dir=args.data_dir)
    
    tours = ["atp", "wta"] if args.tour == "both" else [args.tour]
    
    # Smart detection: If --years looks like a specific year (4-digit >= 1900), treat it as such
    if not args.start_year and not args.end_year and args.years >= 1900:
        print(f"📅 Detected specific year: {args.years}")
        print(f"   (Use --years 5 to download last 5 years, or --start-year/--end-year for range)\n")
        args.start_year = args.years
        args.end_year = args.years
    
    for tour in tours:
        print(f"\n{'='*60}")
        print(f"Downloading {tour.upper()} match data")
        print(f"{'='*60}\n")
        
        if args.start_year and args.end_year:
            data = downloader.download_multiple_years(args.start_year, args.end_year, tour)
        else:
            data = downloader.download_recent_matches(args.years, tour)
        
        if data:
            total_matches = sum(len(df) for df in data.values())
            print(f"\n✓ Successfully downloaded {total_matches} matches across {len(data)} years")
        else:
            print(f"\n✗ Failed to download {tour} data")


if __name__ == "__main__":
    main()
