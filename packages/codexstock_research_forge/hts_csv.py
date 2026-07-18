from __future__ import annotations

import csv
import hashlib
import io
import math
from datetime import datetime
from pathlib import Path
from typing import Any

from .indicators import INDICATORS


BASE_COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]


def template(profile: str, indicator: str) -> dict[str, Any]:
    profile, indicator = profile.upper(), indicator.upper()
    if profile not in {"LS_HTS", "KIWOOM_HTS", "KIS"} or indicator not in INDICATORS:
        raise ValueError("unsupported HTS profile or indicator")
    outputs = [f"hts_{value}" for value in INDICATORS[indicator]["outputs"]]; columns = BASE_COLUMNS + outputs
    stream = io.StringIO(newline=""); csv.writer(stream, lineterminator="\n").writerow(columns)
    return {"ok": True, "profile": profile, "indicator": indicator, "columns": columns, "csv_header": stream.getvalue(), "required_market_row_count": 20, "required_reference_row_count": 10, "output_columns": outputs, "instructions": "Export chronological OHLCV and place HTS values in hts_* columns. Warmup cells may remain blank; at least ten rows must contain reference output values."}


def import_csv(csv_text: str, metadata: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(csv_text, str) or not csv_text.strip() or len(csv_text.encode("utf-8")) > 50_000_000:
        raise ValueError("HTS CSV must be non-empty and at most 50MB")
    profile, indicator = str(metadata.get("profile") or "").upper(), str(metadata.get("indicator") or "").upper()
    definition = template(profile, indicator); expected_columns = definition["columns"]
    reader = csv.DictReader(io.StringIO(csv_text.lstrip("\ufeff")))
    if reader.fieldnames != expected_columns or len(set(reader.fieldnames or [])) != len(expected_columns):
        raise ValueError("HTS CSV header does not exactly match the template")
    market_rows, references, last = [], [], ""
    for line_number, value in enumerate(reader, start=2):
        if None in value or any(cell is None for cell in value.values()): raise ValueError(f"HTS CSV row {line_number} has the wrong column count")
        timestamp = str(value["timestamp"]).strip(); parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        if parsed.tzinfo is None or timestamp <= last: raise ValueError("HTS CSV timestamps must be unique, increasing, and timezone-aware")
        last = timestamp; row = {"timestamp": timestamp}
        for key in BASE_COLUMNS[1:]:
            number = float(str(value[key]).replace(",", ""))
            if not math.isfinite(number) or (key != "volume" and number <= 0) or (key == "volume" and number < 0): raise ValueError(f"HTS CSV row {line_number} has invalid {key}")
            row[key] = number
        if row["high"] < max(row["open"], row["low"], row["close"]) or row["low"] > min(row["open"], row["high"], row["close"]): raise ValueError(f"HTS CSV row {line_number} has invalid OHLC ordering")
        market_rows.append(row); outputs = {}
        for output in INDICATORS[indicator]["outputs"]:
            cell = str(value[f"hts_{output}"]).strip()
            if cell:
                number = float(cell.replace(",", ""))
                if not math.isfinite(number): raise ValueError(f"HTS CSV row {line_number} has a non-finite reference")
                outputs[output] = number
        if outputs: references.append({"timestamp": timestamp, "outputs": outputs})
    if len(market_rows) < 20 or len(references) < 10: raise ValueError("HTS CSV requires at least 20 market rows and 10 reference rows")
    exported_at = str(metadata.get("exported_at") or ""); exported = datetime.fromisoformat(exported_at.replace("Z", "+00:00"))
    if exported.tzinfo is None: raise ValueError("HTS CSV exported_at must include timezone")
    source_name = Path(str(metadata.get("source_file_name") or "hts_export.csv")).name
    package = {"export_id": str(metadata.get("export_id") or ""), "profile": profile, "indicator": indicator, "parameters": dict(metadata.get("parameters") or {}), "symbol": str(metadata.get("symbol") or "").upper(), "timeframe": str(metadata.get("timeframe") or ""), "exported_at": exported.isoformat(), "source_file_name": source_name, "source_file_hash": f"sha256:{hashlib.sha256(csv_text.encode('utf-8')).hexdigest()}", "market_rows": market_rows, "reference_points": references, "absolute_tolerance": float(metadata.get("absolute_tolerance") if metadata.get("absolute_tolerance") is not None else 1e-6), "notes": str(metadata.get("notes") or "")}
    return {"ok": True, "package": package, "row_count": len(market_rows), "reference_row_count": len(references), "source_file_hash": package["source_file_hash"], "profile": profile, "indicator": indicator}
