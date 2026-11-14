"""Data-quality and logic checks on the marts. Run: pytest -q"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from build_marts import DB, build, connect  # noqa: E402


@pytest.fixture(scope="module")
def con():
    if not DB.exists():
        build()
    c = connect(read_only=True)
    yield c
    c.close()


def one(con, sql):
    return con.execute(sql).fetchone()[0]


def test_one_row_per_user(con):
    assert one(con, "SELECT count(*) - count(DISTINCT user_id) FROM mart_user_activation") == 0


def test_event_ids_unique(con):
    assert one(con, "SELECT count(*) - count(DISTINCT event_id) FROM stg_events") == 0


def test_no_events_before_install(con):
    assert one(con, "SELECT count(*) FROM stg_events WHERE day_n < 0") == 0


def test_funnel_is_monotonic(con):
    """No user can complete a later onboarding step without the earlier one."""
    bad = one(con, """
        SELECT count(*) FROM mart_user_activation
        WHERE (did_kyc_start = 1 AND did_signup = 0) OR (did_kyc_done = 1 AND did_kyc_start = 0)
           OR (did_upi = 1 AND did_kyc_done = 0) OR (did_first_buy = 1 AND did_upi = 0)""")
    assert bad == 0


def test_step_order_in_time(con):
    bad = one(con, """
        SELECT count(*) FROM int_user_funnel
        WHERE signup_ts < install_ts OR kyc_done_ts < kyc_start_ts OR first_buy_ts < upi_ts""")
    assert bad == 0


def test_week1_features_only_for_buyers(con):
    """Week-1 savings behaviours require a completed first purchase."""
    assert one(con, "SELECT count(*) FROM mart_user_activation WHERE did_first_buy = 0 AND w1_autosave = 1") == 0


def test_retention_flags_binary(con):
    assert one(con, "SELECT count(*) FROM mart_user_activation WHERE d30_retained NOT IN (0, 1)") == 0
