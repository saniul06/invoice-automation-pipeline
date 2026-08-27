from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import fitz
import numpy as np
from PIL import Image
from paddleocr import PaddleOCR


@dataclass
class ExtractionResult:
    text: str
    method: str
    confidence: float | None


class DocumentExtractor:

    SUPPORTED_EXTENSIONS = {
        ".pdf",
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
    }

    def __init__(self):
        print("Initializing PaddleOCR...")

        self.ocr = PaddleOCR(
            lang="japan",
        )

        print("PaddleOCR initialized.")

    # ==================================================
    # PUBLIC
    # ==================================================

    def extract(
        self,
        file_path: str,
    ) -> ExtractionResult:

        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(
                f"File not found: {path}"
            )

        extension = path.suffix.lower()

        if extension not in self.SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported file type: {extension}"
            )

        if extension == ".pdf":
            return self._extract_pdf(path)

        return self._extract_image(path)

    # ==================================================
    # PDF
    # ==================================================

    def _extract_pdf(
        self,
        path: Path,
    ) -> ExtractionResult:

        document = fitz.open(path)

        try:
            text = self._extract_pdf_text(
                document
            )

            if self._is_meaningful_text(text):

                print(
                    "Using embedded PDF text."
                )

                return ExtractionResult(
                    text=text,
                    method="pdf_text",
                    confidence=None,
                )

            print(
                "No usable PDF text layer found."
            )

            print(
                "Rendering PDF pages for OCR..."
            )

            return self._ocr_pdf(document)

        finally:
            document.close()

    def _extract_pdf_text(
        self,
        document,
    ) -> str:

        pages = []

        for page in document:

            text = page.get_text("text")

            if text:
                pages.append(text)

        return "\n\n".join(pages).strip()

    # ==================================================
    # SCANNED PDF
    # ==================================================

    def _ocr_pdf(
        self,
        document,
    ) -> ExtractionResult:

        page_texts = []
        confidence_values = []

        for page_number, page in enumerate(document):

            print(
                f"OCR page {page_number + 1}..."
            )

            # PDF points are 72 DPI.
            # Render at approximately 300 DPI.
            zoom = 300 / 72

            matrix = fitz.Matrix(
                zoom,
                zoom,
            )

            pixmap = page.get_pixmap(
                matrix=matrix,
                alpha=False,
            )

            # Convert PyMuPDF Pixmap → NumPy
            image = np.frombuffer(
                pixmap.samples,
                dtype=np.uint8,
            )

            image = image.reshape(
                pixmap.height,
                pixmap.width,
                pixmap.n,
            )

            # PaddleOCR expects an ndarray.
            result = self._ocr_numpy_image(
                image
            )

            page_texts.append(
                result.text
            )

            if result.confidence is not None:
                confidence_values.append(
                    result.confidence
                )

        confidence = None

        if confidence_values:
            confidence = (
                sum(confidence_values)
                / len(confidence_values)
            )

        return ExtractionResult(
            text="\n\n".join(
                page_texts
            ).strip(),
            method="pdf_ocr",
            confidence=confidence,
        )

    # ==================================================
    # IMAGE
    # ==================================================

    def _extract_image(
        self,
        path: Path,
    ) -> ExtractionResult:

        print(
            "Reading image..."
        )

        # PIL is fine for opening the image,
        # but PaddleOCR wants ndarray or str.
        pil_image = Image.open(path)

        # Convert to RGB first.
        pil_image = pil_image.convert("RGB")

        # PIL → NumPy
        numpy_image = np.array(
            pil_image
        )

        return self._ocr_numpy_image(
            numpy_image
        )

    # ==================================================
    # OCR
    # ==================================================

    def _ocr_numpy_image(
        self,
        image: np.ndarray,
    ) -> ExtractionResult:

        print(
            "Running PaddleOCR..."
        )

        results = self.ocr.predict(
            image
        )

        texts = []
        scores = []

        for page_result in results:

            data = page_result.json

            if not data:
                continue

            if isinstance(data, str):

                import json

                data = json.loads(data)

            res = data.get(
                "res",
                data,
            )

            rec_texts = res.get(
                "rec_texts",
                [],
            )

            rec_scores = res.get(
                "rec_scores",
                [],
            )

            texts.extend(
                rec_texts
            )

            scores.extend(
                rec_scores
            )

        text = "\n".join(
            texts
        ).strip()

        confidence = None

        if scores:

            confidence = (
                sum(scores)
                / len(scores)
            )

        return ExtractionResult(
            text=text,
            method="ocr",
            confidence=confidence,
        )

    # ==================================================
    # HELPERS
    # ==================================================

    @staticmethod
    def _is_meaningful_text(
        text: str,
    ) -> bool:

        if not text:
            return False

        compact = "".join(
            text.split()
        )

        return len(compact) >= 50