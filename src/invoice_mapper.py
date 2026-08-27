from .invoice_schema import Invoice


def invoice_to_api_payload(
    invoice: Invoice,
    partner_code: str,
    tax_codes: dict[int, str],
) -> dict:

    lines = []

    for line in invoice.lines:

        tax_code = tax_codes.get(
            line.tax_rate
        )

        if tax_code is None:
            raise ValueError(
                f"Unsupported tax rate: "
                f"{line.tax_rate}%"
            )

        lines.append(
            {
                "description": line.description or " ",
                "quantity": line.quantity,
                "unit": line.unit,
                "unit_price": line.unit_price,
                "amount": line.amount,
                "tax_code": tax_code,
            }
        )

    return {
        "partner_code": partner_code,

        "invoice_number": invoice.invoice_number,

        "issue_date": invoice.issue_date,

        "due_date": invoice.due_date,

        "currency": invoice.currency,

        "lines": lines,

        "subtotal": invoice.subtotal,

        "tax_amount": invoice.tax_amount,

        "total_amount": invoice.total_amount,
    }