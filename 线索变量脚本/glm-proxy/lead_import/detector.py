from __future__ import annotations

from pathlib import Path

import pandas as pd

from .models import DetectedStore, DetectionResult
from .registry import StoreScriptRegistry


class StoreDetector:
    def __init__(self, registry: StoreScriptRegistry, threshold: float = 0.75):
        self.registry = registry
        self.threshold = threshold

    def detect(self, file_path: Path, original_filename: str | None = None) -> DetectionResult:
        display_name = original_filename or file_path.name
        text_parts = [display_name]
        matched_sources: dict[str, set[str]] = {}

        try:
            if file_path.suffix.lower() in [".xlsx", ".xls"]:
                with pd.ExcelFile(file_path) as excel:
                    text_parts.extend(excel.sheet_names)
                    for sheet_name in excel.sheet_names[:3]:
                        sample = pd.read_excel(excel, sheet_name=sheet_name, nrows=10)
                        text_parts.extend(str(col) for col in sample.columns)
                        text_parts.extend(sample.fillna("").astype(str).head(10).to_numpy().ravel().tolist())
            elif file_path.suffix.lower() == ".csv":
                sample = pd.read_csv(file_path, nrows=10)
                text_parts.extend(str(col) for col in sample.columns)
                text_parts.extend(sample.fillna("").astype(str).head(10).to_numpy().ravel().tolist())
        except Exception:
            pass

        haystacks = {
            "filename": display_name,
            "sheet_name": " ".join(text_parts[1:6]),
            "column": " ".join(text_parts),
            "content_keyword": " ".join(text_parts),
        }

        candidates = []
        for store in self.registry.list_stores():
            score = 0.0
            matched_by = []
            for source, haystack in haystacks.items():
                if any(keyword and keyword in haystack for keyword in store.keywords):
                    matched_by.append(source)
                    if source == "filename":
                        score += 0.80
                    elif source == "sheet_name":
                        score += 0.25
                    elif source == "column":
                        score += 0.15
                    else:
                        score += 0.20
            if matched_by:
                matched_sources[store.store_code] = set(matched_by)
                candidates.append(
                    DetectedStore(
                        store.store_code,
                        store.store_name,
                        min(score, 0.99),
                        sorted(matched_sources[store.store_code]),
                    )
                )

        candidates.sort(key=lambda item: item.confidence, reverse=True)
        detected = candidates[0] if candidates and candidates[0].confidence >= self.threshold else None
        return DetectionResult(detected_store=detected, candidate_stores=candidates)
