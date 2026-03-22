"""calctl — macOS Calendar CLI."""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timedelta, timezone
from typing import Annotated

import typer

from calctl.calendar import (
    create_event,
    delete_event,
    edit_event,
    get_event,
    list_calendars,
    list_events,
    search_events,
)
from calctl.errors import AlarmParseError, CalctlError
from calctl.formatting import Format, format_output

logger = logging.getLogger(__name__)

app = typer.Typer(
    help="macOS Calendar CLI using EventKit",
    no_args_is_help=True,
)

# Module-level state for global options
_format: Format = Format.text


def _detect_format() -> Format:
    """Auto-detect format: JSON for pipes, text for TTY."""
    if sys.stdout.isatty():
        return Format.text
    return Format.json


def _output(data: object) -> None:
    """Format and print data to stdout."""
    print(format_output(data, _format))  # noqa: T201


def _today() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")


def _next_week() -> str:
    return (datetime.now(tz=timezone.utc) + timedelta(days=7)).strftime("%Y-%m-%d")


def _validate_alarms(alarm: list[str] | None) -> None:
    """Validate alarm list: empty string cannot be combined with other alarms."""
    if alarm and "" in alarm and len(alarm) > 1:
        msg = 'Cannot combine --alarm "" with other --alarm values'
        raise AlarmParseError(msg)


@app.callback()
def callback(
    fmt: Annotated[
        Format | None,
        typer.Option("--format", "-f", help="Output format (json or text)"),
    ] = None,
    verbose: Annotated[  # noqa: FBT002
        bool,
        typer.Option("--verbose", "-v", help="Enable debug logging"),
    ] = False,
) -> None:
    """macOS Calendar CLI using EventKit."""
    global _format  # noqa: PLW0603
    _format = fmt if fmt is not None else _detect_format()

    if verbose:
        logging.basicConfig(
            level=logging.DEBUG,
            stream=sys.stderr,
            format="%(name)s %(levelname)s: %(message)s",
        )


@app.command()
def calendars() -> None:
    """List all calendars."""
    result = list_calendars()
    _output(result)


@app.command(name="list")
def list_cmd(
    from_date: Annotated[
        str,
        typer.Option("--from", help="Start date YYYY-MM-DD (default: today)"),
    ] = "",
    to_date: Annotated[
        str,
        typer.Option("--to", help="End date YYYY-MM-DD (default: +7 days)"),
    ] = "",
    calendar: Annotated[
        list[str] | None,
        typer.Option(
            "--calendar",
            help="Filter by calendar name (repeatable)",
        ),
    ] = None,
    exclude_calendar: Annotated[
        list[str] | None,
        typer.Option(
            "--exclude-calendar",
            help="Exclude calendar (repeatable)",
        ),
    ] = None,
) -> None:
    """List events in a date range."""
    from_date = from_date or _today()
    to_date = to_date or _next_week()
    result = list_events(
        from_date,
        to_date,
        calendars=calendar,
        exclude_calendars=exclude_calendar,
    )
    _output(result)


@app.command()
def search(
    query: Annotated[str, typer.Argument(help="Search query")],
    from_date: Annotated[
        str | None,
        typer.Option("--from", help="Start date YYYY-MM-DD"),
    ] = None,
    to_date: Annotated[
        str | None,
        typer.Option("--to", help="End date YYYY-MM-DD"),
    ] = None,
    calendar: Annotated[
        list[str] | None,
        typer.Option(
            "--calendar",
            help="Filter by calendar name (repeatable)",
        ),
    ] = None,
    exclude_calendar: Annotated[
        list[str] | None,
        typer.Option(
            "--exclude-calendar",
            help="Exclude calendar (repeatable)",
        ),
    ] = None,
) -> None:
    """Search events by keyword."""
    result = search_events(
        query,
        from_date,
        to_date,
        calendars=calendar,
        exclude_calendars=exclude_calendar,
    )
    _output(result)


@app.command()
def show(
    event_id: Annotated[str, typer.Argument(help="Event ID")],
    date: Annotated[
        str | None,
        typer.Option(
            "--date",
            help="Show occurrence on this date (YYYY-MM-DDTHH:MM:SS)",
        ),
    ] = None,
) -> None:
    """Show event details."""
    result = get_event(event_id, date=date)
    _output(result)


