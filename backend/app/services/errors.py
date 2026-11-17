from typing import Any


class ApiProblem(Exception):
    """An error that should reach the client as a friendly JSON body (see ``ErrorResponse``)."""

    def __init__(
        self,
        status_code: int,
        detail: str,
        errors: list[dict[str, Any]] | None = None,
        ingestion_id: str | None = None,
    ):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail
        self.errors = errors or []
        self.ingestion_id = ingestion_id

    def body(self) -> dict[str, Any]:
        return {"detail": self.detail, "errors": self.errors, "ingestion_id": self.ingestion_id}
