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
    AUTO_CREATE_SCHEMA = os.getenv("AUTO_CREATE_SCHEMA", "false").lower() == "true"


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
