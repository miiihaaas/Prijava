from datetime import datetime

from flask import current_app
from sqlalchemy import or_

from prijava.models import Application


def parse_datetime_local(raw):
    """Parse the value produced by an HTML ``datetime-local`` (or plain date) input.

    Returns a ``datetime`` on success, ``None`` on parse failure.
    """
    if not raw:
        return None
    if isinstance(raw, datetime):
        return raw
    try:
        if 'T' in raw:
            return datetime.strptime(raw, '%Y-%m-%dT%H:%M')
        return datetime.strptime(raw, '%Y-%m-%d')
    except ValueError as exc:
        current_app.logger.error(f"Greška pri parsiranju datuma '{raw}': {exc}")
        return None


def apply_application_filters(
    query,
    *,
    search=None,
    date_from=None,
    date_to=None,
    grade=None,
    end_of_day_if_date_only=True,
):
    """Apply the standard Application filter set to a query.

    ``date_from`` / ``date_to`` accept raw strings (from request args) or
    ``datetime`` objects. When ``end_of_day_if_date_only`` is truthy and a
    date-only string is passed for ``date_to``, it is bumped to 23:59:59 so
    the filter is inclusive.
    """
    if search:
        like = f"%{search}%"
        query = query.filter(or_(
            Application.children_name.ilike(like),
            Application.children_surname.ilike(like),
            Application.mother_name.ilike(like),
            Application.mother_surname.ilike(like),
            Application.father_name.ilike(like),
            Application.father_surname.ilike(like),
        ))

    if date_from:
        parsed_from = date_from if isinstance(date_from, datetime) else parse_datetime_local(date_from)
        if parsed_from is not None:
            query = query.filter(Application.date_submitted >= parsed_from)

    if date_to:
        parsed_to = date_to if isinstance(date_to, datetime) else parse_datetime_local(date_to)
        if parsed_to is not None:
            if (
                end_of_day_if_date_only
                and not isinstance(date_to, datetime)
                and isinstance(date_to, str)
                and 'T' not in date_to
            ):
                parsed_to = datetime(parsed_to.year, parsed_to.month, parsed_to.day, 23, 59, 59)
            query = query.filter(Application.date_submitted <= parsed_to)

    if grade:
        query = query.filter(Application.grade == grade)

    return query
