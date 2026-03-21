"""Tests for backup.common — parse_interval and _format_interval."""
import pytest

from backup.common import parse_interval, _format_interval


class TestParseInterval:
    def test_minutes(self):
        assert parse_interval("30m") == 1800

    def test_hours(self):
        assert parse_interval("6h") == 21600

    def test_days(self):
        assert parse_interval("7d") == 604800

    def test_single_minute(self):
        assert parse_interval("1m") == 60

    def test_leading_whitespace(self):
        assert parse_interval("  12h  ") == 43200

    def test_uppercase_unit(self):
        assert parse_interval("24H") == 86400

    def test_invalid_no_unit(self):
        with pytest.raises(ValueError, match="Invalid interval"):
            parse_interval("60")

    def test_invalid_bad_unit(self):
        with pytest.raises(ValueError, match="Invalid interval"):
            parse_interval("5w")

    def test_invalid_empty_string(self):
        with pytest.raises(ValueError, match="Invalid interval"):
            parse_interval("")

    def test_invalid_text_only(self):
        with pytest.raises(ValueError, match="Invalid interval"):
            parse_interval("daily")


class TestFormatInterval:
    def test_exact_days(self):
        assert _format_interval(86400) == "1d"

    def test_multiple_days(self):
        assert _format_interval(7 * 86400) == "7d"

    def test_exact_hours(self):
        assert _format_interval(3600) == "1h"

    def test_multiple_hours(self):
        assert _format_interval(6 * 3600) == "6h"

    def test_minutes(self):
        assert _format_interval(1800) == "30m"

    def test_non_round_hours_falls_back_to_minutes(self):
        # 90 minutes = 5400s — not a round number of hours
        assert _format_interval(5400) == "90m"

    def test_non_round_days_falls_back_to_hours(self):
        # 36 hours = 129600s — not a round number of days but is a round number of hours
        assert _format_interval(36 * 3600) == "36h"
