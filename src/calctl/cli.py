"""calctl — macOS Calendar CLI."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta

from calctl.calendar import (
    create_event,
    delete_event,
    edit_event,
    get_event,
    list_calendars,
    list_events,
    search_events,
)


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _next_week() -> str:
    return (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")


def main() -> None:
    parser = argparse.ArgumentParser(prog="calctl", description="macOS Calendar CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    # calendars
    sub.add_parser("calendars", help="List all calendars")

    # list
    p_list = sub.add_parser("list", help="List events in a date range")
    p_list.add_argument(
        "--from", dest="from_date", default=_today(),
        help="Start date YYYY-MM-DD (default: today)",
    )
    p_list.add_argument(
        "--to", dest="to_date", default=_next_week(),
        help="End date YYYY-MM-DD (default: +7 days)",
    )
    p_list.add_argument("--calendar", help="Filter by calendar name")

    # search
    p_search = sub.add_parser("search", help="Search events by keyword")
    p_search.add_argument("query", help="Search query")
    p_search.add_argument("--from", dest="from_date", help="Start date")
    p_search.add_argument("--to", dest="to_date", help="End date")

    # show
    p_show = sub.add_parser("show", help="Show event details")
    p_show.add_argument("id", help="Event ID")

    # create
    p_create = sub.add_parser("create", help="Create an event")
    p_create.add_argument("--title", required=True)
    p_create.add_argument(
        "--start", required=True,
        help="YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS",
    )
    p_create.add_argument(
        "--end",
        help="End datetime (default: +1h, or same day if --all-day)",
    )
    p_create.add_argument("--calendar", help="Calendar name")
    p_create.add_argument("--location", help="Event location")
    p_create.add_argument("--notes", help="Event notes")
    p_create.add_argument("--all-day", action="store_true")

    # edit
    p_edit = sub.add_parser("edit", help="Edit an existing event")
    p_edit.add_argument("id", help="Event ID")
    p_edit.add_argument("--title")
    p_edit.add_argument("--start", help="YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS")
    p_edit.add_argument("--end", help="YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS")
    p_edit.add_argument("--location")
    p_edit.add_argument("--notes")
    p_edit.add_argument("--all-day", action="store_true", default=None)

    # delete
    p_delete = sub.add_parser("delete", help="Delete an event")
    p_delete.add_argument("id", help="Event ID")

    args = parser.parse_args()

    if args.command == "calendars":
        result = list_calendars()
    elif args.command == "list":
        result = list_events(args.from_date, args.to_date, args.calendar)
    elif args.command == "search":
        result = search_events(args.query, args.from_date, args.to_date)
    elif args.command == "show":
        result = get_event(args.id)
    elif args.command == "create":
        result = create_event(
            title=args.title,
            start=args.start,
            end=args.end,
            calendar=args.calendar,
            location=args.location,
            notes=args.notes,
            all_day=args.all_day,
        )
    elif args.command == "edit":
        result = edit_event(
            event_id=args.id,
            title=args.title,
            start=args.start,
            end=args.end,
            location=args.location,
            notes=args.notes,
            all_day=args.all_day,
        )
    elif args.command == "delete":
        result = delete_event(args.id)
    else:
        parser.print_help()
        sys.exit(1)

    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
