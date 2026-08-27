from typing import Any

import requests


class AccountingAPIError(Exception):

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        error_code: str | None = None,
        details: Any = None,
    ):
        super().__init__(message)

        self.status_code = status_code
        self.error_code = error_code
        self.details = details


class AccountingClient:

    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: int = 30,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

        self.session = requests.Session()

        self.session.headers.update(
            {
                "X-API-Key": api_key,
                "Content-Type": "application/json",
            }
        )

    # ---------------------------------------------------------
    # GET
    # ---------------------------------------------------------

    def _get(self, path: str) -> Any:

        try:
            response = self.session.get(
                f"{self.base_url}{path}",
                timeout=self.timeout,
            )

        except requests.RequestException as exc:

            raise AccountingAPIError(
                f"Could not connect to accounting API: {exc}"
            ) from exc

        return self._handle_response(
            response,
            path,
        )

    # ---------------------------------------------------------
    # POST
    # ---------------------------------------------------------

    def _post(
        self,
        path: str,
        payload: dict,
    ) -> Any:

        try:

            response = self.session.post(
                f"{self.base_url}{path}",
                json=payload,
                timeout=self.timeout,
            )

        except requests.RequestException as exc:

            raise AccountingAPIError(
                f"Could not connect to accounting API: {exc}"
            ) from exc

        return self._handle_response(
            response,
            path,
        )

    # ---------------------------------------------------------
    # Common response handling
    # ---------------------------------------------------------

    def _handle_response(
        self,
        response: requests.Response,
        path: str,
    ) -> Any:

        try:
            body = response.json()

        except ValueError:

            raise AccountingAPIError(
                f"Accounting API returned invalid JSON "
                f"for {path}. "
                f"HTTP {response.status_code}: "
                f"{response.text}"
            )

        # HTTP-level failure
        if not response.ok:

            error = body.get("error") or {}

            raise AccountingAPIError(
                message=error.get(
                    "message",
                    f"HTTP {response.status_code}",
                ),
                status_code=response.status_code,
                error_code=error.get("code"),
                details=error.get("details"),
            )

        # API-level failure
        if not body.get("success"):

            error = body.get("error") or {}

            raise AccountingAPIError(
                message=error.get(
                    "message",
                    "Accounting API request failed",
                ),
                status_code=response.status_code,
                error_code=error.get("code"),
                details=error.get("details"),
            )

        return body.get("data")

    # ---------------------------------------------------------
    # Partners
    # ---------------------------------------------------------

    def get_partners(self) -> list[dict]:

        data = self._get("/partners")

        return data["partners"]

    # ---------------------------------------------------------
    # Tax codes
    # ---------------------------------------------------------

    def get_tax_codes(self) -> list[dict]:

        data = self._get("/tax-codes")

        return data["tax_codes"]

    # ---------------------------------------------------------
    # Existing invoices
    # ---------------------------------------------------------

    def get_invoices(self) -> list[dict]:

        data = self._get("/invoices")

        return data["invoices"]

    # ---------------------------------------------------------
    # Register invoice
    # ---------------------------------------------------------

    def register_invoice(
        self,
        payload: dict,
    ) -> dict:

        data = self._post(
            "/invoices",
            payload,
        )

        return data