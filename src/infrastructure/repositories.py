"""
Repository Implementations (SOLID: SRP, DIP)

Concrete implementations of data access interfaces.
Each repository has a single responsibility: managing one type of data.
"""

import json
import os
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta, timezone
import pandas as pd

from src.core.interfaces import IRatingRepository, IMatchDataRepository, ICacheStorage
from src.core.exceptions import RepositoryError
from src.core.constants import DEFAULT_RATINGS_FILE, DEFAULT_DATA_DIR, DEFAULT_CACHE_FILE
from src.core.tennis_utils import get_years_to_check, find_date_column

logger = logging.getLogger(__name__)


class JsonRatingRepository(IRatingRepository):
    """
    JSON file-based rating repository.
    
    Single Responsibility: Managing rating persistence in JSON format.
    Open/Closed: Can extend with different file formats without modifying.
    """
    
    def __init__(self, file_path: str = DEFAULT_RATINGS_FILE):
        """
        Initialize JSON rating repository.
        
        Args:
            file_path: Path to JSON file
        """
        self.file_path = Path(file_path)
    
    def load(self) -> Dict[str, Any]:
        """Load ratings from JSON file."""
        if not self.exists():
            return {}
        
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if not content:
                    return {}
                return json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in ratings file {self.file_path}: {e}")
            raise RepositoryError(f"Invalid JSON format in {self.file_path}") from e
        except FileNotFoundError:
            return {}
        except IOError as e:
            logger.error(f"Failed to load ratings from {self.file_path}: {e}")
            raise RepositoryError(f"Cannot read ratings file {self.file_path}") from e
    
    def save(self, ratings: Dict[str, Any]) -> None:
        """Save ratings to JSON file."""
        try:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(ratings, f, indent=2, ensure_ascii=False)
        except IOError as e:
            logger.error(f"Failed to save ratings to {self.file_path}: {e}")
            raise RepositoryError(f"Cannot write to ratings file {self.file_path}") from e
    
    def exists(self) -> bool:
        """Check if ratings file exists."""
        return self.file_path.exists()


