def run_scan_job(job_id, user_id, market, filters, timeframe, limit):
    from backend.jobs.scan_jobs import run_scan_job as _run_scan_job

    return _run_scan_job(job_id, user_id, market, filters, timeframe, limit)


def evaluate_scan_templates_job():
    from backend.jobs.template_jobs import evaluate_scan_templates_job as _evaluate_scan_templates_job

    return _evaluate_scan_templates_job()
