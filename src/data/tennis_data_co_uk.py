"""
Tennis Data from tennis-data.co.uk

Downloads tennis match data from tennis-data.co.uk which provides:
- ATP and WTA match results
- Tournament information
- Surface, rankings, and betting odds
- Data available for recent years including 2024, 2025, 2026

No API key required, no rate limits!
"""

import requests
import pandas as pd
from io import BytesIO
from pathlib import Path
from typing import Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class TennisDataCoUkFetcher:
    """Fetches tennis match data from tennis-data.co.uk"""
    
    BASE_URL = "http://www.tennis-data.co.uk"
    
    def __init__(self, data_dir: str = "data"):
        """
        Initialize the fetcher.
        
        Args:
            data_dir: Directory to save downloaded data
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.atp_dir = self.data_dir / "atp"
        self.wta_dir = self.data_dir / "wta"
        self.atp_dir.mkdir(exist_ok=True)
        self.wta_dir.mkdir(exist_ok=True)
    
    def download_matches(
        self, 
        year: int, 
        tour: str = "atp", 
        verbose: bool = False
    ) -> Optional[pd.DataFrame]:
        """
        Download match data for a specific year and tour from tennis-data.co.uk.
        
        Args:
            year: Year to download (e.g., 2024)
            tour: 'atp' or 'wta'
            verbose: If True, print detailed messages
            
        Returns:
            DataFrame with match data in Jeff Sackmann format, or None if download failed
        """
        tour_lower = tour.lower()
        
        # Build URL based on tour
        if tour_lower == "atp":
            url = f"{self.BASE_URL}/{year}/{year}.xlsx"
            save_dir = self.atp_dir
        elif tour_lower == "wta":
            url = f"{self.BASE_URL}/{year}w/{year}.xlsx"
            save_dir = self.wta_dir
        else:
            logger.error(f"Invalid tour: {tour}. Must be 'atp' or 'wta'")
            return None
        
        if verbose:
            print(f"Downloading {tour.upper()} {year} from tennis-data.co.uk...")
        
        try:
            # Download the Excel file
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            if verbose:
                print(f"  ✓ Downloaded {len(response.content)} bytes")  # noqa: G004
            
            # Parse Excel file
            df = pd.read_excel(BytesIO(response.content))
            
            if verbose:
                print(f"  ✓ Parsed {len(df)} matches")
            
            # Convert to Jeff Sackmann format
            converted_df = self._convert_to_sackmann_format(df, year, tour_lower)
            
            if converted_df is not None and not converted_df.empty:
                # Save to CSV in Jeff Sackmann format
                filename = f"{tour_lower}_matches_{year}.csv"
                filepath = save_dir / filename
                converted_df.to_csv(filepath, index=False)
                
                if verbose:
                    print(f"  ✓ Saved {len(converted_df)} matches to {filepath}")
                
                return converted_df
            else:
                if verbose:
                    print(f"  ✗ No valid match data after conversion")
                return None
                
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                if verbose:
                    print(f"  ✗ Data not available for {tour.upper()} {year}")
            else:
                logger.error(f"HTTP error downloading {tour} {year}: {e}")
                if verbose:
                    print(f"  ✗ HTTP error: {e}")
            return None
        except Exception as e:
            logger.error(f"Error downloading {tour} {year} from tennis-data.co.uk: {e}")
            if verbose:
                print(f"  ✗ Error: {e}")
            return None
    
    def _convert_to_sackmann_format(
        self, 
        df: pd.DataFrame, 
        year: int,
        tour: str  # noqa: ARG002 - kept for API consistency
    ) -> pd.DataFrame:
        """
        Convert tennis-data.co.uk format to Jeff Sackmann format.
        
        Args:
            df: DataFrame from tennis-data.co.uk
            year: Year of the data
            tour: 'atp' or 'wta'
            
        Returns:
            DataFrame in Jeff Sackmann format
        """
        matches = []
        
        for _, row in df.iterrows():
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
                    tourney_date = f"{year}0101"  # Default to Jan 1 if no date
                
                # Build set score
                sets = []
                for i in range(1, 6):  # Up to 5 sets
                    w_set = row.get(f'W{i}')
                    l_set = row.get(f'L{i}')
                    if pd.notna(w_set) and pd.notna(l_set):
                        sets.append(f"{int(w_set)}-{int(l_set)}")
                
                score = " ".join(sets) if sets else ""
                
                # Build match record in Jeff Sackmann format
                match_data = {
                    "tourney_id": f"TD-{year}-{row.get('Tournament', '')[:20].replace(' ', '')}",
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
                
            except (ValueError, KeyError, TypeError) as e:
                logger.warning(f"Error converting row: {e}")
                continue
        
        if not matches:
            return pd.DataFrame()
        
        return pd.DataFrame(matches)
    
    def download_multiple_years(
        self, 
        start_year: int, 
        end_year: int, 
        tour: str = "atp", 
        verbose: bool = True
    ) -> dict:
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
            if df is not None and not df.empty:
                data[year] = df
        return data
    
    def download_recent_matches(
        self, 
        years: int = 5, 
        tour: str = "atp", 
        verbose: bool = True
    ) -> dict:
        """
        Download match data for recent years.
        
        Args:
            years: Number of recent years to download
            tour: 'atp' or 'wta'
            verbose: If True, print detailed messages
            
        Returns:
            Dictionary mapping year to DataFrame
        """
        current_year = datetime.now().year
        start_year = current_year - years + 1
        return self.download_multiple_years(start_year, current_year, tour, verbose=verbose)


def main():
    """Test the tennis-data.co.uk integration"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Download tennis match data from tennis-data.co.uk"
    )
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
    
    fetcher = TennisDataCoUkFetcher(data_dir=args.data_dir)
    
    tours = ["atp", "wta"] if args.tour == "both" else [args.tour]
    
    for tour in tours:
        print(f"\n{'='*60}")
        print(f"Downloading {tour.upper()} match data from tennis-data.co.uk")
        print(f"{'='*60}\n")
        
        if args.start_year and args.end_year:
            data = fetcher.download_multiple_years(
                args.start_year, args.end_year, tour
            )
        else:
            data = fetcher.download_recent_matches(args.years, tour)
        
        if data:
            total_matches = sum(len(df) for df in data.values())
            print(f"\n✓ Successfully downloaded {total_matches} matches across {len(data)} years")
        else:
            print(f"\n✗ Failed to download {tour} data")


if __name__ == "__main__":
    main()

