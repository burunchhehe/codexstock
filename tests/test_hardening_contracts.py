from app.local_api_security import validate_local_api_write
from app.native_core import NativeBacktester, NativeMarket
from app.startup_policy import resolve_startup_policy


def test_clean_install_is_safe_and_heavy_workers_are_idle():
    policy = resolve_startup_policy({}, saved_research_enabled=False)
    assert policy.clean_install_safe is True
    assert policy.heavy_research_workers is False


def test_cross_site_and_form_writes_are_blocked():
    cross_site = validate_local_api_write(
        "/api/logic/save",
        {"Content-Type": "application/json", "Host": "127.0.0.1:8765", "Origin": "https://evil.example", "Sec-Fetch-Site": "cross-site"},
        body_length=2,
    )
    form = validate_local_api_write(
        "/api/logic/save",
        {"Content-Type": "application/x-www-form-urlencoded", "Host": "127.0.0.1:8765"},
        body_length=2,
    )
    assert cross_site is not None and cross_site.status == 403
    assert form is not None and form.status == 415


def test_native_results_cannot_be_mistaken_for_real_data():
    for payload in (NativeMarket().quote("AAPL"), NativeBacktester().run_ma_cross("AAPL", 180, 12, 32)):
        assert payload["data_mode"] == "synthetic"
        assert payload["real_order_allowed"] is False
        assert payload["data_warning"]
