import numpy as np
import pytest

from backend.services.patternDetection.signalResolver import resolve_pattern_signal
from backend.services.patternDetection import yoloService
from backend.services.patternDetection.yoloService import YOLOPatternService


class FakeBox:
    def __init__(self, cls, conf, xyxy):
        self.cls = np.array([cls])
        self.conf = np.array([conf])
        self.xyxy = np.array([xyxy])


class FakePrediction:
    names = {0: "head_and_shoulders", 1: "triangle"}

    def __init__(self):
        self.boxes = [
            FakeBox(0, 0.91, [1, 2, 30, 40]),
            FakeBox(1, 0.31, [4, 5, 20, 25]),
        ]


class FakeModel:
    names = {0: "head_and_shoulders", 1: "triangle"}

    def __init__(self, model_path):
        self.model_path = model_path
        self.predict_calls = []

    def predict(self, source, verbose=False):
        self.predict_calls.append((source, verbose))
        return [FakePrediction()]


class FakeDownloadResponse:
    def __init__(self, chunks):
        self.chunks = chunks

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size):
        return iter(self.chunks)


def test_yolo_service_loads_once_and_filters_sample_image(tmp_path):
    model_path = tmp_path / "model.pt"
    model_path.write_bytes(b"fake weights")
    load_calls = []

    def fake_loader(path):
        load_calls.append(path)
        return FakeModel(path)

    service = YOLOPatternService(
        model_path=model_path,
        confidence_threshold=0.50,
        model_loader=fake_loader,
    )

    assert service.load_model() is service.load_model()
    assert len(load_calls) == 1

    sample_image = np.zeros((64, 64, 3), dtype=np.uint8)
    detections = service.detect(sample_image)

    assert detections == [
        {
            "label": "head_and_shoulders",
            "confidence": pytest.approx(0.91),
            "bbox": [1.0, 2.0, 30.0, 40.0],
        }
    ]


def test_yolo_service_downloads_missing_model_before_loading(tmp_path, monkeypatch):
    model_path = tmp_path / "models" / "yolov8" / "model.pt"
    load_calls = []

    monkeypatch.setattr(yoloService, "MIN_MODEL_BYTES", 4)
    monkeypatch.setattr(
        yoloService.requests,
        "get",
        lambda *args, **kwargs: FakeDownloadResponse([b"fake", b" weights"]),
    )

    def fake_loader(path):
        load_calls.append(path)
        return FakeModel(path)

    service = YOLOPatternService(
        model_path=model_path,
        model_url="https://example.test/model.pt",
        auto_download=True,
        model_loader=fake_loader,
    )

    assert service.load_model() is not None
    assert model_path.exists()
    assert model_path.read_bytes() == b"fake weights"
    assert load_calls == [str(model_path)]
    assert service.last_error is None


def test_yolo_service_rejects_non_numpy_input(tmp_path):
    model_path = tmp_path / "model.pt"
    model_path.write_bytes(b"fake weights")
    service = YOLOPatternService(model_path=model_path, model_loader=FakeModel)
    service.load_model()

    with pytest.raises(ValueError):
        service.detect("not an image")


def test_signal_resolver_prioritizes_yolo_with_talib_confirmation():
    resolved = resolve_pattern_signal(
        [{"label": "Head and Shoulders", "confidence": 0.86, "bbox": [1, 2, 3, 4]}],
        [{"pattern": "head_and_shoulders"}],
        confidence_threshold=0.50,
    )

    assert resolved == {
        "signal_priority": 1,
        "pattern": "Head and Shoulders",
        "confidence": 0.86,
        "source_badge": "YOLOv8 + TA-Lib",
        "bounding_boxes": [[1, 2, 3, 4]],
        "talib_confirmation": True,
        "talib_conflict": False,
    }


def test_signal_resolver_handles_absent_conflicting_and_low_confidence_talib():
    absent = resolve_pattern_signal(
        [{"label": "triangle", "confidence": 0.77, "bbox": [0, 0, 10, 10]}],
        [],
        confidence_threshold=0.50,
    )
    assert absent["signal_priority"] == 2
    assert absent["source_badge"] == "YOLOv8"
    assert absent["talib_conflict"] is False

    conflicting = resolve_pattern_signal(
        [{"label": "triangle", "confidence": 0.77, "bbox": [0, 0, 10, 10]}],
        ["double_top"],
        confidence_threshold=0.50,
    )
    assert conflicting["signal_priority"] == 2
    assert conflicting["source_badge"] == "YOLOv8"
    assert conflicting["talib_conflict"] is True

    suppressed = resolve_pattern_signal(
        [{"label": "triangle", "confidence": 0.49, "bbox": [0, 0, 10, 10]}],
        ["triangle"],
        confidence_threshold=0.50,
    )
    assert suppressed == {
        "signal_priority": None,
        "pattern": None,
        "confidence": None,
        "source_badge": None,
        "bounding_boxes": [],
        "talib_confirmation": False,
        "talib_conflict": False,
    }
