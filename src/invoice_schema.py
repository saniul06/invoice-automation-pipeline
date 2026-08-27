from typing import Optional

from pydantic import BaseModel, Field


class InvoiceLine(BaseModel):

    description: str

    quantity: Optional[int] = None

    unit: Optional[str] = None

    unit_price: Optional[int] = None

    amount: int

    tax_rate: int = Field(
        description="8 or 10"
    )


class Invoice(BaseModel):

    supplier_name: str

    invoice_number: str

    issue_date: str

    due_date: str

    currency: str

    lines: list[InvoiceLine]

    subtotal: int

    tax_amount: int

    total_amount: int