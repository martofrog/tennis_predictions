"""
Dependency Injection Container (SOLID: DIP)

Centralized configuration of dependencies.
Makes it easy to swap implementations without changing business logic.
"""

from typing import Optional
import os

from src.core.interfaces import (
    IRatingSystem,
    IRatingRepository,
    IOddsProvider,
    IOddsConverter,
    IMatchDataRepository,
    ICacheStorage
)
from src.core.constants import (
    DEFAULT_RATINGS_FILE,
    DEFAULT_DATA_DIR,
    DEFAULT_CACHE_FILE,
    DEFAULT_SURFACE_ADVANTAGE,
    DEFAULT_K_FACTOR
)
from src.core.exceptions import ConfigurationError

from src.infrastructure.repositories import (
    JsonRatingRepository,
    CsvMatchDataRepository,
    JsonCacheStorage
)

from src.infrastructure.adapters import (
    TheOddsApiAdapter,
    StandardOddsConverter,
    MockOddsProvider
)

from src.prediction.elo_rating_system import TennisEloRatingSystem
from src.services.rating_service import RatingService
from src.services.betting_service import BettingService


class DependencyContainer:
    """
    Dependency Injection Container.
    
    Centralizes creation and configuration of all dependencies.
    Follows Dependency Inversion Principle.
    """
    
    def __init__(
        self,
        ratings_file: Optional[str] = None,
        data_dir: Optional[str] = None,
        cache_file: Optional[str] = None,
        surface_advantage: float = DEFAULT_SURFACE_ADVANTAGE,
        k_factor: float = DEFAULT_K_FACTOR,
        use_mock_odds: bool = False
    ):
        """
        Initialize dependency container.
        
        Args:
            ratings_file: Path to ratings file
            data_dir: Directory for match data
            cache_file: Path to cache file
            surface_advantage: Surface specialization advantage in Elo points
            k_factor: K-factor for Elo updates
            use_mock_odds: Whether to use mock odds provider (for testing)
        """
        self.ratings_file = ratings_file or DEFAULT_RATINGS_FILE
        self.data_dir = data_dir or DEFAULT_DATA_DIR
        self.cache_file = cache_file or DEFAULT_CACHE_FILE
        self.surface_advantage = surface_advantage
        self.k_factor = k_factor
        self.use_mock_odds = use_mock_odds
        
        # Lazy initialization
        self._rating_repository: Optional[IRatingRepository] = None
        self._match_data_repository: Optional[IMatchDataRepository] = None
        self._cache_storage: Optional[ICacheStorage] = None
        self._odds_provider: Optional[IOddsProvider] = None
        self._odds_converter: Optional[IOddsConverter] = None
        self._rating_system: Optional[IRatingSystem] = None
        self._rating_service: Optional[RatingService] = None
        self._betting_service: Optional[BettingService] = None
    
    # Repositories
    
    def rating_repository(self) -> IRatingRepository:
        """Get rating repository instance."""
        if self._rating_repository is None:
            self._rating_repository = JsonRatingRepository(self.ratings_file)
        return self._rating_repository
    
    def match_data_repository(self) -> IMatchDataRepository:
        """Get match data repository instance."""
        if self._match_data_repository is None:
            self._match_data_repository = CsvMatchDataRepository(self.data_dir)
        return self._match_data_repository
    
    def cache_storage(self) -> ICacheStorage:
        """Get cache storage instance."""
        if self._cache_storage is None:
            self._cache_storage = JsonCacheStorage(self.cache_file)
        return self._cache_storage
    
    # Adapters
    
    def odds_provider(self) -> IOddsProvider:
        """Get odds provider instance."""
        if self._odds_provider is None:
            if self.use_mock_odds:
                self._odds_provider = MockOddsProvider()
            else:
                # Try to create The Odds API provider
                odds_api_key = os.getenv("ODDS_API_KEY")
                if odds_api_key:
                    try:
                        self._odds_provider = TheOddsApiAdapter(odds_api_key)
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.info("✓ The Odds API configured")
                    except Exception as e:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.error(f"Failed to initialize The Odds API: {e}")
                        raise
                else:
                    import logging
                    logger = logging.getLogger(__name__)
                    raise ConfigurationError(
                        "ODDS_API_KEY not found. Set it in .env file or "
                        "use use_mock_odds=True for testing."
                    )
        
        return self._odds_provider
    
    def odds_converter(self) -> IOddsConverter:
        """Get odds converter instance."""
        if self._odds_converter is None:
            self._odds_converter = StandardOddsConverter()
        return self._odds_converter
    
    # Domain Services
    
    def rating_system(self) -> IRatingSystem:
        """Get rating system instance."""
        if self._rating_system is None:
            self._rating_system = TennisEloRatingSystem(
                repository=self.rating_repository(),
                surface_advantage=self.surface_advantage,
                k_factor=self.k_factor
            )
        return self._rating_system
    
    def rating_service(self) -> RatingService:
        """Get rating service instance."""
        if self._rating_service is None:
            self._rating_service = RatingService(
                rating_system=self.rating_system(),
                repository=self.rating_repository()
            )
        return self._rating_service
    
    def betting_service(self) -> BettingService:
        """Get betting service instance."""
        if self._betting_service is None:
            self._betting_service = BettingService(
                rating_system=self.rating_system(),
                odds_provider=self.odds_provider(),
                odds_converter=self.odds_converter(),
                cache_storage=self.cache_storage()
            )
        return self._betting_service
    
    # Reset methods (useful for testing)
    
    def reset(self) -> None:
        """Reset all cached instances."""
        self._rating_repository = None
        self._match_data_repository = None
        self._cache_storage = None
        self._odds_provider = None
        self._odds_converter = None
        self._rating_system = None
        self._rating_service = None
        self._betting_service = None


# Global container instance
_container: Optional[DependencyContainer] = None


def get_container(
    ratings_file: Optional[str] = None,
    data_dir: Optional[str] = None,
    cache_file: Optional[str] = None,
    surface_advantage: float = DEFAULT_SURFACE_ADVANTAGE,
    k_factor: float = DEFAULT_K_FACTOR,
    use_mock_odds: bool = False
) -> DependencyContainer:
    """
    Get or create global dependency container.
    
    This allows singleton-like behavior while maintaining testability.
    """
    global _container
    if _container is None:
        _container = DependencyContainer(
            ratings_file=ratings_file,
            data_dir=data_dir,
            cache_file=cache_file,
            surface_advantage=surface_advantage,
            k_factor=k_factor,
            use_mock_odds=use_mock_odds
        )
    return _container


def reset_container() -> None:
    """Reset the global container (useful for testing)."""
    global _container
    if _container:
        _container.reset()
    _container = None
