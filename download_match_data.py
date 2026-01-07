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
        Falls back to tennis-data.co.uk, then FlashScore if Jeff Sackmann data is unavailable.
        
        Args:
            year: Year to download (e.g., 2023)
            tour: 'atp' or 'wta'
            verbose: If True, print detailed messages
            use_fallback: If True, use fallbacks (tennis-data.co.uk, then FlashScore)
            
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
        
        # If Jeff Sackmann failed and fallback is enabled
        if use_fallback:
            # Try tennis-data.co.uk
            if verbose:
                print(f"Jeff Sackmann data not available, trying tennis-data.co.uk fallback...")
            
            df = self.download_matches_from_tennis_data_co_uk(year, tour)
            if df is not None:
                return df
            
            # If tennis-data.co.uk also failed, try FlashScore for current year
            from datetime import datetime
            current_year = datetime.now().year
            
            # #region agent log
            import json; open('/Users/nmartorana/dev/playground/tennis_predictions/.cursor/debug.log', 'a').write(json.dumps({"sessionId":"debug-session","runId":"startup","hypothesisId":"H1,H4","location":"download_match_data.py:115","message":"Checking FlashScore fallback conditions","data":{"year":year,"current_year":current_year,"should_use_flashscore":year==current_year,"tour":tour},"timestamp":datetime.now().timestamp()*1000})+'\n')
            # #endregion
            
            if year == current_year:
                print(f"  → tennis-data.co.uk failed, trying FlashScore for current year {year}...")
                
                # #region agent log
                import json; open('/Users/nmartorana/dev/playground/tennis_predictions/.cursor/debug.log', 'a').write(json.dumps({"sessionId":"debug-session","runId":"startup","hypothesisId":"H1,H4","location":"download_match_data.py:125","message":"Calling FlashScore fallback","data":{"year":year,"tour":tour,"verbose":verbose},"timestamp":datetime.now().timestamp()*1000})+'\n')
                # #endregion
                
                result = self.download_matches_from_flashscore(year, tour, verbose)
                
                # #region agent log
                import json; open('/Users/nmartorana/dev/playground/tennis_predictions/.cursor/debug.log', 'a').write(json.dumps({"sessionId":"debug-session","runId":"startup","hypothesisId":"H1,H4","location":"download_match_data.py:132","message":"FlashScore fallback returned","data":{"result_is_none":result is None,"result_len":len(result) if result is not None else 0},"timestamp":datetime.now().timestamp()*1000})+'\n')
                # #endregion
                
                return result
        
        if verbose:
            print(f"  ⚠️  {tour.upper()} {year} could not be downloaded from any source")
        return None
    
    def download_matches_from_tennis_data_co_uk(self, year: int, tour: str = "atp") -> Optional[pd.DataFrame]:
        """
        Download match data from tennis-data.co.uk as fallback for missing historical data.
        This source provides Excel files with comprehensive match data including odds.
        
        Args:
            year: Year to download
            tour: 'atp' or 'wta'
            
        Returns:
            DataFrame with match data in Jeff Sackmann format, or None if failed
        """
        from io import BytesIO
        from datetime import datetime
        
        print(f"  → Fallback: Fetching {tour.upper()} {year} from tennis-data.co.uk...")
        
        try:
            # Build URL based on tour
            base_url = "http://www.tennis-data.co.uk"
            if tour.lower() == "atp":
                url = f"{base_url}/{year}/{year}.xlsx"
                save_dir = self.atp_dir
            else:
                url = f"{base_url}/{year}w/{year}.xlsx"
                save_dir = self.wta_dir
            
            # Download the Excel file
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            print(f"  ✓ Downloaded {len(response.content)} bytes")
            
            # Check if file is too small (likely empty/invalid)
            if len(response.content) < 5000:  # Less than 5KB is suspicious
                print(f"  ✗ File too small ({len(response.content)} bytes) - likely no data for {year}")
                return None
            
            # Parse Excel file
            try:
                df_raw = pd.read_excel(BytesIO(response.content))
            except Exception as e:
                print(f"  ✗ tennis-data.co.uk: Error parsing Excel - {e}")
                return None
            
            print(f"  ✓ Parsed {len(df_raw)} matches")
            
            # Convert to Jeff Sackmann format
            matches = []
            for _, row in df_raw.iterrows():
                try:
                    # Extract basic info
                    winner_name = str(row.get('Winner', '')).strip()
                    loser_name = str(row.get('Loser', '')).strip()
                    
                    # Skip if no player names
                    if not winner_name or not loser_name or winner_name == 'nan' or loser_name == 'nan':
                        continue
                    
                    # Parse date
                    date_val = row.get('Date')
                    if pd.notna(date_val):
                        if isinstance(date_val, str):
                            try:
                                date_obj = datetime.strptime(date_val, '%Y-%m-%d')
                            except:
                                date_obj = datetime.strptime(date_val, '%d/%m/%Y')
                        else:
                            date_obj = pd.to_datetime(date_val)
                        tourney_date = date_obj.strftime('%Y%m%d')
                    else:
                        tourney_date = f"{year}0101"
                    
                    # Build set score
                    sets = []
                    for i in range(1, 6):  # Up to 5 sets
                        w_set = row.get(f'W{i}')
                        l_set = row.get(f'L{i}')
                        if pd.notna(w_set) and pd.notna(l_set):
                            sets.append(f"{int(w_set)}-{int(l_set)}")
                    
                    score = " ".join(sets) if sets else ""
                    
                    # Build match record
                    match_data = {
                        "tourney_id": f"TD-{year}-{str(row.get('Tournament', ''))[:20].replace(' ', '')}",
                        "tourney_name": str(row.get('Tournament', '')),
                        "surface": str(row.get('Surface', 'Hard')),
                        "draw_size": "",
                        "tourney_level": str(row.get('Series', '')),
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
                        "winner_rank": int(row['WRank']) if pd.notna(row.get('WRank')) else "",
                        "winner_rank_points": int(row['WPts']) if pd.notna(row.get('WPts')) else "",
                        "loser_id": "",
                        "loser_seed": "",
                        "loser_entry": "",
                        "loser_name": loser_name,
                        "loser_hand": "",
                        "loser_ht": "",
                        "loser_ioc": "",
                        "loser_age": "",
                        "loser_rank": int(row['LRank']) if pd.notna(row.get('LRank')) else "",
                        "loser_rank_points": int(row['LPts']) if pd.notna(row.get('LPts')) else "",
                        "score": score,
                        "best_of": int(row['Best of']) if pd.notna(row.get('Best of')) else 3,
                        "round": str(row.get('Round', '')),
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
                    }
                    
                    matches.append(match_data)
                    
                except Exception as e:
                    continue
            
            if matches:
                df = pd.DataFrame(matches)
                print(f"  ✓ tennis-data.co.uk: Converted {len(matches)} matches")
                
                # Save to file
                filename = f"{tour}_matches_{year}.csv"
                filepath = save_dir / filename
                df.to_csv(filepath, index=False)
                print(f"  ✓ Saved to {filepath}")
                
                return df
            else:
                print(f"  ✗ tennis-data.co.uk: No valid matches after conversion")
                return None
                
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                print(f"  ✗ tennis-data.co.uk: Data not available for {tour.upper()} {year}")
            else:
                print(f"  ✗ tennis-data.co.uk: HTTP error {e.response.status_code}")
            return None
        except Exception as e:
            print(f"  ✗ tennis-data.co.uk: Error - {e}")
            return None
    
    def download_matches_from_flashscore(self, year: int, tour: str = "atp", verbose: bool = False) -> Optional[pd.DataFrame]:
        """
        Download match data from FlashScore using browser automation.
        This is the final fallback for current year data when other sources fail.
        
        Args:
            year: Year to download
            tour: 'atp' or 'wta'
            verbose: If True, print detailed messages
            
        Returns:
            DataFrame with match data in Jeff Sackmann format, or None if failed
        """
        print(f"  → FlashScore Fallback: Fetching {tour.upper()} {year} (browser automation)...")
        
        # #region agent log
        import json; from datetime import datetime; open('/Users/nmartorana/dev/playground/tennis_predictions/.cursor/debug.log', 'a').write(json.dumps({"sessionId":"debug-session","runId":"startup","hypothesisId":"H4","location":"download_match_data.py:309","message":"download_matches_from_flashscore called","data":{"year":year,"tour":tour},"timestamp":datetime.now().timestamp()*1000})+'\n')
        # #endregion
        
        try:
            # Import FlashScore client
            import sys
            sys.path.insert(0, str(Path(__file__).parent))
            
            # #region agent log
            import json; from datetime import datetime; open('/Users/nmartorana/dev/playground/tennis_predictions/.cursor/debug.log', 'a').write(json.dumps({"sessionId":"debug-session","runId":"startup","hypothesisId":"H4","location":"download_match_data.py:319","message":"About to import FlashScore client","data":{},"timestamp":datetime.now().timestamp()*1000})+'\n')
            # #endregion
            
            from src.data.flashscore_client import fetch_recent_matches_from_flashscore
            
            # #region agent log
            import json; from datetime import datetime; open('/Users/nmartorana/dev/playground/tennis_predictions/.cursor/debug.log', 'a').write(json.dumps({"sessionId":"debug-session","runId":"startup","hypothesisId":"H4","location":"download_match_data.py:326","message":"FlashScore client imported","data":{},"timestamp":datetime.now().timestamp()*1000})+'\n')
            # #endregion
            
            if tour.lower() == "atp":
                save_dir = self.atp_dir
            else:
                save_dir = self.wta_dir
            
            # Fetch last 14 days to get reasonable amount of data
            save_path = save_dir / f"{tour}_matches_{year}_flashscore.csv"
            
            # #region agent log
            import json; from datetime import datetime; open('/Users/nmartorana/dev/playground/tennis_predictions/.cursor/debug.log', 'a').write(json.dumps({"sessionId":"debug-session","runId":"startup","hypothesisId":"H1,H5","location":"download_match_data.py:335","message":"Calling fetch_recent_matches_from_flashscore","data":{"days":14,"tour":tour},"timestamp":datetime.now().timestamp()*1000})+'\n')
            # #endregion
            
            df = fetch_recent_matches_from_flashscore(days=14, tour=tour, save_to_file=save_path)
            
            # #region agent log
            import json; from datetime import datetime; open('/Users/nmartorana/dev/playground/tennis_predictions/.cursor/debug.log', 'a').write(json.dumps({"sessionId":"debug-session","runId":"startup","hypothesisId":"H1,H5","location":"download_match_data.py:343","message":"fetch_recent_matches_from_flashscore returned","data":{"df_is_none":df is None,"df_empty":df.empty if df is not None else True},"timestamp":datetime.now().timestamp()*1000})+'\n')
            # #endregion
            
            if df is not None and not df.empty:
                print(f"  ✓ FlashScore: Retrieved {len(df)} matches")
                
                # Save as main year file
                filename = f"{tour}_matches_{year}.csv"
                filepath = save_dir / filename
                df.to_csv(filepath, index=False)
                print(f"  ✓ Saved to {filepath}")
                
                return df
            else:
                print(f"  ✗ FlashScore: No matches retrieved")
                return None
                
        except ImportError as e:
            if verbose:
                print(f"  ✗ FlashScore client not available: {e}")
            return None
        except Exception as e:
            if verbose:
                print(f"  ✗ FlashScore error: {e}")
            return None
    
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
