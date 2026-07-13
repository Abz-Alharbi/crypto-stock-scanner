def run_scan_job(job_id, user_id, market, filters, timeframe, limit, universe=None):
    from backend.jobs.scan_jobs import run_scan_job as _run_scan_job

    return _run_scan_job(
        job_id,
        user_id,
        market,
        filters,
        timeframe,
        limit,
        universe=universe,
    )


def evaluate_scan_templates_job():
    from backend.jobs.template_jobs import evaluate_scan_templates_job as _evaluate_scan_templates_job

    return _evaluate_scan_templates_job()


def rebuild_universe_job():
    from backend.jobs.universe_jobs import rebuild_universe_job as _rebuild_universe_job

    return _rebuild_universe_job()
