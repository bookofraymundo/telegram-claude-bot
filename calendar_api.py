"""
Google Calendar API integration for Santacruz Brothers LLC bot.
Arizona timezone (MST = UTC-7, no DST).
Default reminders: 1 day (1440 min) + 1 hour (60 min) before.
"""
import os
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

TIMEZONE = 'America/Phoenix'


def _get_service():
    creds = Credentials(
        token=None,
        refresh_token=os.environ['GOOGLE_REFRESH_TOKEN'],
        client_id=os.environ['GOOGLE_CLIENT_ID'],
        client_secret=os.environ['GOOGLE_CLIENT_SECRET'],
        token_uri='https://oauth2.googleapis.com/token',
    )
    return build('calendar', 'v3', credentials=creds)


def _fmt(dt: datetime) -> str:
    """Format datetime for Google Calendar API (RFC3339 with MST offset)."""
    return dt.strftime('%Y-%m-%dT%H:%M:%S') + '-07:00'


def add_event(
    title: str,
    start: datetime,
    end: datetime,
    location: str = '',
    description: str = '',
) -> dict:
    """Add an event to the primary calendar. Returns the created event."""
    service = _get_service()
    event = {
        'summary': title,
        'start': {'dateTime': _fmt(start), 'timeZone': TIMEZONE},
        'end':   {'dateTime': _fmt(end),   'timeZone': TIMEZONE},
        'reminders': {
            'useDefault': False,
            'overrides': [
                {'method': 'popup', 'minutes': 1440},  # 1 day
                {'method': 'popup', 'minutes': 60},    # 1 hour
            ],
        },
    }
    if location:
        event['location'] = location
    if description:
        event['description'] = description

    return service.events().insert(calendarId='primary', body=event).execute()


def delete_event(event_id: str) -> None:
    """Delete an event by its Google Calendar event ID."""
    service = _get_service()
    service.events().delete(calendarId='primary', eventId=event_id).execute()


def update_event(
    event_id: str,
    title: str,
    new_start: datetime,
    new_end: datetime,
    location: str = '',
    description: str = '',
) -> dict:
    """Update an existing event by its Google Calendar event ID."""
    service = _get_service()
    event = service.events().get(calendarId='primary', eventId=event_id).execute()
    event['summary'] = title
    event['start'] = {'dateTime': _fmt(new_start), 'timeZone': TIMEZONE}
    event['end']   = {'dateTime': _fmt(new_end),   'timeZone': TIMEZONE}
    if location:
        event['location'] = location
    if description:
        event['description'] = description
    return service.events().update(calendarId='primary', eventId=event_id, body=event).execute()


def find_event(title: str, date: str) -> str | None:
    """
    Search for an event by title and date (YYYY-MM-DD).
    Returns the event ID if found, None otherwise.
    """
    service = _get_service()
    day_start = f"{date}T00:00:00-07:00"
    day_end   = f"{date}T23:59:59-07:00"
    result = service.events().list(
        calendarId='primary',
        timeMin=day_start,
        timeMax=day_end,
        q=title,
        singleEvents=True,
    ).execute()
    events = result.get('items', [])
    if events:
        return events[0]['id']
    return None
