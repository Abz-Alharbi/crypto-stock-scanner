import os
import re

DEFAULT_CONFIDENCE_THRESHOLD = 0.50
INCONCLUSIVE_PATTERNS = {"", "none", "neutral", "inconclusive", "no_pattern", "no pattern"}


def _confidence_threshold():
    try:
        return float(os.getenv("YOLO_CONFIDENCE_THRESHOLD", DEFAULT_CONFIDENCE_THRESHOLD))
    except (TypeError, ValueError):
        return DEFAULT_CONFIDENCE_THRESHOLD


def resolve_pattern_signal(yolo_results, talib_patterns, confidence_threshold=None):
    threshold = _confidence_threshold() if confidence_threshold is None else float(confidence_threshold)
    concrete_talib_patterns = _concrete_talib_patterns(talib_patterns)
    candidates = []

    for result in yolo_results or []:
        confidence = float(result.get("confidence") or 0)
        if confidence < threshold:
            continue

        pattern = result.get("label") or result.get("pattern")
        normalized_pattern = _normalize_pattern(pattern)
        talib_confirmation = normalized_pattern in concrete_talib_patterns
        talib_conflict = bool(concrete_talib_patterns) and not talib_confirmation

        candidates.append(
            {
                "signal_priority": 1 if talib_confirmation else 2,
                "pattern": pattern,
                "confidence": confidence,
                "source_badge": "YOLOv8 + TA-Lib" if talib_confirmation else "YOLOv8",
                "bounding_boxes": [result.get("bbox")] if result.get("bbox") is not None else [],
                "talib_confirmation": talib_confirmation,
                "talib_conflict": talib_conflict,
            }
        )

    if not candidates:
        return _empty_signal()

    candidates.sort(key=lambda item: (item["signal_priority"], -item["confidence"]))
    best = candidates[0]
    best["bounding_boxes"] = [
        candidate["bounding_boxes"][0]
        for candidate in candidates
        if candidate["pattern"] == best["pattern"] and candidate["bounding_boxes"]
    ]
    return best


def _empty_signal():
    return {
        "signal_priority": None,
        "pattern": None,
        "confidence": None,
        "source_badge": None,
        "bounding_boxes": [],
        "talib_confirmation": False,
        "talib_conflict": False,
    }


def _concrete_talib_patterns(talib_patterns):
    patterns = set()
    for item in talib_patterns or []:
        pattern = _extract_pattern(item)
        normalized = _normalize_pattern(pattern)
        if normalized not in INCONCLUSIVE_PATTERNS:
            patterns.add(normalized)
    return patterns


def _extract_pattern(item):
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        return item.get("pattern") or item.get("label") or item.get("name") or item.get("signal") or ""
    return ""


def _normalize_pattern(value):
    normalized = str(value or "").strip().lower()
    normalized = re.sub(r"[^a-z0-9]+", "_", normalized)
    return normalized.strip("_")


resolve = resolve_pattern_signal
