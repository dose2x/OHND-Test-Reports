"""Custom exceptions for the Garage 61 API client."""


class Garage61APIError(Exception):
    """Raised when the Garage 61 API returns an error response."""

    def __init__(self, status_code: int, message: str, payload: dict | None = None):
        self.status_code = status_code
        self.payload = payload or {}
        super().__init__(f"Garage 61 API error {status_code}: {message}")


class Garage61AuthError(Garage61APIError):
    """Raised when the API rejects the supplied personal access token."""


class Garage61RateLimitError(Garage61APIError):
    """Raised when the API responds with 429 Too Many Requests."""

    def __init__(self, message: str, retry_after: float | None = None, payload: dict | None = None):
        self.retry_after = retry_after
        super().__init__(429, message, payload)
