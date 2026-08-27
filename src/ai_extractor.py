import os

from google import genai
from google.genai import types

from .invoice_schema import Invoice


PROMPT = """
You extract structured information from Japanese
business invoices.

The input is text extracted locally from a PDF or
image using PDF text extraction or OCR.

Japanese labels include:

- 請求書 / 御請求書 = Invoice
- 請求書番号 = Invoice number
- 発行日 = Issue date
- お支払期日 = Due date
- 品名・摘要 = Description
- 数量 = Quantity
- 単位 = Unit
- 単価 = Unit price
- 金額 = Amount
- 小計 = Subtotal
- 消費税 = Consumption tax amount
- 税率 = Tax rate
- 合計 = Total invoice amount
- 登録番号 = Japanese tax registration number
- 御中 = Addressed-to company
- お振込先 = Bank transfer / payment destination information

Rules:

- Do not invent information.
- Currency is JPY.
- Amounts are integer yen.
- Dates must use YYYY-MM-DD.
- Tax rate must be 8 or 10.
- Extract all identifiable invoice lines.
- Preserve descriptions.
- If optional information is unavailable,
  return null.
- OCR may contain mistakes. Use surrounding
  context to resolve obvious OCR errors.
- Do not invent values.
"""


class InvoiceAIExtractor:

    def __init__(self, api_key):
        
        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not configured."
            )

        self.client = genai.Client(
            api_key=api_key
        )

    def extract(
        self,
        text: str,
    ) -> Invoice:\


        # return {"supplier_name":"株式会社山田製作所","invoice_number":"YM-2026-0107","issue_date":"2026-01-07","due_date":"2026-02-28","currency":"JPY","lines":[{"description":"精密部品A-100","quantity":120,"unit":"個","unit_price":1250,"amount":150000,"tax_rate":10},{"description":"精密部品B-220","quantity":40,"unit":"個","unit_price":3400,"amount":136000,"tax_rate":10},{"description":"梱包・輸送費","quantity":0,"unit":"式","unit_price":0,"amount":18000,"tax_rate":10}],"subtotal":304000,"tax_amount":30400,"total_amount":334400}

        response = (
            self.client.models.generate_content(
                model="gemini-3.6-flash",
                contents=f"""
{PROMPT}

Invoice text:

-------------------------

{text}

-------------------------
""",
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=Invoice,
                    temperature=0,
                ),
            )
        )

        if response.parsed:
            
            return response.parsed

        if not response.text:

            raise RuntimeError(
                "Gemini returned no response."
            )

        return Invoice.model_validate_json(
            response.text
        )