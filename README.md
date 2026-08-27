# Submission

- **Name:** Saniul Islam
- **Submission date (YYYY-MM-DD):** 2026-08-27
- **Hours actually spent:** 12
- **Repository / how to run it:** https://github.com/saniul06/invoice-automation-pipeline.git

The application is Dockerized, You just need docker to run the project. Also don't forget to run the accounting server as well.

To run:

```bash
docker compose up --build
```

Place invoice files in:

```text
invoices/
```

Processed results ( Whether it is Completed / In Review / Failed ) are written to:

```text
output/
```

The application processes each invoice through:

1. Local text/OCR extraction
2. LLM-based structured extraction
3. Pydantic schema validation
4. Accounting-system validation
5. Invoice registration when validation succeeds
6. Error/review handling when validation fails

---

## 1. Understanding the request

The client's problem is to automate the processing of Japanese invoices and register the extracted information into an existing accounting system.

The input documents may be:

- PDFs containing selectable text
- Scanned PDFs
- Scanned image files

I understood that the main challenge is not only extracting text from invoices, but reliably converting that information into structured invoice data that satisfies the accounting system's constraints that should avoid dupliate invoice payment.

I therefore set out to build an end-to-end pipeline:

```text
Invoice
   ↓
Local text extraction / OCR
   ↓
Gemini structured extraction
   ↓
Pydantic validation
   ↓
Accounting-system validation
   ↓
 ┌───────────────┐
 │               │
Valid           Invalid
 │               │
 ↓               ↓
Register       Review
```

I treated the accounting API as the source of truth for supplier information, tax codes, and existing invoices.

I also deliberately kept accounting-specific decisions outside the LLM. For example, Gemini extracts a tax rate such as `10%`, while the application maps that rate to the accounting system's `T10` tax code.

---

## 2. What you would have asked the client

| What you wanted to ask                                             | The assumption you made                                                                                                     | Why                                                                                                                          |
| ------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| What should happen when an invoice has no description for a line?  | I assumed an empty description is allowed and represented it as a single space `" "` when sending it to the accounting API. | The API explicitly allows an empty-space description, so I did not make missing descriptions block otherwise valid invoices. |
| Will there be other types of documents besides those 3 types?      | I assumed the supplied documents are in 3 types only.                                                                       | Only 3 types of documents provided                                                                                           |
| What should happen if the supplier name matches multiple partners? | I assumed the invoice should not be registered and should require human review.                                             | Registering an invoice against the wrong supplier is more dangerous than requiring manual review.                            |

---

## 3. Scoping decisions

The assignment intentionally does not fit completely into 8 hours. I prioritized completing the core workflow and the accounting-system safety checks rather than building additional infrastructure or UI.

### What you built

#### 1. Local document extraction

- Text extraction from normal PDFs using PyMuPDF.
- OCR for scanned PDFs using PaddleOCR.
- OCR for scanned image files using PaddleOCR.
- Dockerized environment for reproducible OCR/Python dependencies.

#### 2. Structured invoice extraction

Gemini converts the extracted invoice text into a structured Pydantic invoice model.

The extracted fields include:

- Supplier name
- Invoice number
- Issue date
- Due date
- Line descriptions
- Quantity
- Unit
- Unit price
- Line amount
- Tax rate
- Subtotal
- Tax amount
- Total amount

#### 3. Deterministic validation

The application validates:

- Supplier existence
- Supplier aliases
- Ambiguous supplier matches
- Invoice number
- Dates
- Currency
- Line existence
- Line amount
- Negative amounts
- Tax rates
- Subtotal
- Tax
- Total
- Duplicate invoices

#### 4. Accounting API integration

Invoices that pass validation are transformed into the accounting API format and registered using `POST /invoices`.

#### 5. Error handling

Accounting API errors are captured and reported rather than treating a failed registration as successful.

#### 6. Output for verification

The application saves extracted text and structured validation results so the processing can be inspected afterward.

### What you left out, and why

#### 1. Human review UI

I did not build a web-based review interface.

Instead, invoices that fail validation are marked as:

```text
REVIEW
```

and their validation errors are saved.

I prioritized completing the extraction → validation → registration workflow first. A review UI would be useful in production but would consume a significant part of the available time.

#### 2. Sophisticated confidence scoring

I did not implement a separate field-level confidence framework.

Instead, I focused on deterministic validation for accounting-critical information.

For example, the LLM's tax information is checked against the accounting API's tax-code master.

#### 3. Production deployment

I did not deploy the application to AWS, GCP, or another cloud environment.

The assignment only contains 12 sample invoices, so a reproducible Docker environment was a higher priority.

#### 4. Support for non-invoice documents

I assumed the supplied files are invoices and limited the implementation to:

```text
PDF
JPG
JPEG
PNG
WEBP
```

#### 5. Large-scale processing infrastructure

I did not introduce queues, distributed workers, microservices, or a database.

