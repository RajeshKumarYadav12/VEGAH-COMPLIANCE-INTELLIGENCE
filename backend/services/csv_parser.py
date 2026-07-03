"""
VEGAH Compliance Intelligence — CSV/JSON Capability Matrix Parser
Parses the company's uploaded capability matrix into structured Capability objects.
Supports both CSV and JSON formats, with flexible column name mapping.
"""

from __future__ import annotations

import csv
import io
import json
import logging
from pathlib import Path
from typing import Union

from models.schemas import Capability

logger = logging.getLogger(__name__)


# Column aliases — maps common variations to our standard field names
COLUMN_ALIASES: dict[str, str] = {
    # capability_id
    "id": "capability_id",
    "cap_id": "capability_id",
    "capability_id": "capability_id",
    # name
    "name": "name",
    "capability": "name",
    "capability_name": "name",
    "service": "name",
    "offering": "name",
    # category
    "category": "category",
    "domain": "category",
    "area": "category",
    "type": "category",
    # description
    "description": "description",
    "details": "description",
    "summary": "description",
    "overview": "description",
    # certifications
    "certifications": "certifications",
    "certs": "certifications",
    "standards": "certifications",
    "compliance": "certifications",
    # technologies
    "technologies": "technologies",
    "tech_stack": "technologies",
    "tech": "technologies",
    "tools": "technologies",
    # maturity_level
    "maturity_level": "maturity_level",
    "maturity": "maturity_level",
    "status": "maturity_level",
    "readiness": "maturity_level",
    # applicable_industries
    "applicable_industries": "applicable_industries",
    "industries": "applicable_industries",
    "sectors": "applicable_industries",
    "verticals": "applicable_industries",
    # case_studies
    "case_studies": "case_studies",
    "references": "case_studies",
    "clients": "case_studies",
    "projects": "case_studies",
}


def _normalize_header(raw_header: str) -> str:
    """Normalizes a column header to a standard field name."""
    normalized = raw_header.strip().lower().replace(" ", "_").replace("-", "_")
    return COLUMN_ALIASES.get(normalized, normalized)


