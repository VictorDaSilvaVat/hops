"""
Base API client with retry logic, error handling, and logging.
"""
import time
import json
import logging
from typing import Optional, Dict, Any, Callable
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from exceptions import APIError, NetworkError, RateLimitError, AuthenticationError

logger = logging.getLogger(__name__)


class BaseAPIClient:
    """
    Base class for API clients with retry, error handling, and logging.
    """
    
    def __init__(
        self,
        base_url: str,
        timeout: int = 15,
        max_retries: int = 5,
        retry_delay: float = 1.0,
        rate_limit_delay: float = 0.3,
        backoff_factor: float = 1.0,
        status_forcelist: tuple = (429, 500, 502, 503, 504),
    ):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.rate_limit_delay = rate_limit_delay
        self.backoff_factor = backoff_factor
        self.status_forcelist = status_forcelist
        self._last_request_time = 0.0
        
        # Create session with retry strategy
        self.session = requests.Session()
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=backoff_factor,
            status_forcelist=status_forcelist,
            allowed_methods=["GET"],
            respect_retry_after_header=True,
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Cache for responses (simple dictionary cache)
        self._cache = {}
        self._cache_timestamps = {}
    
    def _get(
        self,
        endpoint: str,
        use_cache: bool = True,
        cache_ttl: int = 300,
        **kwargs
    ) -> Optional[Dict[Any, Any]]:
        """
        Make a GET request with retry logic and optional caching.
        
        Args:
            endpoint: API endpoint (will be appended to base_url)
            use_cache: Whether to use caching
            cache_ttl: Cache time-to-live in seconds
            **kwargs: Additional arguments to pass to requests.get
            
        Returns:
            JSON response as dictionary or None if failed
            
        Raises:
            APIError: For various API-related errors
        """
        url = f"{self.base_url}{endpoint}"
        
        # Check cache
        if use_cache:
            cached = self._get_from_cache(url, cache_ttl)
            if cached is not None:
                logger.debug("Cache hit for %s", url)
                return cached
        
        # Apply inter-request throttle to avoid rate limits
        self._throttle()
        
        # Make request with retry logic
        start_time = time.time()
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                logger.debug("Making request to %s (attempt %d/%d)", url, attempt + 1, self.max_retries + 1)
                response = self.session.get(url, timeout=self.timeout, **kwargs)
                self._last_request_time = time.time()
                
                # Log request details
                logger.info(
                    "API request completed: url=%s status=%d duration=%.2fs",
                    url, response.status_code, time.time() - start_time
                )
                
                # Handle HTTP status codes
                if response.status_code == 200:
                    try:
                        data = response.json()
                        # Cache successful response
                        if use_cache:
                            self._cache_response(url, data)
                        return data
                    except json.JSONDecodeError as e:
                        logger.error("Failed to decode JSON from %s: %s", url, e)
                        raise APIError(f"Invalid JSON response: {e}")
                
                elif response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', max(2, self.rate_limit_delay * (2 ** attempt))))
                    logger.warning("Rate limit exceeded for %s. Waiting %ds before retry (attempt %d/%d)", 
                                   url, retry_after, attempt + 1, self.max_retries + 1)
                    if attempt < self.max_retries:
                        time.sleep(retry_after)
                        continue  # Retry
                    else:
                        raise RateLimitError(
                            f"Rate limit exceeded after {self.max_retries + 1} attempts. Last retry-after: {retry_after}s",
                            status_code=429,
                            retry_after=retry_after
                        )
                
                elif response.status_code == 401:
                    logger.error("Authentication failed for %s", url)
                    raise AuthenticationError(
                        f"Authentication failed: {response.text}",
                        status_code=401
                    )
                
                elif response.status_code >= 500:
                    logger.error("Server error %d for %s", response.status_code, url)
                    if attempt < self.max_retries:
                        wait = self.backoff_factor * (2 ** attempt)
                        logger.info("Retrying in %.1fs...", wait)
                        time.sleep(wait)
                        continue
                    raise APIError(
                        f"Server error: {response.status_code} {response.text}",
                        status_code=response.status_code
                    )
                
                else:
                    logger.error("Client error %d for %s: %s", response.status_code, url, response.text[:200])
                    raise APIError(
                        f"Client error: {response.status_code} {response.text[:200]}",
                        status_code=response.status_code
                    )
                    
            except (RateLimitError, AuthenticationError, APIError):
                raise  # Don't catch our own errors
                    
            except requests.Timeout:
                logger.error("Timeout requesting %s (attempt %d/%d)", url, attempt + 1, self.max_retries + 1)
                last_exception = NetworkError(f"Request timeout after {self.timeout} seconds")
                if attempt < self.max_retries:
                    wait = self.backoff_factor * (2 ** attempt)
                    logger.info("Retrying in %.1fs...", wait)
                    time.sleep(wait)
                    continue
            
            except requests.ConnectionError as e:
                logger.error("Connection error for %s (attempt %d/%d): %s", url, attempt + 1, self.max_retries + 1, e)
                last_exception = NetworkError(f"Connection error: {e}")
                if attempt < self.max_retries:
                    wait = self.backoff_factor * (2 ** attempt)
                    logger.info("Retrying in %.1fs...", wait)
                    time.sleep(wait)
                    continue
            
            except requests.RequestException as e:
                logger.error("Request exception for %s: %s", url, e)
                raise NetworkError(f"Request failed: {e}")
        
        # All retries exhausted
        if last_exception:
            raise last_exception
        raise NetworkError(f"Request to {url} failed after {self.max_retries + 1} attempts")
    def _throttle(self):
        """Enforce minimum delay between requests to avoid rate limiting."""
        if self._last_request_time > 0:
            elapsed = time.time() - self._last_request_time
            if elapsed < self.rate_limit_delay:
                sleep_time = self.rate_limit_delay - elapsed
                logger.debug("Throttling: sleeping %.2fs between requests", sleep_time)
                time.sleep(sleep_time)
    
    def _get_from_cache(self, url: str, ttl: int) -> Optional[Dict[Any, Any]]:
        """Retrieve item from cache if not expired."""
        if url in self._cache:
            timestamp = self._cache_timestamps.get(url, 0)
            if time.time() - timestamp < ttl:
                return self._cache[url]
            else:
                # Remove expired cache entry
                del self._cache[url]
                del self._cache_timestamps[url]
        return None
    
    def _cache_response(self, url: str, data: Dict[Any, Any]) -> None:
        """Store response in cache with timestamp."""
        self._cache[url] = data
        self._cache_timestamps[url] = time.time()
    
    def clear_cache(self) -> None:
        """Clear all cached responses."""
        self._cache.clear()
        self._cache_timestamps.clear()
        logger.info("API client cache cleared")