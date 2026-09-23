"""Safe errors crossing the application boundary."""

from typing import Any


class ServiceError(Exception):
    """Represent an actionable error without serializing private inputs.

    Parameters
    ----------
    code : str
        Stable machine-readable error code.
    message : str
        Public explanation of the failed operation.
    status : int
        HTTP status used by the transport adapter.
    details : list of dict, optional
        Sanitized field paths and reasons, never submitted secret values.
    """

    def __init__(
        self,
        code: str,
        message: str,
        status: int = 409,
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message)
        self.code, self.message, self.status = code, message, status
        self.details = details or []
