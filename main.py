import os
import caldav
from caldav import DAVClient
from dotenv import load_dotenv
import json

from datetime import date
from datetime import datetime
from datetime import timedelta


def search_calendar_demo(calendars):
    events_fetched = []
    for calendar in calendars:
        events = calendar.date_search(
            start=datetime.now() - timedelta(days=7),
            end=datetime.now() + timedelta(days=7)
        )
        events_fetched.extend(events)

    print(events_fetched)
    return events_fetched


def print_calendars_demo(calendars):
    """
    This example prints the name and URL for every calendar on the list
    """
    if calendars:
        ## Some calendar servers will include all calendars you have
        ## access to in this list, and not only the calendars owned by
        ## this principal.
        print("your principal has %i calendars:" % len(calendars))
        for c in calendars:
            print("    Name: %-36s  URL: %s" % (c.name, c.url))
    else:
        print("your principal has no calendars")


def fill_event(component, calendar) -> dict[str, str]:
    cur = {}
    cur["calendar"] = f"{calendar}"
    cur["summary"] = component.get("summary")
    cur["description"] = component.get("description")
    cur["start"] = component.get("dtstart").dt.strftime("%m/%d/%Y %H:%M")
    endDate = component.get("dtend")
    if endDate and endDate.dt:
        cur["end"] = endDate.dt.strftime("%m/%d/%Y %H:%M")
    cur["datestamp"] = component.get("dtstamp").dt.strftime("%m/%d/%Y %H:%M")
    return cur

def print_events(calendars):
    if not calendars:
        return
    events = []
    for calendar in calendars:
        for event in calendar.events():
            for component in event.icalendar_instance.walk():
                if component.name != "VEVENT":
                    continue
                events.append(fill_event(component, calendar))
    print(json.dumps(events, indent=2, ensure_ascii=False))

def main():
    # Load environment variables from a .env file
    load_dotenv()

    caldav_url = os.environ.get('CALDAV_URL')
    username = os.environ.get('CALDAV_USERNAME')
    password = os.environ.get('CALDAV_PASSWORD')

    with DAVClient(
            url=caldav_url,
            username=username,
            password=password,
        ) as client:

        principal = client.principal()
        print(f"Principal: {principal}")

        calendars = principal.calendars()

        print_calendars_demo(calendars)
        search_calendar_demo(calendars)

if __name__ == "__main__":
    main()