from datetime import date

import services.limits_service as limits_mod
from tests.setup.fakes import FakeFirestore


def _wire(monkeypatch, fake_db):
    monkeypatch.setattr(limits_mod, "get_firestore_client", lambda: fake_db)


def _freeze(monkeypatch, year: int, month: int, day: int) -> None:
    monkeypatch.setattr(limits_mod, "_today_utc", lambda: date(year, month, day))


class TestIsExempt:
    def test_admin_and_super_admin_are_exempt(self):
        assert limits_mod.is_exempt("ADMIN") is True
        assert limits_mod.is_exempt("SUPER_ADMIN") is True

    def test_user_and_missing_role_are_not_exempt(self):
        assert limits_mod.is_exempt("USER") is False
        assert limits_mod.is_exempt(None) is False


class TestGetLimits:
    def test_returns_defaults_when_no_override_exists(self, monkeypatch):
        fake_db = FakeFirestore()
        _wire(monkeypatch, fake_db)

        assert limits_mod.get_limits("u1") == limits_mod.DEFAULT_LIMITS

    def test_merges_a_partial_override_over_the_defaults(self, monkeypatch):
        fake_db = FakeFirestore(seed={"usage_limits": {"u1": {"daily_token_limit": 5000}}})
        _wire(monkeypatch, fake_db)

        limits = limits_mod.get_limits("u1")

        assert limits["daily_token_limit"] == 5000
        assert limits["daily_search_limit"] == limits_mod.DEFAULT_LIMITS["daily_search_limit"]


class TestSetLimits:
    def test_stores_all_four_fields_and_returns_them(self, monkeypatch):
        fake_db = FakeFirestore()
        _wire(monkeypatch, fake_db)

        result = limits_mod.set_limits(
            "u1",
            daily_token_limit=1,
            daily_search_limit=2,
            monthly_token_limit=3,
            monthly_search_limit=4,
        )

        assert result == {
            "daily_token_limit": 1,
            "daily_search_limit": 2,
            "monthly_token_limit": 3,
            "monthly_search_limit": 4,
        }
        stored = fake_db.collection("usage_limits").document("u1").get().to_dict()
        assert stored == result


class TestResetDates:
    def test_next_daily_reset_is_tomorrow(self, monkeypatch):
        _freeze(monkeypatch, 2026, 9, 11)
        assert limits_mod.next_daily_reset() == "2026-09-12"

    def test_next_monthly_reset_is_the_first_of_next_month(self, monkeypatch):
        _freeze(monkeypatch, 2026, 9, 11)
        assert limits_mod.next_monthly_reset() == "2026-10-01"

    def test_next_monthly_reset_rolls_over_the_year(self, monkeypatch):
        _freeze(monkeypatch, 2026, 12, 20)
        assert limits_mod.next_monthly_reset() == "2027-01-01"