class CsvMatchDataRepository(IMatchDataRepository):
    """
    CSV file-based match data repository.
    
    Single Responsibility: Managing match data persistence in CSV format.
    """
    
    def __init__(self, data_dir: str = DEFAULT_DATA_DIR):
        """
        Initialize CSV match data repository.
        
        Args:
            data_dir: Directory containing CSV files
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
    
    def load_matches(self, years: Optional[List[int]] = None, tour: Optional[str] = None) -> pd.DataFrame:
        """
        Load match data for specified years and tour.
        
        Args:
            years: List of years to load. If None, loads all available.
            tour: Optional tour filter ('atp' or 'wta')
            
        Returns:
            DataFrame with combined match data
        """
        if years is None:
            years = self._get_available_years()
        
        if not years:
            return pd.DataFrame()
        
        dataframes = []
        for year in years:
            for tour_type in (['atp', 'wta'] if not tour else [tour]):
                filepath = self._get_file_path(year, tour_type)
                if filepath.exists():
                    try:
                        df = pd.read_csv(filepath)
                        df['season'] = year
                        df['tour'] = tour_type
                        dataframes.append(df)
                    except Exception as e:
                        logger.warning(f"Failed to load data for {year} {tour_type}: {e}")
        
        if not dataframes:
            return pd.DataFrame()
        
        return pd.concat(dataframes, ignore_index=True)
    
    def save_matches(self, data: pd.DataFrame, year: int, tour: str) -> None:
        """
        Save match data for a year and tour.
        
        Args:
            data: DataFrame with match data
            year: Season year
            tour: Tour type ('atp' or 'wta')
        """
        filepath = self._get_file_path(year, tour)
        try:
            data.to_csv(filepath, index=False)
        except Exception as e:
            raise RuntimeError(f"Failed to save match data for {year} {tour}: {e}")
    
    def match_data_exists(self, year: int, tour: str) -> bool:
        """Check if match data exists for a year and tour."""
        return self._get_file_path(year, tour).exists()
    
    def _get_file_path(self, year: int, tour: str) -> Path:
        """Get file path for a given year and tour."""
        return self.data_dir / tour.lower() / f"{tour.lower()}_matches_{year}.csv"
    
    def get_matches_by_date(self, target_date: datetime, tour: Optional[str] = None) -> pd.DataFrame:
        """
        Get matches for a specific date.
        
        Args:
            target_date: Date to get matches for
            tour: Optional tour filter ('atp' or 'wta')
            
        Returns:
            DataFrame with matches for the specified date
        """
        years_to_check = get_years_to_check()
        
        all_matches = self.load_matches(years=years_to_check, tour=tour)
        
        if all_matches.empty:
            return pd.DataFrame()
        
        date_col = find_date_column(all_matches)
        
        if not date_col:
            return pd.DataFrame()
        
        all_matches[date_col] = pd.to_datetime(all_matches[date_col], errors='coerce')
        
        target_date_only = target_date.date()
        all_matches['date_only'] = all_matches[date_col].dt.date
        
        filtered = all_matches[all_matches['date_only'] == target_date_only].copy()
        
        if 'date_only' in filtered.columns:
            filtered = filtered.drop(columns=['date_only'])
        
        return filtered
    
    def _get_available_years(self) -> List[int]:
        """Get list of years with available data."""
        years = []
        # Check both atp and wta subdirectories
        for tour_dir in ['atp', 'wta']:
            tour_path = self.data_dir / tour_dir
            if tour_path.exists():
                for file in tour_path.glob(f"{tour_dir}_matches_*.csv"):
                    try:
                        # Extract year from filename like "atp_matches_2024.csv"
                        parts = file.stem.split('_')
                        if len(parts) >= 3:
                            year = int(parts[-1])
                            years.append(year)
                    except ValueError:
                        continue
        return sorted(set(years))


class JsonCacheStorage(ICacheStorage):
    """
    JSON file-based cache storage.
    
    Single Responsibility: Managing cache persistence.
    Can be easily replaced with Redis, Memcached, etc.
    """
    
    def __init__(
        self,
        cache_file: str = DEFAULT_CACHE_FILE,
        default_ttl_minutes: int = 60
    ):
        """
        Initialize JSON cache storage.
        
        Args:
            cache_file: Path to cache file
            default_ttl_minutes: Default TTL for cache entries
        """
        self.cache_file = Path(cache_file)
        self.default_ttl_minutes = default_ttl_minutes
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._load()
    
    def get(self, key: str) -> Optional[Any]:
        """Get cached value if valid."""
        if not self.is_valid(key):
            self.delete(key)
            return None
        
        entry = self._cache.get(key)
        return entry["data"] if entry else None
    
    def set(self, key: str, value: Any, ttl_minutes: Optional[int] = None) -> None:
        """Set cached value with TTL."""
        ttl = ttl_minutes if ttl_minutes is not None else self.default_ttl_minutes
        
        self._cache[key] = {
            "data": value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "ttl_minutes": ttl
        }
        self._save()
    
    def delete(self, key: str) -> None:
        """Delete cached value."""
        if key in self._cache:
            del self._cache[key]
            self._save()
    
    def clear(self) -> None:
        """Clear all cached values."""
        self._cache = {}
        self._save()
    
    def keys(self) -> List[str]:
        """Get all valid cache keys."""
        self._clean_expired()
        return list(self._cache.keys())
    
    def is_valid(self, key: str) -> bool:
        """Check if cached value is still valid."""
        if key not in self._cache:
            return False
        
        entry = self._cache[key]
        timestamp = datetime.fromisoformat(entry["timestamp"])
        ttl = timedelta(minutes=entry.get("ttl_minutes", self.default_ttl_minutes))
        
        return datetime.now(timezone.utc) - timestamp < ttl
    
    def _load(self) -> None:
        """Load cache from file."""
        if not self.cache_file.exists():
            self._cache = {}
            return
        
        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if not content:
                    self._cache = {}
                else:
                    self._cache = json.loads(content)
            self._clean_expired()
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load cache from {self.cache_file}: {e}")
            self._cache = {}
    
    def _save(self) -> None:
        """Save cache to file."""
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self._cache, f, indent=4, ensure_ascii=False)
        except IOError as e:
            logger.error(f"Failed to save cache to {self.cache_file}: {e}")
            raise RepositoryError(f"Cannot write to cache file {self.cache_file}") from e
    
    def _clean_expired(self) -> None:
        """Remove expired entries."""
        expired_keys = [k for k in self._cache if not self.is_valid(k)]
        for key in expired_keys:
            del self._cache[key]
        
        if expired_keys:
            self._save()
