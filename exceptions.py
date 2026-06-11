"""
Custom exceptions for the HOPS forensic system.
"""
class APIError(Exception):
    """Base exception for API-related errors."""
    def __init__(self, message: str, status_code: int = None):
        super().__init__(message)
        self.status_code = status_code


class NetworkError(APIError):
    """Raised when there are network connectivity issues."""
    pass


class RateLimitError(APIError):
    """Raised when API rate limits are exceeded."""
    def __init__(self, message: str, status_code: int = 429, retry_after: int = None):
        super().__init__(message, status_code)
        self.retry_after = retry_after


class AuthenticationError(APIError):
    """Raised when API authentication fails."""
    def __init__(self, message: str, status_code: int = 401):
        super().__init__(message, status_code)


class ValidationError(Exception):
    """Raised when data validation fails."""
    pass


class ConfigurationError(Exception):
    """Raised when there are configuration issues."""
    pass