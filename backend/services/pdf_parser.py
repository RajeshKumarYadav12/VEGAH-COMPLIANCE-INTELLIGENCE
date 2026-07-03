"""
VEGAH Compliance Intelligence — PDF Parser Service
Extracts clean text and metadata from uploaded RFP PDF files.
Uses pdfplumber as primary (handles tables well) with pymupdf fallback.
"""

from __future__ import annotations

import io
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

import pdfplumber
import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


@dataclass
class PDFParseResult:
    """Result of parsing a PDF file."""
    full_text: str
    page_count: int
    pages: list[str] = field(default_factory=list)      # Per-page text
    tables: list[list[list[str]]] = field(default_factory=list)  # Extracted tables
    metadata: dict = field(default_factory=dict)
    file_size_kb: float = 0.0
    is_scanned: bool = False
    warnings: list[str] = field(default_factory=list)


class PDFParser:
    """
    Robust PDF text extractor supporting both digital and partially-scanned PDFs.
    Strategy:
      1. Try pdfplumber (best for tables + structured text)
      2. Fall back to PyMuPDF if pdfplumber yields poor results
      3. Flag as scanned if neither extracts meaningful text
    """

    MIN_TEXT_THRESHOLD = 50  # chars per page to consider it "text-extractable"

    def parse(self, file_path: str | Path) -> PDFParseResult:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF not found: {file_path}")

        file_size_kb = path.stat().st_size / 1024
        logger.info(f"Parsing PDF: {path.name} ({file_size_kb:.1f} KB)")

        # Primary: pdfplumber
        result = self._parse_with_pdfplumber(path)
        result.file_size_kb = file_size_kb

        # Fallback: PyMuPDF if text is too sparse
        avg_chars = len(result.full_text) / max(result.page_count, 1)
        if avg_chars < self.MIN_TEXT_THRESHOLD:
            logger.warning(f"pdfplumber returned sparse text ({avg_chars:.0f} chars/page). Trying PyMuPDF.")
            fallback = self._parse_with_pymupdf(path)
            fallback.file_size_kb = file_size_kb
            if len(fallback.full_text) > len(result.full_text):
                fallback.tables = result.tables  # Keep tables from pdfplumber
                return fallback
            result.is_scanned = True
            result.warnings.append(
                "Document appears to be scanned or image-based. OCR not supported — text extraction may be incomplete."
            )

        return result

    def _parse_with_pdfplumber(self, path: Path) -> PDFParseResult:
        pages_text: list[str] = []
        all_tables: list[list[list[str]]] = []
        metadata: dict = {}

        with pdfplumber.open(str(path)) as pdf:
            metadata = pdf.metadata or {}
            for page in pdf.pages:
                # Extract text
                text = page.extract_text(x_tolerance=3, y_tolerance=3) or ""
                pages_text.append(text)

                # Extract tables (returns list of list of list of str)
                for table in page.extract_tables():
                    if table:
                        # Clean None cells
                        cleaned = [
                            [cell if cell is not None else "" for cell in row]
                            for row in table
                        ]
                        all_tables.append(cleaned)

        full_text = "\n\n".join(pages_text)

        return PDFParseResult(
            full_text=full_text,
            page_count=len(pages_text),
            pages=pages_text,
            tables=all_tables,
            metadata=metadata,
        )

    def _parse_with_pymupdf(self, path: Path) -> PDFParseResult:
        pages_text: list[str] = []

        doc = fitz.open(str(path))
        for page in doc:
            text = page.get_text("text")
            pages_text.append(text or "")
        doc.close()

        full_text = "\n\n".join(pages_text)

        return PDFParseResult(
            full_text=full_text,
            page_count=len(pages_text),
            pages=pages_text,
        )

    def get_metadata_summary(self, result: PDFParseResult) -> dict:
        """Returns a human-readable metadata dict for logging and frontend display."""
        return {
            "page_count": result.page_count,
            "file_size_kb": round(result.file_size_kb, 2),
            "total_characters": len(result.full_text),
            "total_words": len(result.full_text.split()),
            "tables_found": len(result.tables),
            "is_scanned": result.is_scanned,
            "title": result.metadata.get("Title", "Unknown"),
            "author": result.metadata.get("Author", "Unknown"),
            "warnings": result.warnings,
        }
