"""
Data Loader for Tennis Match Data

Loads historical match data from CSV files.
"""

import pandas as pd
from pathlib import Path
from typing import List, Optional
from datetime import datetime
import logging

from src.core.interfaces import IMatchDataRepository
from src.core.constants import DEFAULT_DATA_DIR

logger = logging.getLogger(__name__)


def load_match_data(
    years: Optional[List[int]] = None,
    tour: Optional[str] = None,
    data_dir: str = DEFAULT_DATA_DIR,
    filter_future_matches: bool = True
) -> pd.DataFrame:
    """
    Load tennis match data from CSV files.
    
    Args:
        years: List of years to load (None = all available)
        tour: Tour filter ('atp' or 'wta', None = both)
        data_dir: Directory containing CSV files
        filter_future_matches: If True, exclude matches with dates in the future
        
    Returns:
        DataFrame with match data (only completed matches if filter_future_matches=True)
    """
    data_path = Path(data_dir)
    
    if not data_path.exists():
        logger.warning(f"Data directory {data_dir} does not exist")
        return pd.DataFrame()
    
    dataframes = []
    
    # Determine which files to load
    if tour:
        tours_to_load = [tour]
    else:
        tours_to_load = ['atp', 'wta']
    
    for tour_type in tours_to_load:
        # Look for files in tour subdirectory with pattern: atp/atp_matches_*.csv
        tour_dir = data_path / tour_type
        if tour_dir.exists():
            pattern = f"{tour_type}_matches_*.csv"
            
            for file_path in tour_dir.glob(pattern):
                try:
                    # Extract year from filename
                    year_str = file_path.stem.split('_')[-1]
                    year = int(year_str)
                    
                    if years is None or year in years:
                        df = pd.read_csv(file_path)
                        df['year'] = year
                        df['tour'] = tour_type
                        dataframes.append(df)
                        logger.info(f"Loaded {len(df)} matches from {file_path.name}")
                except Exception as e:
                    logger.warning(f"Failed to load {file_path}: {e}")
        else:
            logger.warning(f"Tour directory {tour_dir} does not exist")
    
    if not dataframes:
        return pd.DataFrame()
    
    combined_df = pd.concat(dataframes, ignore_index=True)
    
    # Filter out future matches if requested
    if filter_future_matches and 'tourney_date' in combined_df.columns:
        original_count = len(combined_df)
        
        # Convert tourney_date to datetime for comparison
        # Format is YYYYMMDD (e.g., 20250107) - stored as integer
        today = int(datetime.now().strftime('%Y%m%d'))
        
        # Filter to only include matches on or before today
        # Handle both string and int formats
        combined_df['tourney_date'] = pd.to_numeric(combined_df['tourney_date'], errors='coerce')
        combined_df = combined_df[combined_df['tourney_date'] <= today].copy()
        
        filtered_count = original_count - len(combined_df)
        if filtered_count > 0:
            logger.info(f"Filtered out {filtered_count} future matches (only using completed matches)")
    
    return combined_df
