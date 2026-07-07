"""canonical active timeframes

Revision ID: e4f2a9b7c6d1
Revises: d3a6f1c2b8e9
Create Date: 2026-07-08 00:30:00.000000

"""
from alembic import op


revision = "e4f2a9b7c6d1"
down_revision = "d3a6f1c2b8e9"
branch_labels = None
depends_on = None


NEW_TIMEFRAME_SQL = "timeframe IN ('1m', '5m', '15m', '30m', '45m', '1H', '4H', '1D', '1W', '1M', '1Y')"
OLD_TIMEFRAME_SQL = "timeframe IN ('1min', '5min', '15min', '30min', '45min', '1H', '1D', '1W', '1M', '1Y')"


def _rewrite_timeframes(mapping):
    for table in ("scan_history", "scan_results"):
        for old_value, new_value in mapping.items():
            op.execute(
                f"UPDATE {table} SET timeframe = '{new_value}' WHERE timeframe = '{old_value}'"
            )


def _replace_constraint(table_name, constraint_name, sqltext):
    with op.batch_alter_table(table_name, schema=None) as batch_op:
        batch_op.drop_constraint(constraint_name, type_="check")
        batch_op.create_check_constraint(constraint_name, sqltext)


def upgrade():
    _rewrite_timeframes(
        {
            "1min": "1m",
            "5min": "5m",
            "15min": "15m",
            "30min": "30m",
            "45min": "45m",
        }
    )
    _replace_constraint("scan_history", "ck_scan_history_timeframe", NEW_TIMEFRAME_SQL)
    _replace_constraint("scan_results", "ck_scan_results_timeframe", NEW_TIMEFRAME_SQL)


def downgrade():
    op.execute("UPDATE scan_history SET timeframe = '1H' WHERE timeframe = '4H'")
    op.execute("UPDATE scan_results SET timeframe = '1H' WHERE timeframe = '4H'")
    _rewrite_timeframes(
        {
            "1m": "1min",
            "5m": "5min",
            "15m": "15min",
            "30m": "30min",
            "45m": "45min",
        }
    )
    _replace_constraint("scan_history", "ck_scan_history_timeframe", OLD_TIMEFRAME_SQL)
    _replace_constraint("scan_results", "ck_scan_results_timeframe", OLD_TIMEFRAME_SQL)
