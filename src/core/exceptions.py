"""
Custom Exceptions for Tennis Predictions

Domain-specific exceptions for better error handling.
"""


class TennisPredictionError(Exception):
    """Base exception for tennis prediction errors."""
    pass


class RepositoryError(TennisPredictionError):
    """Error related to data repository operations."""
    pass


class OddsProviderError(TennisPredictionError):
    """Error related to odds provider operations."""
    pass


class ValidationError(TennisPredictionError):
    """Error related to input validation."""
    pass


class ConfigurationError(TennisPredictionError):
    """Error related to configuration issues."""
    pass


class RatingSystemError(TennisPredictionError):
    """Error related to rating system operations."""
    pass