@app.command()
def create(  # noqa: PLR0913
    title: Annotated[str, typer.Option("--title", help="Event title")],
    start: Annotated[
        str,
        typer.Option(
            "--start",
            help="Start datetime (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)",
        ),
    ],
    end: Annotated[
        str | None,
        typer.Option(
            "--end",
            help="End datetime (default: +1h, or same day if --all-day)",
        ),
    ] = None,
    calendar: Annotated[
        str | None,
        typer.Option("--calendar", help="Calendar name"),
    ] = None,
    location: Annotated[
        str | None,
        typer.Option("--location", help="Event location"),
    ] = None,
    geo: Annotated[
        str | None,
        typer.Option("--geo", help="Geo coordinates (lat,lng)"),
    ] = None,
    notes: Annotated[
        str | None,
        typer.Option("--notes", help="Event notes"),
    ] = None,
    url: Annotated[
        str | None,
        typer.Option("--url", help="Event URL"),
    ] = None,
    all_day: Annotated[  # noqa: FBT002
        bool,
        typer.Option("--all-day/--no-all-day", help="All-day event"),
    ] = False,
    availability: Annotated[
        str | None,
        typer.Option(
            "--availability",
            help="Availability (busy/free/tentative/unavailable)",
        ),
    ] = None,
    timezone_: Annotated[
        str | None,
        typer.Option("--timezone", help="Timezone (e.g. America/New_York)"),
    ] = None,
    rrule: Annotated[
        str | None,
        typer.Option("--rrule", help="Recurrence rule (RRULE string)"),
    ] = None,
    alarm: Annotated[
        list[str] | None,
        typer.Option("--alarm", help="Alarm offset (e.g. -15m, -1h). Repeatable."),
    ] = None,
) -> None:
    """Create a new event."""
    _validate_alarms(alarm)
    result = create_event(
        title=title,
        start=start,
        end=end,
        calendar=calendar,
        location=location,
        geo=geo,
        notes=notes,
        url=url,
        all_day=all_day,
        availability=availability,
        timezone=timezone_,
        rrule=rrule,
        alarms=alarm,
    )
    _output(result)


@app.command()
def edit(  # noqa: PLR0913
    event_id: Annotated[str, typer.Argument(help="Event ID")],
    title: Annotated[
        str | None,
        typer.Option("--title", help="New title"),
    ] = None,
    start: Annotated[
        str | None,
        typer.Option("--start", help="New start datetime"),
    ] = None,
    end: Annotated[
        str | None,
        typer.Option("--end", help="New end datetime"),
    ] = None,
    calendar: Annotated[
        str | None,
        typer.Option("--calendar", help="Move to calendar"),
    ] = None,
    location: Annotated[
        str | None,
        typer.Option("--location", help="New location"),
    ] = None,
    geo: Annotated[
        str | None,
        typer.Option("--geo", help="New geo coordinates (lat,lng)"),
    ] = None,
    notes: Annotated[
        str | None,
        typer.Option("--notes", help="New notes"),
    ] = None,
    url: Annotated[
        str | None,
        typer.Option("--url", help="New URL"),
    ] = None,
    all_day: Annotated[
        bool | None,
        typer.Option("--all-day/--no-all-day", help="Set all-day flag"),
    ] = None,
    availability: Annotated[
        str | None,
        typer.Option("--availability", help="New availability"),
    ] = None,
    timezone_: Annotated[
        str | None,
        typer.Option("--timezone", help="New timezone"),
    ] = None,
    rrule: Annotated[
        str | None,
        typer.Option("--rrule", help="New recurrence rule"),
    ] = None,
    alarm: Annotated[
        list[str] | None,
        typer.Option("--alarm", help="Alarm offset. Repeatable."),
    ] = None,
    span: Annotated[
        str | None,
        typer.Option("--span", help="Edit span: this or future"),
    ] = None,
    dry_run: Annotated[  # noqa: FBT002
        bool,
        typer.Option(
            "--dry-run",
            help="Show what would be changed without saving",
        ),
    ] = False,
    date: Annotated[
        str | None,
        typer.Option(
            "--date",
            help="Target occurrence on this date (YYYY-MM-DDTHH:MM:SS)",
        ),
    ] = None,
) -> None:
    """Edit an existing event."""
    _validate_alarms(alarm)
    result = edit_event(
        event_id=event_id,
        title=title,
        start=start,
        end=end,
        calendar=calendar,
        location=location,
        geo=geo,
        notes=notes,
        url=url,
        all_day=all_day,
        availability=availability,
        timezone=timezone_,
        rrule=rrule,
        alarms=alarm,
        span=span,
        dry_run=dry_run,
        date=date,
    )
    _output(result)


@app.command()
def delete(
    event_id: Annotated[str, typer.Argument(help="Event ID")],
    span: Annotated[
        str | None,
        typer.Option("--span", help="Delete span: this or future"),
    ] = None,
    dry_run: Annotated[  # noqa: FBT002
        bool,
        typer.Option(
            "--dry-run",
            help="Show what would be deleted without removing",
        ),
    ] = False,
    date: Annotated[
        str | None,
        typer.Option(
            "--date",
            help="Target occurrence on this date (YYYY-MM-DDTHH:MM:SS)",
        ),
    ] = None,
) -> None:
    """Delete an event."""
    result = delete_event(
        event_id, span=span, dry_run=dry_run, date=date,
    )
    _output(result)


def run() -> None:
    """Entry point with error handling."""
    try:
        app()
    except CalctlError as exc:
        logger.debug("CalctlError", exc_info=True)
        print(f"Error: {exc}", file=sys.stderr)  # noqa: T201
        sys.exit(1)
    except Exception as exc:
        if logging.getLogger().isEnabledFor(logging.DEBUG):
            logger.exception("Unexpected error")
        else:
            print(f"Unexpected error: {exc}", file=sys.stderr)  # noqa: T201
        sys.exit(2)


main = run
