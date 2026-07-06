from backend.factory import create_app


def evaluate_scan_templates_job():
    app = create_app()
    with app.app_context():
        from backend.services import scan_templates

        scan_templates.clear_template_sweep_marker()
        try:
            return scan_templates.evaluate_all_templates()
        finally:
            scan_templates.schedule_next_template_sweep()
