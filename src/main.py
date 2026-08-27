import json
import os
from pathlib import Path

from .document_extractor import DocumentExtractor
from .ai_extractor import InvoiceAIExtractor

from .accounting_client import (
    AccountingClient,
    AccountingAPIError,
)

from .invoice_validator import InvoiceValidator
from .invoice_mapper import invoice_to_api_payload


INPUT_DIR = Path("/app/invoices")
OUTPUT_DIR = Path("/app/output")


SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
}


def main():

    print()
    print("======================================")
    print("Japanese Invoice Processor")
    print("======================================")
    print()

    # ---------------------------------------------------------
    # Environment
    # ---------------------------------------------------------

    gemini_api_key = os.getenv(
        "GEMINI_API_KEY", "AQ.Ab8RN6J5Xc2AUFg3Na-AiQmclQ6UKjXcZjRP3pTRcfZ92Vhr1Q"
    )

    accounting_api_url = os.getenv(
        "ACCOUNTING_API_URL",
        "http://host.docker.internal:8080",
    )

    accounting_api_key = os.getenv(
        "ACCOUNTING_API_KEY",
        "demo-key-1234"
    )

    if not gemini_api_key:

        print(
            "ERROR: GEMINI_API_KEY is not configured."
        )

        return

    # ---------------------------------------------------------
    # Find invoice files
    # ---------------------------------------------------------

    files = sorted(
        file
        for file in INPUT_DIR.iterdir()
        if (
            file.is_file()
            and file.suffix.lower()
            in SUPPORTED_EXTENSIONS
        )
    )

    print(
        f"Found {len(files)} invoice files."
    )

    if not files:

        print(
            "No invoices found."
        )

        return

    OUTPUT_DIR.mkdir(
        exist_ok=True
    )

    # ---------------------------------------------------------
    # Create components
    # ---------------------------------------------------------

    document_extractor = DocumentExtractor()

    ai_extractor = InvoiceAIExtractor(gemini_api_key)

    accounting_client = AccountingClient(
        base_url=accounting_api_url,
        api_key=accounting_api_key,
    )

    validator = InvoiceValidator(
        accounting_client=accounting_client,
    )

    results = []

    # ---------------------------------------------------------
    # Process invoices
    # ---------------------------------------------------------

    for file_path in files:

        print()
        print("--------------------------------------")
        print(
            f"Processing: {file_path.name}"
        )

        try:

            # ================================================
            # 1. LOCAL DOCUMENT EXTRACTION
            # ================================================

            extraction = (
                document_extractor.extract(
                    str(file_path)
                )
            )

            print(
                f"Method: {extraction.method}"
            )

            print(
                f"Characters: "
                f"{len(extraction.text)}"
            )

            if extraction.confidence is not None:

                print(
                    f"OCR confidence: "
                    f"{extraction.confidence:.3f}"
                )

            # Save raw extracted text

            text_path = (
                OUTPUT_DIR
                / f"{file_path.stem}.txt"
            )

            text_path.write_text(
                extraction.text,
                encoding="utf-8",
            )

            # ================================================
            # 2. AI STRUCTURED EXTRACTION
            # ================================================

            print(
                "Extracting structured data..."
            )

            invoice = (
                ai_extractor.extract(
                    extraction.text
                )
            )

            # ================================================
            # 3. VALIDATION
            # ================================================

            print(
                "Validating invoice..."
            )

            validation = (
                validator.validate(
                    invoice
                )
            )

            if validation.valid:

                status = "READY"

            else:

                status = "REVIEW"

            # ================================================
            # 4. REGISTER IF VALID
            # ================================================

            accounting_result = None

            if validation.valid:

                print(
                    "Validation passed."
                )

                print(
                    f"Partner code: "
                    f"{validation.partner_code}"
                )

                payload = (
                    invoice_to_api_payload(
                        invoice=invoice,
                        partner_code=validation.partner_code,
                        tax_codes=validator.tax_codes,
                    )
                )

                print(
                    "Registering invoice..."
                )

                try:

                    accounting_result = (
                        accounting_client.register_invoice(
                            payload
                        )
                    )

                    status = "REGISTERED"

                    print(
                        "Invoice registered successfully."
                    )

                    if accounting_result:

                        accounting_id = (
                            accounting_result.get(
                                "accounting_id"
                            )
                        )

                        if accounting_id:

                            print(
                                f"Accounting ID: "
                                f"{accounting_id}"
                            )

                except AccountingAPIError as api_error:

                    status = "API_ERROR"

                    print(
                        "Accounting API rejected "
                        "the invoice."
                    )

                    print(
                        f"  HTTP status: "
                        f"{api_error.status_code}"
                    )

                    print(
                        f"  Error code: "
                        f"{api_error.error_code}"
                    )

                    print(
                        f"  Message: "
                        f"{api_error}"
                    )

                    if api_error.details:

                        print(
                            f"  Details: "
                            f"{api_error.details}"
                        )

            else:

                print(
                    "Invoice requires human review."
                )

                for error in validation.errors:

                    print(
                        f"  ERROR: {error}"
                    )

            # ================================================
            # 5. SAVE RESULT
            # ================================================

            output = {

                "source_file":
                    file_path.name,

                "extraction": {

                    "method":
                        extraction.method,

                    "confidence":
                        extraction.confidence,
                },

                "status": status,

                "invoice":
                    invoice.model_dump(
                        mode="json"
                    ),

                "validation": {

                    "valid":
                        validation.valid,

                    "partner_code":
                        validation.partner_code,

                    "errors":
                        validation.errors,
                },

                "accounting": {

                    "registered":
                        status == "REGISTERED",

                    "response":
                        accounting_result,
                },
            }

            json_path = (
                OUTPUT_DIR
                / f"{file_path.stem}.json"
            )

            json_path.write_text(
                json.dumps(
                    output,
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            # ================================================
            # 6. DISPLAY SUMMARY
            # ================================================

            print(
                f"Supplier: "
                f"{invoice.supplier_name}"
            )

            print(
                f"Invoice number: "
                f"{invoice.invoice_number}"
            )

            print(
                f"Total: "
                f"¥{invoice.total_amount:,}"
            )

            print(
                f"Status: {status}"
            )

            results.append(
                {
                    "file":
                        file_path.name,

                    "status":
                        status,

                    "partner_code":
                        validation.partner_code,

                    "errors":
                        validation.errors,
                }
            )

        except Exception as error:

            # ================================================
            # UNEXPECTED ERROR
            # ================================================

            print(
                f"FAILED: {error}"
            )

            results.append(
                {
                    "file":
                        file_path.name,

                    "status":
                        "FAILED",

                    "error":
                        str(error),
                }
            )

    # ---------------------------------------------------------
    # Summary
    # ---------------------------------------------------------

    summary_path = (
        OUTPUT_DIR
        / "results.json"
    )

    summary_path.write_text(
        json.dumps(
            results,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print()
    print("======================================")
    print("Processing complete")
    print("======================================")

    for result in results:

        print(
            f"{result['file']}: "
            f"{result['status']}"
        )


if __name__ == "__main__":
    main()