def _parse_list_field(value: Union[str, list, None]) -> list[str]:
    """Parses a string-encoded list field (e.g., 'ISO 27001|SOC 2') into a Python list."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if v]
    # Try JSON array first
    stripped = value.strip()
    if stripped.startswith("["):
        try:
            parsed = json.loads(stripped)
            return [str(v).strip() for v in parsed if v]
        except json.JSONDecodeError:
            pass
    # Fall back to delimiter splitting
    for delimiter in ["|", ";", ","]:
        if delimiter in stripped:
            return [v.strip() for v in stripped.split(delimiter) if v.strip()]
    # Single value
    return [stripped] if stripped else []


class CapabilityParser:
    """
    Parses CSV or JSON capability matrix files into list[Capability].
    Auto-generates capability_ids if missing.
    """

    def parse(self, file_path: str | Path) -> list[Capability]:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Capability file not found: {file_path}")

        suffix = path.suffix.lower()
        if suffix == ".csv":
            return self._parse_csv(path)
        elif suffix in (".json", ".jsonl"):
            return self._parse_json(path)
        else:
            raise ValueError(f"Unsupported file format: {suffix}. Use .csv or .json")

    def _read_file_content(self, path: Path) -> str:
        for enc in ["utf-8-sig", "utf-16", "cp1252", "iso-8859-1"]:
            try:
                with open(path, "r", encoding=enc, newline="") as f:
                    return f.read()
            except UnicodeDecodeError:
                continue
        raise ValueError(f"Could not decode file {path} with common encodings.")

    def _parse_csv(self, path: Path) -> list[Capability]:
        capabilities: list[Capability] = []
        content = self._read_file_content(path)

        # Normalize null bytes that can appear in some exported CSV files
        content = content.replace("\x00", "")

        # Auto-detect delimiter to support CSVs exported with ;, |, or tab
        delimiter = ","
        sample = content[:4096]
        try:
            sniffed = csv.Sniffer().sniff(sample, delimiters=",;|\t")
            delimiter = sniffed.delimiter
        except csv.Error:
            delimiter = ","

        f = io.StringIO(content, newline="")
        reader = csv.DictReader(f, delimiter=delimiter)
        if not reader.fieldnames:
            raise ValueError("CSV file is empty or has no headers.")

        # Build normalized header map
        header_map = {raw: _normalize_header(raw) for raw in reader.fieldnames}
        logger.info(f"CSV delimiter detected: '{delimiter}'")
        logger.info(f"CSV headers mapped: {header_map}")

        for idx, row in enumerate(reader):
            normalized_row = {header_map[k]: v for k, v in row.items() if k in header_map}
            cap = self._build_capability(normalized_row, idx)
            if cap:
                capabilities.append(cap)

        logger.info(f"Parsed {len(capabilities)} capabilities from CSV.")
        return capabilities

    def _parse_json(self, path: Path) -> list[Capability]:
        capabilities: list[Capability] = []
        content = self._read_file_content(path)
        data = json.loads(content)

        # Support both root array and {"capabilities": [...]} wrapper
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = data.get("capabilities", data.get("data", [data]))
        else:
            raise ValueError("JSON must be a root array or object with 'capabilities' key.")

        for idx, item in enumerate(items):
            # Normalize keys
            normalized = {_normalize_header(k): v for k, v in item.items()}
            cap = self._build_capability(normalized, idx)
            if cap:
                capabilities.append(cap)

        logger.info(f"Parsed {len(capabilities)} capabilities from JSON.")
        return capabilities

    def _build_capability(self, row: dict, idx: int) -> Capability | None:
        """Constructs a Capability from a normalized dict row."""
        try:
            cap_id = row.get("capability_id", "").strip() or f"CAP-{idx + 1:04d}"
            name = row.get("name", "").strip()
            description = row.get("description", "").strip()

            # Fallback for non-standard CSVs: infer fields from the first non-empty columns.
            if not name or not description:
                raw_values = [
                    str(v).strip()
                    for v in row.values()
                    if v is not None and str(v).strip()
                ]
                if not name and raw_values:
                    name = raw_values[0]
                if not description:
                    description = raw_values[1] if len(raw_values) > 1 else name

            if not name and not description:
                logger.warning(f"Row {idx} skipped — no name or description.")
                return None

            return Capability(
                capability_id=cap_id,
                name=name or f"Capability {idx + 1}",
                category=row.get("category", "general").strip(),
                description=description or name,
                certifications=_parse_list_field(row.get("certifications")),
                technologies=_parse_list_field(row.get("technologies")),
                maturity_level=row.get("maturity_level", "production").strip(),
                applicable_industries=_parse_list_field(row.get("applicable_industries")),
                case_studies=_parse_list_field(row.get("case_studies")),
            )
        except Exception as e:
            logger.error(f"Failed to parse row {idx}: {e}")
            return None

    def capabilities_to_text_chunks(self, capabilities: list[Capability]) -> list[dict]:
        """
        Converts capabilities into text chunks ready for embedding.
        Each chunk contains rich context for better semantic search quality.
        """
        chunks = []
        for cap in capabilities:
            text_parts = [
                f"Capability: {cap.name}",
                f"Category: {cap.category}",
                f"Description: {cap.description}",
            ]
            if cap.certifications:
                text_parts.append(f"Certifications & Standards: {', '.join(cap.certifications)}")
            if cap.technologies:
                text_parts.append(f"Technologies: {', '.join(cap.technologies)}")
            if cap.applicable_industries:
                text_parts.append(f"Applicable Industries: {', '.join(cap.applicable_industries)}")
            if cap.case_studies:
                text_parts.append(f"Case Studies / References: {', '.join(cap.case_studies)}")
            text_parts.append(f"Maturity Level: {cap.maturity_level}")

            chunks.append({
                "capability_id": cap.capability_id,
                "capability_name": cap.name,
                "text": "\n".join(text_parts),
                "metadata": {
                    "category": cap.category,
                    "maturity_level": cap.maturity_level,
                    "certifications": cap.certifications,
                    "technologies": cap.technologies,
                },
            })
        return chunks