class TestRecordTokenUsage:
    def test_accumulates_within_the_same_day_and_month(self, monkeypatch):
        fake_db = FakeFirestore()
        _wire(monkeypatch, fake_db)
        _freeze(monkeypatch, 2026, 9, 11)

        limits_mod.record_token_usage("u1", {"total_tokens": 100})
        limits_mod.record_token_usage("u1", {"total_tokens": 50})

        stored = fake_db.collection("usage_periods").document("u1").get().to_dict()
        assert stored["daily_tokens"] == 150
        assert stored["monthly_tokens"] == 150

    def test_daily_counter_resets_on_a_new_day_but_monthly_carries_over(self, monkeypatch):
        fake_db = FakeFirestore(
            seed={
                "usage_periods": {
                    "u1": {
                        "daily_period": "2026-09-10",
                        "daily_tokens": 500,
                        "daily_searches": 0,
                        "monthly_period": "2026-09",
                        "monthly_tokens": 500,
                        "monthly_searches": 0,
                    }
                }
            }
        )
        _wire(monkeypatch, fake_db)
        _freeze(monkeypatch, 2026, 9, 11)

        limits_mod.record_token_usage("u1", {"total_tokens": 10})

        stored = fake_db.collection("usage_periods").document("u1").get().to_dict()
        assert stored["daily_tokens"] == 10
        assert stored["monthly_tokens"] == 510

    def test_monthly_counter_resets_on_a_new_month(self, monkeypatch):
        fake_db = FakeFirestore(
            seed={
                "usage_periods": {
                    "u1": {
                        "daily_period": "2026-08-31",
                        "daily_tokens": 500,
                        "daily_searches": 0,
                        "monthly_period": "2026-08",
                        "monthly_tokens": 5000,
                        "monthly_searches": 0,
                    }
                }
            }
        )
        _wire(monkeypatch, fake_db)
        _freeze(monkeypatch, 2026, 9, 1)

        limits_mod.record_token_usage("u1", {"total_tokens": 10})

        stored = fake_db.collection("usage_periods").document("u1").get().to_dict()
        assert stored["daily_tokens"] == 10
        assert stored["monthly_tokens"] == 10

    def test_is_a_no_op_for_admin_and_super_admin(self, monkeypatch):
        fake_db = FakeFirestore()
        _wire(monkeypatch, fake_db)
        _freeze(monkeypatch, 2026, 9, 11)

        limits_mod.record_token_usage("admin-1", {"total_tokens": 100}, "ADMIN")
        limits_mod.record_token_usage("super-1", {"total_tokens": 100}, "SUPER_ADMIN")

        assert fake_db.collection("usage_periods").document("admin-1").get().to_dict() is None
        assert fake_db.collection("usage_periods").document("super-1").get().to_dict() is None


class TestRecordSearchUsage:
    def test_adds_one_search_credit_to_both_counters(self, monkeypatch):
        fake_db = FakeFirestore()
        _wire(monkeypatch, fake_db)
        _freeze(monkeypatch, 2026, 9, 11)

        limits_mod.record_search_usage("u1")
        limits_mod.record_search_usage("u1")

        stored = fake_db.collection("usage_periods").document("u1").get().to_dict()
        assert stored["daily_searches"] == 2
        assert stored["monthly_searches"] == 2
        assert stored["daily_tokens"] == 0

    def test_is_a_no_op_for_admin_and_super_admin(self, monkeypatch):
        fake_db = FakeFirestore()
        _wire(monkeypatch, fake_db)
        _freeze(monkeypatch, 2026, 9, 11)

        limits_mod.record_search_usage("admin-1", "ADMIN")
        limits_mod.record_search_usage("super-1", "SUPER_ADMIN")

        assert fake_db.collection("usage_periods").document("admin-1").get().to_dict() is None
        assert fake_db.collection("usage_periods").document("super-1").get().to_dict() is None


class TestTokenLimitMessage:
    def test_returns_none_when_within_both_limits(self, monkeypatch):
        fake_db = FakeFirestore()
        _wire(monkeypatch, fake_db)
        _freeze(monkeypatch, 2026, 9, 11)

        assert limits_mod.token_limit_message("u1") is None

    def test_names_the_daily_limit_and_its_exact_reset_date(self, monkeypatch):
        fake_db = FakeFirestore(
            seed={
                "usage_limits": {"u1": {"daily_token_limit": 100}},
                "usage_periods": {
                    "u1": {
                        "daily_period": "2026-09-11",
                        "daily_tokens": 100,
                        "monthly_period": "2026-09",
                        "monthly_tokens": 100,
                    }
                },
            }
        )
        _wire(monkeypatch, fake_db)
        _freeze(monkeypatch, 2026, 9, 11)

        message = limits_mod.token_limit_message("u1")

        assert "daily token limit of 100 tokens" in message
        assert "2026-09-12" in message

    def test_names_the_monthly_limit_when_only_it_is_exceeded(self, monkeypatch):
        fake_db = FakeFirestore(
            seed={
                "usage_limits": {"u1": {"monthly_token_limit": 1000}},
                "usage_periods": {
                    "u1": {
                        "daily_period": "2026-09-11",
                        "daily_tokens": 10,
                        "monthly_period": "2026-09",
                        "monthly_tokens": 1000,
                    }
                },
            }
        )
        _wire(monkeypatch, fake_db)
        _freeze(monkeypatch, 2026, 9, 11)

        message = limits_mod.token_limit_message("u1")

        assert "monthly token limit of 1,000 tokens" in message
        assert "2026-10-01" in message

    def test_admin_is_exempt_even_at_100x_the_default_limit(self, monkeypatch):
        fake_db = FakeFirestore(
            seed={
                "usage_periods": {
                    "admin-1": {
                        "daily_period": "2026-09-11",
                        "daily_tokens": 10_000_000,
                        "monthly_period": "2026-09",
                        "monthly_tokens": 10_000_000,
                    }
                }
            }
        )
        _wire(monkeypatch, fake_db)
        _freeze(monkeypatch, 2026, 9, 11)

        assert limits_mod.token_limit_message("admin-1", "ADMIN") is None

    def test_super_admin_is_exempt_even_at_100x_the_default_limit(self, monkeypatch):
        fake_db = FakeFirestore(
            seed={
                "usage_periods": {
                    "super-1": {
                        "daily_period": "2026-09-11",
                        "daily_tokens": 10_000_000,
                        "monthly_period": "2026-09",
                        "monthly_tokens": 10_000_000,
                    }
                }
            }
        )
        _wire(monkeypatch, fake_db)
        _freeze(monkeypatch, 2026, 9, 11)

        assert limits_mod.token_limit_message("super-1", "SUPER_ADMIN") is None


