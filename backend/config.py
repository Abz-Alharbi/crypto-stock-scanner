import os
import secrets

from dotenv import load_dotenv


load_dotenv()


class BaseConfig:
    SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_hex(32))
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///market_scanner.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173")
    DEBUG = False
    TESTING = False
    AUTH_DISABLED = os.getenv("AUTH_DISABLED", "false").lower() == "true"
    AUTO_CREATE_SCHEMA = os.getenv("AUTO_CREATE_SCHEMA", "false").lower() == "true"
    ENABLE_SCAN_TEMPLATE_SCHEDULER = os.getenv("ENABLE_SCAN_TEMPLATE_SCHEDULER", "false").lower() == "true"
    SCAN_TEMPLATE_EVALUATION_INTERVAL_SECONDS = int(os.getenv("SCAN_TEMPLATE_EVALUATION_INTERVAL_SECONDS", "900"))
    SCAN_TEMPLATE_INITIAL_DELAY_SECONDS = int(os.getenv("SCAN_TEMPLATE_INITIAL_DELAY_SECONDS", "60"))
    SMTP_HOST = os.getenv("SMTP_HOST", "")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM = os.getenv("SMTP_FROM", "")
    SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
    YOLO_MODEL_PATH = os.getenv("YOLO_MODEL_PATH", "models/yolov8/model.pt")
    YOLO_MODEL_URL = os.getenv(
        "YOLO_MODEL_URL",
        "https://huggingface.co/foduucom/stockmarket-pattern-detection-yolov8/resolve/main/model.pt",
    )
    YOLO_AUTO_DOWNLOAD = os.getenv(
        "YOLO_AUTO_DOWNLOAD",
        "false" if os.getenv("FLASK_ENV", "").lower() in {"test", "testing"} else "true",
    ).lower() == "true"
    YOLO_CONFIDENCE_THRESHOLD = float(os.getenv("YOLO_CONFIDENCE_THRESHOLD", "0.50"))
    PATTERN_LOG_ROOT = os.getenv("PATTERN_LOG_ROOT", "logs/pattern_detections")
    UNIVERSE_NASDAQ_SIZE = int(os.getenv("UNIVERSE_NASDAQ_SIZE", "500"))
    UNIVERSE_NYSE_SIZE = int(os.getenv("UNIVERSE_NYSE_SIZE", "300"))
    UNIVERSE_LOOKBACK_DAYS = int(os.getenv("UNIVERSE_LOOKBACK_DAYS", "730"))
    UNIVERSE_REFRESH_CRON = os.getenv("UNIVERSE_REFRESH_CRON", "weekly")
    ENABLE_UNIVERSE_REFRESH_SCHEDULER = os.getenv("ENABLE_UNIVERSE_REFRESH_SCHEDULER", "false").lower() == "true"


class DevelopmentConfig(BaseConfig):
    DEBUG = True


class ProductionConfig(BaseConfig):
    DEBUG = False


class TestConfig(BaseConfig):
    TESTING = True
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.getenv("TEST_DATABASE_URL", "sqlite:///:memory:")


CONFIG_BY_ENV = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "test": TestConfig,
    "testing": TestConfig,
}


def get_config(config=None):
    if config is not None and not isinstance(config, str):
        return config
    env_name = (config or os.getenv("FLASK_ENV") or "production").lower()
    return CONFIG_BY_ENV.get(env_name, ProductionConfig)
