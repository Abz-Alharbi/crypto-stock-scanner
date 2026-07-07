from backend.factory import create_app


def rebuild_universe_job():
    app = create_app()
    with app.app_context():
        from backend.services.universe import universe_builder

        universe_builder.clear_universe_refresh_marker()
        try:
            return universe_builder.build_and_save_universe()
        finally:
            universe_builder.schedule_next_universe_rebuild()
