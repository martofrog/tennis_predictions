"""
Data Loader for Tennis Match Data

Loads historical match data from CSV files.
"""

import pandas as pd
from pathlib import Path
from typing import List, Optional
import logging

from src.core.interfaces import IMatchDataRepository
from src.core.constants import DEFAULT_DATA_DIR

logger = logging.getLogger(__name__)


def load_match_data(
    years: Optional[List[int]] = None,
    tour: Optional[str] = None,
    data_dir: str = DEFAULT_DATA_DIR
) -> pd.DataFrame:
    """
    Load tennis match data from CSV files.
    
    Args:
        years: List of years to load (None = all available)
        tour: Tour filter ('atp' or 'wta', None = both)
        data_dir: Directory containing CSV files
        
    Returns:
        DataFrame with match data
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
        # Try multiple patterns: subdirectory format and root format
        patterns = [
            f"{tour_type}_matches_*.csv",  # Subdirectory format: atp_matches_2024.csv
            f"tennis_matches_{tour_type}_*.csv"  # Root format: tennis_matches_atp_2024.csv
        ]
        
        # Check subdirectory first
        tour_dir = data_path / tour_type
        if tour_dir.exists():
            for pattern in patterns:
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
        
        # Check root directory
        for pattern in patterns:
            for file_path in data_path.glob(pattern):
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
    
    if not dataframes:
        return pd.DataFrame()
    
    return pd.concat(dataframes, ignore_index=True)
