import unicodedata
from dataclasses import dataclass

from .accounting_client import (
    AccountingAPIError,
    AccountingClient,
)
from .invoice_schema import Invoice


@dataclass
class ValidationResult:
    valid: bool
    partner_code: str | None
    errors: list[str]


@dataclass
class PartnerMatch:
    partner_code: str | None
    status: str


class InvoiceValidator:
    """
    Validates an AI-extracted invoice against:

    - Pydantic schema
    - Accounting partner master
    - Accounting tax-code master
    - Existing invoices
    - Accounting system calculation rules
    """

    def __init__(
        self,
        accounting_client: AccountingClient,
    ):
        self.accounting_client = accounting_client

        # Loaded from accounting API.
        self.partners: list[dict] = []

        # Maps invoice tax rate (%) to accounting tax code.
        #
        # Example:
        #
        # {
        #     10: "T10",
        #     8: "T08",
        # }
        #
        self.tax_codes: dict[int, str] = {}

        # Maps accounting tax code to its rate.
        #
        # Example:
        #
        # {
        #     "T10": 0.10,
        #     "T08": 0.08,
        # }
        #
        # This is used when calculating tax.
        self.tax_rates: dict[str, float] = {}

        self.registered_invoices: list[dict] = []

    # ---------------------------------------------------------
    # Public API
    # ---------------------------------------------------------

    def validate(
        self,
        invoice: Invoice,
    ) -> ValidationResult:

        errors: list[str] = []

        # -----------------------------------------------------
        # Load master/reference data from accounting system
        # -----------------------------------------------------

        try:

            self.partners = (
                self.accounting_client.get_partners()
            )

            self._load_tax_codes()

            self.registered_invoices = (
                self.accounting_client.get_invoices()
            )

        except AccountingAPIError as exc:

            return ValidationResult(
                valid=False,
                partner_code=None,
                errors=[
                    f"Could not load accounting data: {exc}"
                ],
            )

        # -----------------------------------------------------
        # Normalize extracted data
        # -----------------------------------------------------

        self._normalize_invoice(invoice)

        # -----------------------------------------------------
        # Supplier
        # -----------------------------------------------------

        partner_match = self._find_partner_code(
            invoice.supplier_name
        )

        if partner_match.status == "NOT_FOUND":

            errors.append(
                "Supplier could not be matched to "
                "the accounting partner master: "
                f"{invoice.supplier_name!r}"
            )

        elif partner_match.status == "AMBIGUOUS":

            errors.append(
                "Supplier name matched multiple "
                "partners and requires human review: "
                f"{invoice.supplier_name!r}"
            )

        partner_code = partner_match.partner_code

        # -----------------------------------------------------
        # Invoice number
        # -----------------------------------------------------

        if (
            invoice.invoice_number is None
            or not invoice.invoice_number.strip()
        ):
            errors.append(
                "Invoice number is missing"
            )

        # -----------------------------------------------------
        # Dates
        # -----------------------------------------------------

        if invoice.issue_date is None:

            errors.append(
                "Issue date is missing"
            )

        if invoice.due_date is None:

            errors.append(
                "Due date is missing"
            )

        if (
            invoice.issue_date is not None
            and invoice.due_date is not None
            and invoice.due_date < invoice.issue_date
        ):

            errors.append(
                "Due date precedes issue date"
            )

        # -----------------------------------------------------
        # Currency
        # -----------------------------------------------------

        if invoice.currency != "JPY":

            errors.append(
                f"Unsupported currency: "
                f"{invoice.currency!r}. "
                f"Only JPY is supported."
            )

        # -----------------------------------------------------
        # Lines
        # -----------------------------------------------------

        errors.extend(
            self._validate_lines(invoice)
        )

        # -----------------------------------------------------
        # Tax rates
        # -----------------------------------------------------

        errors.extend(
            self._validate_tax_rates(invoice)
        )

        # -----------------------------------------------------
        # Subtotal
        # -----------------------------------------------------

        calculated_subtotal = (
            self._calculate_subtotal(invoice)
        )

        if invoice.subtotal is None:

            errors.append(
                "Subtotal is missing"
            )

        elif invoice.subtotal != calculated_subtotal:

            errors.append(
                "Subtotal mismatch: "
                f"invoice={invoice.subtotal}, "
                f"calculated={calculated_subtotal}"
            )

        # -----------------------------------------------------
        # Tax
        # -----------------------------------------------------

        calculated_tax = self._calculate_tax(
            invoice
        )

        if invoice.tax_amount is None:

            errors.append(
                "Tax amount is missing"
            )

        elif invoice.tax_amount != calculated_tax:

            errors.append(
                "Tax mismatch: "
                f"invoice={invoice.tax_amount}, "
                f"calculated={calculated_tax}"
            )

        # -----------------------------------------------------
        # Total
        # -----------------------------------------------------

        calculated_total = (
            calculated_subtotal
            + calculated_tax
        )

        if invoice.total_amount is None:

            errors.append(
                "Total amount is missing"
            )

        elif invoice.total_amount != calculated_total:

            errors.append(
                "Total mismatch: "
                f"invoice={invoice.total_amount}, "
                f"calculated={calculated_total}"
            )

        # -----------------------------------------------------
        # Duplicate
        # -----------------------------------------------------

        if (
            partner_code is not None
            and invoice.invoice_number
            and self._is_duplicate(
                partner_code=partner_code,
                invoice_number=invoice.invoice_number,
            )
        ):

            errors.append(
                "Duplicate invoice: invoice number "
                f"{invoice.invoice_number!r} is already "
                "registered for this supplier"
            )

        # -----------------------------------------------------
        # Final result
        # -----------------------------------------------------

        return ValidationResult(
            valid=len(errors) == 0,
            partner_code=partner_code,
            errors=errors,
        )

    # ---------------------------------------------------------
    # Normalization
    # ---------------------------------------------------------

    def _normalize_invoice(
        self,
        invoice: Invoice,
    ) -> None:

        # API allows empty description.
        #
        # Instead of sending "" or None, use a single space.
        for line in invoice.lines:

            if (
                line.description is None
                or not line.description.strip()
            ):

                line.description = " "

    # ---------------------------------------------------------
    # Supplier matching
    # ---------------------------------------------------------

    @staticmethod
    def _normalize_japanese_text(
        value: str,
    ) -> str:

        """
        Normalize Japanese supplier names.

        NFKC helps normalize things such as:
        - full-width / half-width characters
        - compatibility characters

        Whitespace is removed because OCR may introduce
        unnecessary spaces.
        """

        value = unicodedata.normalize(
            "NFKC",
            value,
        )

        return "".join(value.split())

    def _find_partner_code(
        self,
        supplier_name: str,
    ) -> PartnerMatch:

        target = self._normalize_japanese_text(
            supplier_name
        )

        matches = []

        for partner in self.partners:

            names = [
                partner["name"],
                *partner.get("aliases", []),
            ]

            for name in names:

                normalized_name = (
                    self._normalize_japanese_text(
                        name
                    )
                )

                if normalized_name == target:

                    matches.append(partner)

                    break

        # Exactly one match is required.

        if len(matches) == 0:

            return PartnerMatch(
                partner_code=None,
                status="NOT_FOUND",
            )

        if len(matches) > 1:

            return PartnerMatch(
                partner_code=None,
                status="AMBIGUOUS",
            )

        return PartnerMatch(
            partner_code=matches[0]["partner_code"],
            status="MATCHED",
        )

    # ---------------------------------------------------------
    # Tax codes
    # ---------------------------------------------------------

    def _load_tax_codes(self) -> None:

        tax_codes = (
            self.accounting_client.get_tax_codes()
        )

        self.tax_codes = {
            round(item["rate"] * 100): item["tax_code"]
            for item in tax_codes
        }

        self.tax_rates = {
            item["tax_code"]: item["rate"]
            for item in tax_codes
        }

    def get_tax_code(
        self,
        tax_rate: int,
    ) -> str | None:

        """
        Convert the tax rate extracted by Gemini
        into the accounting system's tax code.

        Example:

            10 -> "T10"
            8  -> "T08"
        """

        return self.tax_codes.get(
            tax_rate
        )

    def _validate_tax_rates(
        self,
        invoice: Invoice,
    ) -> list[str]:

        errors: list[str] = []

        for index, line in enumerate(
            invoice.lines,
            start=1,
        ):

            tax_code = self.get_tax_code(
                line.tax_rate
            )

            if tax_code is None:

                errors.append(
                    f"Line {index}: unsupported "
                    f"tax rate {line.tax_rate}%"
                )

        return errors

    # ---------------------------------------------------------
    # Line validation
    # ---------------------------------------------------------

    def _validate_lines(
        self,
        invoice: Invoice,
    ) -> list[str]:

        errors: list[str] = []

        # API requires at least one line.

        if not invoice.lines:

            errors.append(
                "Invoice must contain at least one line"
            )

            return errors

        for index, line in enumerate(
            invoice.lines,
            start=1,
        ):

            # Amount is required.
            #
            # IMPORTANT:
            #
            # We do NOT calculate:
            #
            # quantity * unit_price
            #
            # because both quantity and unit_price
            # may be null.

            if line.amount is None:

                errors.append(
                    f"Line {index}: amount is required"
                )

                continue

            # Negative amounts are not allowed.

            if line.amount < 0:

                errors.append(
                    f"Line {index}: amount cannot "
                    f"be negative"
                )

        return errors

    # ---------------------------------------------------------
    # Subtotal
    # ---------------------------------------------------------

    @staticmethod
    def _calculate_subtotal(
        invoice: Invoice,
    ) -> int:

        """
        Accounting API rule:

            subtotal = sum(line.amount)

        Quantity and unit_price are deliberately ignored.
        """

        return sum(
            line.amount
            for line in invoice.lines
            if line.amount is not None
        )

    # ---------------------------------------------------------
    # Tax
    # ---------------------------------------------------------

    def _calculate_tax(
        self,
        invoice: Invoice,
    ) -> int:

        """
        Accounting API rule:

        1. Map each line's tax_rate to the accounting
           tax_code.
        2. Group line amounts by tax code.
        3. Calculate subtotal for each tax code.
        4. Apply that tax code's rate.
        5. Round down.
        6. Sum the tax amounts.

        Example:

            T10 subtotal = 100001

            100001 * 0.10
            = 10000.1

            rounded down = 10000
        """

        subtotals: dict[str, int] = {}

        for line in invoice.lines:

            if line.amount is None:
                continue

            tax_code = self.get_tax_code(
                line.tax_rate
            )

            if tax_code is None:
                continue

            subtotals[tax_code] = (
                subtotals.get(tax_code, 0)
                + line.amount
            )

        total_tax = 0

        for tax_code, subtotal in subtotals.items():

            rate = self.tax_rates.get(
                tax_code
            )

            if rate is None:
                continue

            # JPY uses integer amounts.
            #
            # // performs floor division, which gives
            # the required rounded-down tax amount.

            tax_amount = int(
                subtotal * rate
            )

            total_tax += tax_amount

        return total_tax

    # ---------------------------------------------------------
    # Duplicate detection
    # ---------------------------------------------------------

    def _is_duplicate(
        self,
        partner_code: str,
        invoice_number: str,
    ) -> bool:

        for existing in self.registered_invoices:

            if (
                existing["partner_code"]
                == partner_code
                and
                existing["invoice_number"]
                == invoice_number
            ):

                return True

        return False