class TestSearchLimitMessage:
    def test_returns_none_when_within_both_limits(self, monkeypatch):
        fake_db = FakeFirestore()
        _wire(monkeypatch, fake_db)
        _freeze(monkeypatch, 2026, 9, 11)

        assert limits_mod.search_limit_message("u1") is None

    def test_names_the_exact_reset_date_when_daily_limit_reached(self, monkeypatch):
        fake_db = FakeFirestore(
            seed={
                "usage_limits": {"u1": {"daily_search_limit": 3}},
                "usage_periods": {
                    "u1": {
                        "daily_period": "2026-09-11",
                        "daily_searches": 3,
                        "monthly_period": "2026-09",
                        "monthly_searches": 3,
                    }
                },
            }
        )
        _wire(monkeypatch, fake_db)
        _freeze(monkeypatch, 2026, 9, 11)

        message = limits_mod.search_limit_message("u1")

        assert "web search limit has been reached" in message
        assert "2026-09-12" in message

    def test_admin_and_super_admin_are_exempt_regardless_of_usage(self, monkeypatch):
        fake_db = FakeFirestore(
            seed={
                "usage_periods": {
                    "admin-1": {
                        "daily_period": "2026-09-11",
                        "daily_searches": 9999,
                        "monthly_period": "2026-09",
                        "monthly_searches": 9999,
                    }
                }
            }
        )
        _wire(monkeypatch, fake_db)
        _freeze(monkeypatch, 2026, 9, 11)

        assert limits_mod.search_limit_message("admin-1", "ADMIN") is None
        assert limits_mod.search_limit_message("admin-1", "SUPER_ADMIN") is None


class TestGetLimitsAndUsage:
    def test_combines_limits_usage_and_reset_dates(self, monkeypatch):
        fake_db = FakeFirestore(
            seed={
                "usage_periods": {
                    "u1": {
                        "daily_period": "2026-09-11",
                        "daily_tokens": 20,
                        "daily_searches": 1,
                        "monthly_period": "2026-09",
                        "monthly_tokens": 20,
                        "monthly_searches": 1,
                    }
                }
            }
        )
        _wire(monkeypatch, fake_db)
        _freeze(monkeypatch, 2026, 9, 11)

        result = limits_mod.get_limits_and_usage("u1")

        assert result["limits"] == limits_mod.DEFAULT_LIMITS
        assert result["usage"] == {
            "daily_tokens": 20,
            "daily_searches": 1,
            "monthly_tokens": 20,
            "monthly_searches": 1,
        }
        assert result["daily_reset_at"] == "2026-09-12"
        assert result["monthly_reset_at"] == "2026-10-01"
