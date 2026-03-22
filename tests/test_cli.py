"""Tests for calctl CLI layer."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from calctl.cli import app, run
from calctl.errors import AlarmParseError, CalctlError

runner = CliRunner()

FAKE_CALENDARS = [{"name": "Personal", "id": "cal-1"}, {"name": "Work", "id": "cal-2"}]
FAKE_EVENT = {
    "id": "evt-123",
    "title": "Test Event",
    "start": "2026-03-19T10:00:00",
    "end": "2026-03-19T11:00:00",
    "calendar": "Personal",
    "all_day": False,
}
FAKE_ACTION = {"_action": "created", **FAKE_EVENT}


# ---------------------------------------------------------------------------
# 1. Help
# ---------------------------------------------------------------------------


def test_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "macOS Calendar CLI" in result.output


# ---------------------------------------------------------------------------
# 2. calendars --format json
# ---------------------------------------------------------------------------


def test_calendars_json():
    with patch("calctl.cli.list_calendars", return_value=FAKE_CALENDARS) as mock:
        result = runner.invoke(app, ["--format", "json", "calendars"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data == FAKE_CALENDARS
    mock.assert_called_once()


# ---------------------------------------------------------------------------
# 3. calendars --format text
# ---------------------------------------------------------------------------


def test_calendars_text():
    with patch("calctl.cli.list_calendars", return_value=FAKE_CALENDARS):
        result = runner.invoke(app, ["--format", "text", "calendars"])
    assert result.exit_code == 0
    assert "Personal" in result.output
    assert "Work" in result.output


# ---------------------------------------------------------------------------
# 4. list default dates
# ---------------------------------------------------------------------------


def test_list_default_dates():
    today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    next_week = (datetime.now(tz=timezone.utc) + timedelta(days=7)).strftime("%Y-%m-%d")
    with patch("calctl.cli.list_events", return_value=[]) as mock:
        result = runner.invoke(app, ["--format", "text", "list"])
    assert result.exit_code == 0
    mock.assert_called_once_with(
        today, next_week, calendars=None, exclude_calendars=None,
    )


# ---------------------------------------------------------------------------
# 5. list --calendar Work
# ---------------------------------------------------------------------------


def test_list_with_calendar():
    with patch("calctl.cli.list_events", return_value=[]) as mock:
        result = runner.invoke(app, ["--format", "text", "list", "--calendar", "Work"])
    assert result.exit_code == 0
    kw = mock.call_args[1]
    assert kw["calendars"] == ["Work"]


# ---------------------------------------------------------------------------
# 6. --format json before subcommand
# ---------------------------------------------------------------------------


def test_list_format_json():
    with patch("calctl.cli.list_events", return_value=[FAKE_EVENT]):
        result = runner.invoke(app, ["--format", "json", "list"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, list)
    assert data[0]["id"] == "evt-123"


# ---------------------------------------------------------------------------
# 7. search
# ---------------------------------------------------------------------------


def test_search():
    with patch("calctl.cli.search_events", return_value=[FAKE_EVENT]) as mock:
        result = runner.invoke(app, ["--format", "json", "search", "meeting"])
    assert result.exit_code == 0
    mock.assert_called_once_with(
        "meeting", None, None, calendars=None, exclude_calendars=None,
    )


# ---------------------------------------------------------------------------
# 8. search --calendar Work
# ---------------------------------------------------------------------------


def test_search_with_calendar():
    with patch("calctl.cli.search_events", return_value=[]) as mock:
        result = runner.invoke(
            app,
            ["--format", "text", "search", "meeting", "--calendar", "Work"],
        )
    assert result.exit_code == 0
    kw = mock.call_args[1]
    assert kw["calendars"] == ["Work"]


# ---------------------------------------------------------------------------
# 8b. list --calendar repeatable
# ---------------------------------------------------------------------------


def test_list_multi_calendar():
    with patch("calctl.cli.list_events", return_value=[]) as mock:
        result = runner.invoke(
            app,
            ["--format", "text", "list", "--calendar", "Work", "--calendar", "Family"],
        )
    assert result.exit_code == 0
    kw = mock.call_args[1]
    assert kw["calendars"] == ["Work", "Family"]


# ---------------------------------------------------------------------------
# 8c. list --exclude-calendar
# ---------------------------------------------------------------------------


def test_list_exclude_calendar():
    with patch("calctl.cli.list_events", return_value=[]) as mock:
        result = runner.invoke(
            app,
            [
                "--format", "text", "list",
                "--exclude-calendar", "Birthdays",
                "--exclude-calendar", "US Holidays",
            ],
        )
    assert result.exit_code == 0
    kw = mock.call_args[1]
    assert kw["exclude_calendars"] == ["Birthdays", "US Holidays"]


# ---------------------------------------------------------------------------
# 8d. search --calendar repeatable
# ---------------------------------------------------------------------------


def test_search_multi_calendar():
    with patch("calctl.cli.search_events", return_value=[]) as mock:
        result = runner.invoke(
            app,
            [
                "--format", "text", "search", "meeting",
                "--calendar", "Work", "--calendar", "Personal",
            ],
        )
    assert result.exit_code == 0
    kw = mock.call_args[1]
    assert kw["calendars"] == ["Work", "Personal"]


# ---------------------------------------------------------------------------
# 9. show
# ---------------------------------------------------------------------------


def test_show():
    with patch("calctl.cli.get_event", return_value=FAKE_EVENT) as mock:
        result = runner.invoke(app, ["--format", "json", "show", "evt-123"])
    assert result.exit_code == 0
    mock.assert_called_once_with("evt-123", date=None)


# ---------------------------------------------------------------------------
# 10. create minimal
# ---------------------------------------------------------------------------


def test_create_minimal():
    with patch("calctl.cli.create_event", return_value=FAKE_ACTION) as mock:
        result = runner.invoke(
            app,
            ["--format", "json", "create", "--title", "Test", "--start", "2026-03-19"],
        )
    assert result.exit_code == 0
    call_kwargs = mock.call_args[1]
    assert call_kwargs["title"] == "Test"
    assert call_kwargs["start"] == "2026-03-19"


# ---------------------------------------------------------------------------
# 11. create all flags
# ---------------------------------------------------------------------------


def test_create_all_flags():
    with patch("calctl.cli.create_event", return_value=FAKE_ACTION) as mock:
        result = runner.invoke(
            app,
            [
                "--format",
                "json",
                "create",
                "--title",
                "Meeting",
                "--start",
                "2026-03-19T10:00:00",
                "--end",
                "2026-03-19T11:00:00",
                "--calendar",
                "Work",
                "--location",
                "Office",
                "--geo",
                "37.7749,-122.4194",
                "--notes",
                "Bring laptop",
                "--url",
                "https://example.com",
                "--all-day",
                "--availability",
                "busy",
                "--timezone",
                "America/New_York",
                "--rrule",
                "FREQ=WEEKLY",
                "--alarm",
                "-15m",
            ],
        )
    assert result.exit_code == 0
    kw = mock.call_args[1]
    assert kw["title"] == "Meeting"
    assert kw["calendar"] == "Work"
    assert kw["location"] == "Office"
    assert kw["geo"] == "37.7749,-122.4194"
    assert kw["notes"] == "Bring laptop"
    assert kw["url"] == "https://example.com"
    assert kw["all_day"] is True
    assert kw["availability"] == "busy"
    assert kw["timezone"] == "America/New_York"
    assert kw["rrule"] == "FREQ=WEEKLY"
    assert kw["alarms"] == ["-15m"]


# ---------------------------------------------------------------------------
# 12. edit
# ---------------------------------------------------------------------------


def test_edit():
    ret = {**FAKE_EVENT, "_action": "updated"}
    with patch("calctl.cli.edit_event", return_value=ret) as mock:
        result = runner.invoke(
            app, ["--format", "json", "edit", "evt-123", "--title", "New"]
        )
    assert result.exit_code == 0
    kw = mock.call_args[1]
    assert kw["event_id"] == "evt-123"
    assert kw["title"] == "New"


# ---------------------------------------------------------------------------
# 13. edit --span future
# ---------------------------------------------------------------------------


def test_edit_span():
    ret = {**FAKE_EVENT, "_action": "updated"}
    with patch("calctl.cli.edit_event", return_value=ret) as mock:
        result = runner.invoke(
            app,
            [
                "--format",
                "json",
                "edit",
                "evt-123",
                "--title",
                "New",
                "--span",
                "future",
            ],
        )
    assert result.exit_code == 0
    kw = mock.call_args[1]
    assert kw["span"] == "future"


# ---------------------------------------------------------------------------
# 14. edit --all-day tristate
# ---------------------------------------------------------------------------


def test_edit_all_day_tristate():
    ret = {**FAKE_EVENT, "_action": "updated"}
    with patch("calctl.cli.edit_event", return_value=ret) as mock:
        runner.invoke(app, ["--format", "json", "edit", "evt-123", "--all-day"])
    kw = mock.call_args[1]
    assert kw["all_day"] is True

    with patch("calctl.cli.edit_event", return_value=ret) as mock:
        runner.invoke(app, ["--format", "json", "edit", "evt-123", "--no-all-day"])
    kw = mock.call_args[1]
    assert kw["all_day"] is False


# ---------------------------------------------------------------------------
# 15. delete
# ---------------------------------------------------------------------------


def test_delete():
    ret = {"_action": "deleted", **FAKE_EVENT}
    with patch("calctl.cli.delete_event", return_value=ret) as mock:
        result = runner.invoke(app, ["--format", "text", "delete", "evt-123"])
    assert result.exit_code == 0
    mock.assert_called_once_with(
        "evt-123", span=None, dry_run=False, date=None,
    )


# ---------------------------------------------------------------------------
# 16. delete --span future
# ---------------------------------------------------------------------------


def test_delete_span():
    ret = {"_action": "deleted", **FAKE_EVENT}
    with patch("calctl.cli.delete_event", return_value=ret) as mock:
        result = runner.invoke(
            app, ["--format", "text", "delete", "evt-123", "--span", "future"]
        )
    assert result.exit_code == 0
    mock.assert_called_once_with(
        "evt-123", span="future", dry_run=False, date=None,
    )


# ---------------------------------------------------------------------------
# 15b. show --date
# ---------------------------------------------------------------------------


def test_show_with_date():
    with patch("calctl.cli.get_event", return_value=FAKE_EVENT) as mock:
        result = runner.invoke(
            app, ["--format", "json", "show", "evt-123", "--date", "2026-03-25"]
        )
    assert result.exit_code == 0
    mock.assert_called_once_with("evt-123", date="2026-03-25")


# ---------------------------------------------------------------------------
# 16b. delete --date
# ---------------------------------------------------------------------------


def test_delete_with_date():
    ret = {"_action": "deleted", "span": "this", **FAKE_EVENT}
    with patch("calctl.cli.delete_event", return_value=ret) as mock:
        result = runner.invoke(
            app, ["--format", "json", "delete", "evt-123", "--date", "2026-03-25"]
        )
    assert result.exit_code == 0
    mock.assert_called_once_with(
        "evt-123", span=None, dry_run=False, date="2026-03-25",
    )


# ---------------------------------------------------------------------------
# 16c. delete --dry-run
# ---------------------------------------------------------------------------


def test_delete_dry_run():
    ret = {"_action": "dry_run", "span": "this", **FAKE_EVENT}
    with patch("calctl.cli.delete_event", return_value=ret) as mock:
        result = runner.invoke(
            app, ["--format", "json", "delete", "evt-123", "--dry-run"]
        )
    assert result.exit_code == 0
    mock.assert_called_once_with(
        "evt-123", span=None, dry_run=True, date=None,
    )
    data = json.loads(result.output)
    assert data["span"] == "this"


# ---------------------------------------------------------------------------
# 16d. edit --dry-run
# ---------------------------------------------------------------------------


def test_edit_dry_run():
    ret = {"_action": "dry_run", "span": "this", **FAKE_EVENT}
    with patch("calctl.cli.edit_event", return_value=ret) as mock:
        result = runner.invoke(
            app, ["--format", "json", "edit", "evt-123", "--title", "X", "--dry-run"]
        )
    assert result.exit_code == 0
    kw = mock.call_args[1]
    assert kw["dry_run"] is True


# ---------------------------------------------------------------------------
# 16e. edit --date
# ---------------------------------------------------------------------------


def test_edit_with_date():
    ret = {"_action": "updated", "span": "this", **FAKE_EVENT}
    with patch("calctl.cli.edit_event", return_value=ret) as mock:
        result = runner.invoke(
            app,
            [
                "--format", "json", "edit", "evt-123",
                "--title", "New", "--date", "2026-03-25",
            ],
        )
    assert result.exit_code == 0
    kw = mock.call_args[1]
    assert kw["date"] == "2026-03-25"
    assert kw["span"] is None


# ---------------------------------------------------------------------------
# 17. alarm repeatable
# ---------------------------------------------------------------------------


def test_alarm_repeatable():
    with patch("calctl.cli.create_event", return_value=FAKE_ACTION) as mock:
        result = runner.invoke(
            app,
            [
                "--format",
                "json",
                "create",
                "--title",
                "X",
                "--start",
                "2026-03-19",
                "--alarm",
                "-15m",
                "--alarm",
                "-1h",
            ],
        )
    assert result.exit_code == 0
    kw = mock.call_args[1]
    assert kw["alarms"] == ["-15m", "-1h"]


# ---------------------------------------------------------------------------
# 18. alarm empty rejects combination
# ---------------------------------------------------------------------------


def test_alarm_empty_rejects_combination():
    with patch("calctl.cli.create_event", side_effect=AlarmParseError("bad")):
        result = runner.invoke(
            app,
            [
                "--format",
                "json",
                "create",
                "--title",
                "X",
                "--start",
                "2026-03-19",
                "--alarm",
                "",
                "--alarm",
                "-15m",
            ],
        )
    # AlarmParseError propagates through CliRunner → non-zero exit
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# 19. error CalctlError -> exit 1
# ---------------------------------------------------------------------------


def test_error_calctl(capsys, monkeypatch):
    monkeypatch.setattr(
        "calctl.cli.list_calendars",
        MagicMock(side_effect=CalctlError("no access")),
    )
    monkeypatch.setattr(sys, "argv", ["calctl", "--format", "text", "calendars"])
    with pytest.raises(SystemExit) as exc_info:
        run()
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "no access" in captured.err


# ---------------------------------------------------------------------------
# 20. error unexpected -> exit 2
# ---------------------------------------------------------------------------


def test_error_unexpected(capsys, monkeypatch):
    monkeypatch.setattr(
        "calctl.cli.list_calendars",
        MagicMock(side_effect=RuntimeError("boom")),
    )
    monkeypatch.setattr(sys, "argv", ["calctl", "--format", "text", "calendars"])
    with pytest.raises(SystemExit) as exc_info:
        run()
    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "boom" in captured.err
