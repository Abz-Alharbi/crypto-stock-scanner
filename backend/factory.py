import os

import click
from flask import Flask
from flask_cors import CORS

from backend.auth.service import create_admin
from backend.config import get_config
from backend.errors import register_error_handlers
from backend.extensions import db, migrate
from backend.logging_config import configure_logging
from backend.models.user import User
from backend.symbols import canonicalize_symbol


def _parse_allowed_origins(value):
    origins = [origin.strip() for origin in str(value).split(",") if origin.strip()]
    return origins or ["http://localhost:5173"]


def _register_blueprints(app):
    from backend.api.admin_routes import admin_bp
    from backend.api.fundamentals_routes import fundamentals_bp
    from backend.api.news_routes import news_bp
    from backend.api.notification_routes import notifications_bp
    from backend.api.ops_routes import ops_bp
    from backend.api.pattern_routes import pattern_bp
    from backend.api.scan_routes import scan_bp
    from backend.api.watchlist_routes import watchlist_bp
    from backend.auth.routes import auth_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(scan_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(watchlist_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(news_bp)
    app.register_blueprint(fundamentals_bp)
    app.register_blueprint(pattern_bp)
    app.register_blueprint(ops_bp)


def _register_cli(app):
    @app.cli.command("create-admin")
    @click.option("--email", required=True, help="Admin email address.")
    @click.option("--password", required=True, help="Admin password.")
    def create_admin_command(email, password):
        """Create the first admin account."""
        email = email.strip().lower()
        if User.query.filter_by(role="admin").first():
            raise click.ClickException("An admin account already exists.")
        if User.query.filter_by(email=email).first():
            raise click.ClickException("A user with that email already exists.")
        user, _created = create_admin(email, password)
        click.echo(f"Created admin account: {user.email}")

    @app.cli.command("seed-db")
    def seed_db_command():
        """Insert safe local development data."""
        from backend.models.scan import ScanHistory, ScanResult
        from backend.models.watchlist import Watchlist

        user = User.query.filter_by(email="dev@marketscanner.local").first()
        if not user:
            user = User(
                username="dev_user",
                email="dev@marketscanner.local",
                role="user",
                plan="free",
            )
            user.set_password("dev-password-change-me")
            db.session.add(user)
            db.session.flush()

        for symbol, market, notes in (
            ("AAPL", "stocks", "Sample equity watch item"),
            ("MSFT", "stocks", "Sample equity watch item"),
            ("X:BTCUSD", "crypto", "Sample crypto watch item"),
        ):
            canonical = canonicalize_symbol(symbol, market)
            exists = Watchlist.query.filter_by(user_id=user.id, symbol=canonical.provider_symbol).first()
            if not exists:
                db.session.add(
                    Watchlist(
                        user_id=user.id,
                        symbol=canonical.provider_symbol,
                        provider_symbol=canonical.provider_symbol,
                        display_symbol=canonical.display_symbol,
                        market=canonical.market,
                        notes=notes,
                    )
                )

        if not ScanHistory.query.first():
            db.session.add(
                ScanHistory(
                    user_id=user.id,
                    job_id="seed-scan",
                    market="stocks",
                    timeframe="1D",
                    total_scanned=3,
                    total_matched=1,
                    filters_used='["rsi_oversold"]',
                    duration_seconds=0.12,
                )
            )

        if not ScanResult.query.first():
            db.session.add(
                ScanResult(
                    user_id=user.id,
                    job_id="seed-scan",
                    symbol="AAPL",
                    provider_symbol="AAPL",
                    display_symbol="AAPL",
                    market="stocks",
                    timeframe="1D",
                    scan_type="filter_scan",
                    filters_matched='["rsi_oversold"]',
                    indicator_values='{"rsi": 28.4}',
                    last_price=195.12,
                    volume=1000000,
                    signal="bullish",
                )
            )

        db.session.commit()
        click.echo("Seeded local development data.")

    @app.cli.command("debug-polygon")
    @click.option("--symbol", default="AAPL", show_default=True, help="Ticker to fetch.")
    @click.option("--days", default=10, show_default=True, help="Calendar days to include.")
    def debug_polygon_command(symbol, days):
        """Fetch raw Polygon aggregate data with the API key redacted."""
        import json
        from datetime import datetime, timedelta

        from backend.clients.polygon import polygon

        to_date = datetime.utcnow().date()
        from_date = to_date - timedelta(days=int(days))
        payload = polygon.debug_aggregates_raw(symbol.upper(), str(from_date), str(to_date))
        click.echo(json.dumps(payload, indent=2))

    @app.cli.command("debug-opencv")
    def debug_opencv_command():
        """Report whether OpenCV/cv2 imports in this runtime."""
        import json

        try:
            import cv2
        except Exception as exc:
            click.echo(
                json.dumps(
                    {
                        "ok": False,
                        "exception_type": type(exc).__name__,
                        "exception_message": str(exc),
                    },
                    indent=2,
                )
            )
            raise click.ClickException("OpenCV import failed") from exc

        click.echo(
            json.dumps(
                {
                    "ok": True,
                    "version": getattr(cv2, "__version__", None),
                    "file": getattr(cv2, "__file__", None),
                },
                indent=2,
            )
        )

    @app.cli.command("debug-yolo")
    @click.option("--load/--no-load", default=True, show_default=True, help="Attempt to download/load the model.")
    def debug_yolo_command(load):
        """Report YOLOv8 model path, download, and load status."""
        import json

        from backend.services.patternDetection.yoloService import get_yolo_service

        service = get_yolo_service()
        if load:
            service.load_model()

        click.echo(
            json.dumps(
                {
                    "loaded": service.is_loaded,
                    "model_path": str(service.model_path),
                    "model_exists": service.model_path.exists(),
                    "model_url": service.model_url,
                    "auto_download": service.auto_download,
                    "last_error": service.last_error,
                },
                indent=2,
            )
        )

    @app.cli.command("debug-scan")
    @click.option("--market", default="stocks", show_default=True, help="Market to scan.")
    @click.option("--timeframe", default="1D", show_default=True, help="Timeframe to scan.")
    @click.option("--filters", required=True, help="Comma-separated filter keys, e.g. bullish_pattern.")
    @click.option("--limit", default=30, show_default=True, help="Maximum result count.")
    def debug_scan_command(market, timeframe, filters, limit):
        """Run a scan synchronously and print scan counters."""
        import json

        from backend.services import scans

        filter_keys = [item.strip() for item in filters.split(",") if item.strip()]
        payload = scans.scan_market(market, filter_keys, timeframe, int(limit), job_id="debug-scan")
        click.echo(
            json.dumps(
                {
                    "meta": payload.get("meta"),
                    "result_count": len(payload.get("results") or []),
                    "results": (payload.get("results") or [])[:5],
                },
                indent=2,
            )
        )

    @app.cli.command("rebuild-universe")
    def rebuild_universe_command():
        """Rebuild equity and crypto scan universes from Polygon volume data."""
        import json

        from backend.services.universe import universe_builder

        payload = universe_builder.build_and_save_all_universes()
        click.echo(json.dumps(payload, indent=2))


def create_app(config=None):
    configure_logging()
    app = Flask(__name__)
    app.json.sort_keys = False
    if isinstance(config, dict):
        app.config.from_object(get_config(None))
        app.config.update(config)
    else:
        app.config.from_object(get_config(config))

    if os.getenv("FLASK_ENV") != "development":
        app.config["DEBUG"] = False

    CORS(
        app,
        resources={
            r"/api/*": {
                "origins": _parse_allowed_origins(app.config.get("ALLOWED_ORIGINS")),
            }
        },
    )

    @app.after_request
    def add_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Strict-Transport-Security"] = "max-age=63072000"
        return response

    db.init_app(app)
    migrate.init_app(app, db)
    register_error_handlers(app)

    from backend import models  # noqa: F401

    _register_blueprints(app)
    _register_cli(app)

    with app.app_context():
        from backend.services.patternDetection.yoloService import initialize_yolo_service

        initialize_yolo_service(
            app.config.get("YOLO_MODEL_PATH"),
            app.config.get("YOLO_MODEL_URL"),
            app.config.get("YOLO_AUTO_DOWNLOAD"),
        )

    if app.config.get("ENABLE_SCAN_TEMPLATE_SCHEDULER"):
        with app.app_context():
            from backend.services.scan_templates import ensure_template_sweep_scheduled

            ensure_template_sweep_scheduled()

    if app.config.get("ENABLE_UNIVERSE_REFRESH_SCHEDULER"):
        with app.app_context():
            from backend.services.universe.universe_builder import ensure_universe_rebuild_scheduled

            ensure_universe_rebuild_scheduled()

    if app.config.get("AUTO_CREATE_SCHEMA"):
        with app.app_context():
            db.create_all()

    return app
