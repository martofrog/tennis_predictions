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
    
    def download_matches(self, year: int, tour: str = "atp", verbose: bool = False) -> Optional[pd.DataFrame]:
        """
        Download match data for a specific year and tour.
        
        Args:
            year: Year to download (e.g., 2023)
            tour: 'atp' or 'wta'
            verbose: If True, print detailed messages
            
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
        
        # Download the file
        if self.download_file(url, filepath, silent_404=not verbose):
            try:
                df = pd.read_csv(filepath)
                if verbose:
                    print(f"✓ Loaded {len(df)} matches from {filename}")
                return df
            except Exception as e:
                if verbose:
                    print(f"✗ Error reading CSV: {e}")
                return None
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