The supplied workload is small, so these would add complexity without improving the core assignment.

---

## 4. Design and technology choices

### End-to-end flow

```text
                    ┌──────────────────┐
                    │ Invoice files    │
                    │ PDF / JPG / PNG  │
                    └────────┬─────────┘
                             │
                             ▼
                  ┌─────────────────────┐
                  │ Local extraction    │
                  │                     │
                  │ PyMuPDF             │
                  │ PaddleOCR           │
                  └──────────┬──────────┘
                             │
                             │ Extracted text
                             ▼
                  ┌─────────────────────┐
                  │ Gemini              │
                  │                     │
                  │ Text → Invoice      │
                  │ structured data     │
                  └──────────┬──────────┘
                             │
                             ▼
                  ┌─────────────────────┐
                  │ Pydantic            │
                  │ Schema validation   │
                  └──────────┬──────────┘
                             │
                             ▼
                  ┌─────────────────────┐
                  │ Invoice Validator   │
                  │                     │
                  │ Supplier matching  │
                  │ Tax validation      │
                  │ Amount validation  │
                  │ Duplicate check    │
                  └──────────┬──────────┘
                             │
                    ┌────────┴────────┐
                    │                 │
                  REVIEW             READY
                    │                 │
                    │                 ▼
                    │       ┌──────────────────┐
                    │       │ Accounting API   │
                    │       │ POST /invoices   │
                    │       └──────────────────┘
                    ▼
              Saved validation
                  errors
```

### Python

I chose Python because the task is primarily document processing, OCR, and structured data extraction. Python has mature libraries for PDF processing and OCR.

### PyMuPDF

I used PyMuPDF for PDFs containing selectable text.

This allows text to be extracted locally without sending the document to an external OCR service when OCR is unnecessary.

### PaddleOCR

I used PaddleOCR for scanned PDFs and images.

OCR runs locally, so invoice images do not need to be sent to a separate cloud OCR service.

I used Docker because OCR libraries can have native/runtime dependencies, and Docker makes the environment reproducible.

### Pydantic

I used Pydantic to define the expected invoice structure.

This creates a validation boundary between:

```text
LLM output
    ↓
Pydantic model
    ↓
Application logic
```

The LLM therefore does not directly control the structure sent to the accounting API.

### Gemini

I used Gemini for the semantic extraction step:

```text
Extracted invoice text
        ↓
Structured invoice data
```

I chose a cloud LLM because the assignment has only 12 invoices and the task requires understanding Japanese invoice content.

I used the available free/trial option during development to avoid the additional infrastructure required to host a local LLM.

### What I decided against

I decided against:

- External OCR APIs
- A database
- Message queues
- Microservices
- A web application
- A local LLM
- Production cloud deployment

because these were not necessary to demonstrate the core workflow within the 8-hour scope.

---

## 5. How you used AI, and how you checked it

### What you delegated to AI

I used AI during development for:

- Designing the invoice-processing pipeline
- Generating initial implementation ideas
- Working through PyMuPDF/PaddleOCR integration
- Creating and refining the Gemini prompt
- Debugging dependency issues
- Designing accounting API validation
- Identifying edge cases
- Reviewing error-handling approaches
- Reviewing parts of the implementation

I treated AI-generated code as a starting point rather than submitting it without review.

In particular, I manually reviewed the accounting validation and registration logic because errors in these areas can result in incorrect accounting records.

### How you verified the output

I used several layers of verification.

#### 1. Local extraction verification

The extracted text is saved to an output file.

This allows me to inspect:

```text
Original invoice
      ↓
Extracted text
```

before involving the LLM.

This helps distinguish OCR/extraction problems from LLM interpretation problems.

#### 2. Pydantic validation

The structured Gemini response is validated against the Pydantic invoice schema.

#### 3. Accounting master validation

Supplier and tax information are checked against the accounting API.

Supplier matching uses both:

```text
partner.name
partner.aliases
```

and normalizes Japanese text using Unicode NFKC normalization and whitespace removal.

#### 4. Deterministic amount validation

I do not trust the LLM's subtotal, tax, and total simply because it extracted those values.

The application recalculates them.

The subtotal is:

```text
sum(line.amount)
```

I deliberately do not calculate:

```text
quantity × unit_price
```

because those fields can be null.

Tax is calculated per tax code, on the subtotal for that tax code, with the result rounded down according to the accounting system's rules.

Finally:

```text
total = subtotal + tax
```

#### 5. Duplicate validation

The invoice number is checked against existing invoices for the matched supplier before registration.

### A case where the AI got it wrong

I did not observe a concrete Gemini extraction error in the 12 supplied invoices.

However, I deliberately treated LLM output as untrusted at the accounting boundary.

For example, the accounting API expects:

```text
T10
T08
```

while the invoice contains a tax rate such as:

```text
10%
```

I therefore do not allow Gemini to directly determine the accounting tax code.

Instead:

```text
Gemini
  ↓
tax_rate = 10
  ↓
Accounting API tax-code master
  ↓
T10
```

This prevents an LLM mistake from directly producing an invalid accounting tax code.

---

## 6. Integrating with the accounting system

I treated the accounting API as the source of truth for registration constraints.

Before registration, the application validates:

- Supplier
- Supplier aliases
- Tax rate
- Invoice number
- Dates
- Currency
- Line amounts
- Subtotal
- Tax
- Total
- Duplicate status

### Supplier matching

The supplier printed on the invoice may not exactly match the canonical partner name.

I normalize the Japanese text using Unicode NFKC normalization and whitespace removal, then compare it against the partner's:

```text
name
aliases
```

Only an unambiguous match produces a `partner_code`.

### Tax mapping

Gemini extracts a tax rate:

```text
10%
```

The accounting API provides:

```text
T10 → 10%
T08 → 8%
```

The application converts:

```text
10 → T10
8  → T08
```

before creating the API payload.

### Amount validation

I do not calculate:

```text
quantity × unit_price
```

because these fields may be null.

Instead:

```text
subtotal = sum(line.amount)
```

Tax is then calculated separately for each tax code and rounded down.

Finally:

```text
total = subtotal + tax
```

Only invoices that pass validation are sent to:

```text
POST /invoices
```

| Invoice              | Result     | How you handled it                                |
| -------------------- | ---------- | ------------------------------------------------- |
| Valid invoice        | Registered | Passed validation and sent to `POST /invoices`    |
| Unknown supplier     | Review     | Registration prevented and validation error saved |
| Ambiguous supplier   | Review     | Registration prevented and manual review required |
| Unknown tax rate     | Review     | Registration prevented                            |
| Amount mismatch      | Review     | Registration prevented                            |
| Duplicate invoice    | Review     | Registration prevented                            |
| Accounting API error | Failed     | Error captured and reported                       |

The application checks the accounting API response and does not assume that a request was successfully registered simply because the HTTP request was sent.

---

## 7. Cost, limits, and risk in production

### Cost per invoice

The main variable cost is the LLM call.

The processing cost can be considered approximately:

```text
LLM input tokens
+
LLM output tokens
+
compute/OCR cost
```

The PDF text extraction and OCR are performed locally, so there is no separate per-document OCR API cost.

The actual LLM cost depends on the selected model, token usage, and current pricing.

For production, I would measure the actual average input/output tokens per invoice before committing to a final cost estimate.

### Monthly cost at 1,000 invoices per month

At 1,000 invoices/month, I would expect the LLM cost to remain manageable if invoice sizes are similar to the supplied samples.

The main infrastructure concern would likely become OCR/CPU processing capacity rather than the accounting API.

I would measure:

```text
Average pages per invoice
OCR processing time per page
LLM tokens per invoice
Average processing time
```

before selecting production infrastructure.

### Processing time per invoice

Processing time depends on the document type.

A text-based PDF generally requires:

```text
PDF text extraction
      ↓
LLM
      ↓
Validation
      ↓
Accounting API
```

A scanned invoice additionally requires OCR:

```text
PDF/image
   ↓
OCR
   ↓
LLM
   ↓
Validation
   ↓
Accounting API
```

Therefore scanned documents are expected to take longer.

### Where this breaks first

I would expect the first bottlenecks to be:

1. OCR CPU capacity
2. LLM API rate limits
3. LLM cost/token usage
4. Accounting API rate limits

At 1,000 invoices/month, I would first measure the actual bottleneck before introducing distributed infrastructure.

### How you would find out if something was registered incorrectly

I would maintain an audit trail containing:

```text
Source invoice
     ↓
Extracted text
     ↓
Structured invoice
     ↓
Validation result
     ↓
Accounting API payload
     ↓
Accounting API response
```

This makes it possible to determine whether an incorrect registration originated from:

- OCR
- LLM extraction
- Validation
- Payload transformation
- Accounting API behavior

For production, I would also persist the accounting system's returned `accounting_id` together with the source invoice identifier.

---

## 8. What you would do with another 8 hours

### 1. Human review interface

I would build a small review UI showing:

```text
Original invoice
       +
Extracted fields
       +
Validation errors
```

The reviewer could correct the extracted fields and submit the corrected invoice for validation and registration.

This is the highest priority because OCR and LLM extraction cannot be assumed to be 100% reliable.

### 2. Better observability and extraction confidence

I would add structured logging and metrics for:

- OCR failures
- LLM failures
- Validation failures
- Accounting API failures
- Registration success rate
- Processing time
- Token usage

I would also investigate field-level confidence scoring for OCR/LLM output.

### 3. More reliable production processing

I would add:

- Retry handling with exponential backoff
- Idempotency protection
- Persistent processing state
- Better API failure recovery
- Queue-based processing if volume increases

The goal would be to prevent temporary failures from causing either lost invoices or accidental duplicate registrations.
