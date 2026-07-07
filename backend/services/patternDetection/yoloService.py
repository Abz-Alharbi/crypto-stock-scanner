import logging
import os
import threading
from pathlib import Path

import numpy as np
import requests

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MODEL_PATH = PROJECT_ROOT / "models" / "yolov8" / "model.pt"
DEFAULT_MODEL_URL = "https://huggingface.co/foduucom/stockmarket-pattern-detection-yolov8/resolve/main/model.pt"
DEFAULT_CONFIDENCE_THRESHOLD = 0.50
MIN_MODEL_BYTES = 1_000_000


def _env_confidence_threshold():
    try:
        return float(os.getenv("YOLO_CONFIDENCE_THRESHOLD", DEFAULT_CONFIDENCE_THRESHOLD))
    except (TypeError, ValueError):
        return DEFAULT_CONFIDENCE_THRESHOLD


def _env_bool(name, default):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class YOLOPatternService:
    def __init__(self, model_path=None, confidence_threshold=None, model_loader=None, model_url=None, auto_download=None):
        self.model_path = _resolve_model_path(model_path or os.getenv("YOLO_MODEL_PATH") or DEFAULT_MODEL_PATH)
        self.model_url = model_url or os.getenv("YOLO_MODEL_URL") or DEFAULT_MODEL_URL
        default_auto_download = os.getenv("FLASK_ENV", "").lower() != "testing"
        self.auto_download = (
            _env_bool("YOLO_AUTO_DOWNLOAD", default_auto_download)
            if auto_download is None
            else bool(auto_download)
        )
        self.confidence_threshold = (
            _env_confidence_threshold()
            if confidence_threshold is None
            else float(confidence_threshold)
        )
        self.model_loader = model_loader
        self._model = None
        self._lock = threading.Lock()
        self.last_error = None

    @property
    def is_loaded(self):
        return self._model is not None

    def load_model(self):
        with self._lock:
            if self._model is not None:
                return self._model

            if not self.model_path.exists():
                if self.auto_download:
                    self._download_model()
                if not self.model_path.exists():
                    self.last_error = {
                        "type": "model_missing",
                        "model_path": str(self.model_path),
                        "model_url": self.model_url,
                    }
                    logger.warning(
                        "YOLOv8 model not found at %s; pattern detection is disabled.",
                        self.model_path,
                        extra=self.last_error,
                    )
                    return None

            loader = self.model_loader or self._load_ultralytics_model
            try:
                self._model = loader(str(self.model_path))
            except Exception as exc:
                self.last_error = {
                    "type": "model_load_failed",
                    "model_path": str(self.model_path),
                    "exception_type": type(exc).__name__,
                    "exception_message": str(exc),
                }
                logger.exception("yolo_model_load_failed", extra=self.last_error)
                return None

            self.last_error = None
            logger.info("yolo_model_loaded", extra={"model_path": str(self.model_path)})
            return self._model

    def _download_model(self):
        if not self.model_url:
            return False

        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.model_path.with_suffix(f"{self.model_path.suffix}.download")
        try:
            logger.info(
                "yolo_model_download_started",
                extra={"model_url": self.model_url, "model_path": str(self.model_path)},
            )
            with requests.get(self.model_url, stream=True, timeout=(10, 120)) as response:
                response.raise_for_status()
                bytes_written = 0
                with temp_path.open("wb") as handle:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if not chunk:
                            continue
                        handle.write(chunk)
                        bytes_written += len(chunk)

            if bytes_written < MIN_MODEL_BYTES:
                raise RuntimeError(f"Downloaded model is too small ({bytes_written} bytes)")

            temp_path.replace(self.model_path)
            logger.info(
                "yolo_model_downloaded",
                extra={"model_path": str(self.model_path), "bytes": bytes_written},
            )
            return True
        except Exception as exc:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
            self.last_error = {
                "type": "model_download_failed",
                "model_url": self.model_url,
                "model_path": str(self.model_path),
                "exception_type": type(exc).__name__,
                "exception_message": str(exc),
            }
            logger.exception("yolo_model_download_failed", extra=self.last_error)
            return False

    def detect(self, image, confidence_threshold=None):
        if not isinstance(image, np.ndarray):
            raise ValueError("YOLO pattern detection expects a numpy array/OpenCV Mat.")
        if image.ndim not in {2, 3}:
            raise ValueError("YOLO pattern detection expects a 2D or 3D image array.")

        model = self._model or self.load_model()
        if model is None:
            raise RuntimeError("YOLOv8 pattern model is not loaded.")

        threshold = self.confidence_threshold if confidence_threshold is None else float(confidence_threshold)
        predictions = model.predict(source=image, verbose=False)
        return _parse_predictions(predictions, model, threshold)

    @staticmethod
    def _load_ultralytics_model(model_path):
        from ultralytics import YOLO

        return YOLO(model_path)


def _parse_predictions(predictions, model, threshold):
    detections = []
    for prediction in predictions or []:
        boxes = getattr(prediction, "boxes", None)
        if boxes is None:
            continue

        names = getattr(prediction, "names", None) or getattr(model, "names", {}) or {}
        for box in boxes:
            confidence = _to_float(getattr(box, "conf", None))
            if confidence is None or confidence < threshold:
                continue

            class_id = _to_int(getattr(box, "cls", None))
            label = _label_for_class(names, class_id)
            bbox = _to_bbox(getattr(box, "xyxy", None))
            if bbox is None:
                continue

            detections.append(
                {
                    "label": label,
                    "confidence": confidence,
                    "bbox": bbox,
                }
            )
    return detections


def _resolve_model_path(model_path):
    path = Path(model_path)
    return path if path.is_absolute() else PROJECT_ROOT / path


def _to_float(value):
    if value is None:
        return None
    array = _to_numpy(value).reshape(-1)
    if array.size == 0:
        return None
    return float(array[0])


def _to_int(value):
    scalar = _to_float(value)
    return int(scalar) if scalar is not None else None


def _to_bbox(value):
    if value is None:
        return None
    array = _to_numpy(value).reshape(-1)
    if array.size < 4:
        return None
    return [float(coord) for coord in array[:4]]


def _to_numpy(value):
    if hasattr(value, "detach"):
        value = value.detach()
    if hasattr(value, "cpu"):
        value = value.cpu()
    if hasattr(value, "numpy"):
        value = value.numpy()
    return np.asarray(value)


def _label_for_class(names, class_id):
    if class_id is None:
        return "unknown"
    if isinstance(names, dict):
        return str(names.get(class_id, class_id))
    if isinstance(names, (list, tuple)) and 0 <= class_id < len(names):
        return str(names[class_id])
    return str(class_id)


_singleton = YOLOPatternService()


def get_yolo_service():
    return _singleton


def initialize_yolo_service(model_path=None, model_url=None, auto_download=None):
    service = get_yolo_service()
    if model_path:
        service.model_path = _resolve_model_path(model_path)
    if model_url:
        service.model_url = model_url
    if auto_download is not None:
        service.auto_download = bool(auto_download)
    return service.load_model()


def detect_patterns(image, confidence_threshold=None):
    return get_yolo_service().detect(image, confidence_threshold)
