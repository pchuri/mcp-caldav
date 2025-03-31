import os
from dotenv import load_dotenv
import json
import requests
import xml.etree.ElementTree as ET

from datetime import date
from datetime import datetime
from datetime import timedelta
import re


def get_event_urls(calendar_url, calendar_name, days_back=30):
    """
    Fetch event URLs from the specified number of days back for a specific calendar using REPORT.
    
    Args:
        calendar_url (str): The URL of the calendar
        calendar_name (str): The name of the calendar for display purposes
        days_back (int): Number of days to look back for events (default: 30)
        
    Returns:
        list: A list of event URLs
    """
    # Load environment variables
    load_dotenv()
    caldav_url = os.environ.get('CALDAV_URL')
    username = os.environ.get('CALDAV_USERNAME')
    password = os.environ.get('CALDAV_PASSWORD')
    
    # Calculate date range (today and days_back days ago)
    today = datetime.now()
    past_date = today - timedelta(days=days_back)
    
    # Format dates in iCalendar format (YYYYMMDDTHHMMSSZ)
    start_date = past_date.strftime("%Y%m%dT000000Z")
    end_date = today.strftime("%Y%m%dT235959Z")
    
    # Create calendar-query request with time-range filter
    # Only request href and etag, not the full calendar-data
    xml_request = f"""
    <c:calendar-query xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">
      <d:prop>
        <d:getetag />
        <d:href />
      </d:prop>
      <c:filter>
        <c:comp-filter name="VCALENDAR">
          <c:comp-filter name="VEVENT">
            <c:time-range start="{start_date}" end="{end_date}" />
          </c:comp-filter>
        </c:comp-filter>
      </c:filter>
    </c:calendar-query>
    """
    
    headers = {
        "Content-Type": "application/xml; charset=utf-8",
        "Depth": "1"
    }
    
    # If calendar_url is a relative URL, make it absolute
    full_calendar_url = f"{caldav_url}{calendar_url}" if calendar_url.startswith('/') else calendar_url
    
    # Send REPORT request
    response = requests.request("REPORT", full_calendar_url, data=xml_request, headers=headers, auth=(username, password))
    
    if response.status_code != 207:
        print(f"Failed to fetch event URLs for calendar '{calendar_name}'. Status code: {response.status_code}")
        return []
    
    # Parse the XML response
    root = ET.fromstring(response.text)
    responses = root.findall('.//d:response', {'d': 'DAV:'})
    
    event_urls = []
    
    for resp in responses:
        href = resp.find('./d:href', {'d': 'DAV:'})
        if href is not None and href.text:
            event_urls.append(href.text)
    
    return event_urls


def get_event_details(event_urls, calendar_name, batch_size=5):
    """
    Fetch detailed event information using calendar-multiget for a list of event URLs.
    Process events in batches to avoid memory issues.
    
    Args:
        event_urls (list): List of event URLs to fetch
        calendar_name (str): The name of the calendar for display purposes
        batch_size (int): Number of events to process in each batch
        
    Returns:
        list: A list of dictionaries containing event information
    """
    if not event_urls:
        return []
    
    # Load environment variables
    load_dotenv()
    caldav_url = os.environ.get('CALDAV_URL')
    username = os.environ.get('CALDAV_USERNAME')
    password = os.environ.get('CALDAV_PASSWORD')
    
    headers = {
        "Content-Type": "application/xml; charset=utf-8",
        "Depth": "1"
    }
    
    # Extract the base calendar URL from the first event URL
    # This assumes all events are from the same calendar
    base_url_parts = event_urls[0].split('/')
    base_url = '/'.join(base_url_parts[:-1]) + '/'
    full_calendar_url = f"{caldav_url}{base_url}" if base_url.startswith('/') else base_url
    
    all_events = []
    total_batches = (len(event_urls) + batch_size - 1) // batch_size  # Ceiling division
    
    # Process events in batches
    for batch_num, i in enumerate(range(0, len(event_urls), batch_size), 1):
        batch_urls = event_urls[i:i+batch_size]
        print(f"  Processing batch {batch_num}/{total_batches} ({len(batch_urls)} events)...")
        
        # Create calendar-multiget request for this batch
        xml_request = """
        <c:calendar-multiget xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">
          <d:prop>
            <d:getetag />
            <c:calendar-data />
          </d:prop>
        """
        
        # Add each event URL to the request
        for url in batch_urls:
            xml_request += f"<d:href>{url}</d:href>\n"
        
        xml_request += "</c:calendar-multiget>"
        
        try:
            # Send REPORT request with calendar-multiget
            response = requests.request("REPORT", full_calendar_url, data=xml_request, headers=headers, auth=(username, password))
            
            if response.status_code != 207:
                print(f"  Failed to fetch batch {batch_num}. Status code: {response.status_code}")
                continue
            
            # Parse the XML response
            root = ET.fromstring(response.text)
            responses = root.findall('.//d:response', {'d': 'DAV:'})
            
            batch_events = []
            
            for resp in responses:
                href = resp.find('./d:href', {'d': 'DAV:'})
                calendar_data = resp.find('.//c:calendar-data', {'c': 'urn:ietf:params:xml:ns:caldav'})
                
                if calendar_data is None or href is None:
                    continue
                
                # Parse iCalendar data
                ical_data = calendar_data.text
                
                # Extract event information using regex
                # First find the VEVENT section to avoid matching timezone definitions
                vevent_match = re.search(r'BEGIN:VEVENT(.*?)END:VEVENT', ical_data, re.DOTALL)
                if not vevent_match:
                    continue
                
                vevent_data = vevent_match.group(1)
                
                summary_match = re.search(r'SUMMARY:(.*?)(?:\r?\n)', vevent_data)
                dtstart_match = re.search(r'DTSTART(?:;(?:TZID=([^:]*?)|VALUE=DATE))?:(.*?)(?:\r?\n)', vevent_data)
                dtend_match = re.search(r'DTEND(?:;(?:TZID=([^:]*?)|VALUE=DATE))?:(.*?)(?:\r?\n)', vevent_data)
                uid_match = re.search(r'UID:(.*?)(?:\r?\n)', vevent_data)
                
                if summary_match and dtstart_match:
                    summary = summary_match.group(1)
                    
                    # Parse start date/time
                    start_dt_str = dtstart_match.group(2)
                    start_timezone = dtstart_match.group(1) if dtstart_match.group(1) else "UTC"
                    
                    # Parse end date/time if available
                    end_dt_str = dtend_match.group(2) if dtend_match else None
                    end_timezone = dtend_match.group(1) if dtend_match and dtend_match.group(1) else "UTC"
                    
                    # Format the date for display
                    try:
                        
                        if len(start_dt_str) == 8:  # All-day event (YYYYMMDD)
                            start_date = datetime.strptime(start_dt_str, "%Y%m%d").strftime("%Y-%m-%d")
                            end_date = datetime.strptime(end_dt_str, "%Y%m%d").strftime("%Y-%m-%d") if end_dt_str else start_date
                            is_all_day = True
                        else:  # Regular event with time
                            if 'T' in start_dt_str:
                                # Handle different time formats
                                if start_dt_str.endswith('Z'):
                                    start_date = datetime.strptime(start_dt_str, "%Y%m%dT%H%M%SZ").strftime("%Y-%m-%d %H:%M")
                                else:
                                    # Handle non-UTC times
                                    start_date = datetime.strptime(start_dt_str, "%Y%m%dT%H%M%S").strftime("%Y-%m-%d %H:%M")
                            else:
                                start_date = datetime.strptime(start_dt_str, "%Y%m%d").strftime("%Y-%m-%d")
                            
                            if end_dt_str:
                                if 'T' in end_dt_str:
                                    # Handle different time formats for end date
                                    if end_dt_str.endswith('Z'):
                                        end_date = datetime.strptime(end_dt_str, "%Y%m%dT%H%M%SZ").strftime("%Y-%m-%d %H:%M")
                                    else:
                                        # Handle non-UTC times
                                        end_date = datetime.strptime(end_dt_str, "%Y%m%dT%H%M%S").strftime("%Y-%m-%d %H:%M")
                                else:
                                    end_date = datetime.strptime(end_dt_str, "%Y%m%d").strftime("%Y-%m-%d")
                            else:
                                end_date = start_date
                            
                            is_all_day = 'T' not in start_dt_str
                    except ValueError as e:
                        print(f"  Date parsing error: {e} for event '{summary_match.group(1)}' with date '{start_dt_str}'")
                        # If there's an error parsing the date, use the raw strings
                        start_date = start_dt_str
                        end_date = end_dt_str if end_dt_str else start_date
                        is_all_day = False
                    
                    uid = uid_match.group(1) if uid_match else "Unknown"
                    
                    event_info = {
                        'summary': summary,
                        'start': start_date,
                        'end': end_date,
                        'start_timezone': start_timezone,
                        'end_timezone': end_timezone,
                        'uid': uid,
                        'calendar': calendar_name,
                        'is_all_day': is_all_day,
                        'href': href.text
                    }
                    
                    batch_events.append(event_info)
            
            all_events.extend(batch_events)
            print(f"  Successfully processed {len(batch_events)} events in batch {batch_num}.")
            
        except Exception as e:
            print(f"  Error processing batch {batch_num}: {str(e)}")
    
    return all_events


def get_recent_events(calendar_url, calendar_name, days_back=30):
    """
    Fetch events from the specified number of days back for a specific calendar.
    This is a two-step process:
    1. Get event URLs using REPORT
    2. Get event details using calendar-multiget
    
    Args:
        calendar_url (str): The URL of the calendar
        calendar_name (str): The name of the calendar for display purposes
        days_back (int): Number of days to look back for events (default: 30)
        
    Returns:
        list: A list of dictionaries containing event information
    """
    # Step 1: Get event URLs
    event_urls = get_event_urls(calendar_url, calendar_name, days_back)
    
    if not event_urls:
        return []
    
    # Step 2: Get event details using calendar-multiget
    return get_event_details(event_urls, calendar_name)


def get_calendar_list():
    """
    Fetch a list of calendars from the CalDAV server.
    Returns a list of dictionaries containing calendar information.
    """
    # Load environment variables
    load_dotenv()
    caldav_url = os.environ.get('CALDAV_URL')
    username = os.environ.get('CALDAV_USERNAME')
    password = os.environ.get('CALDAV_PASSWORD')
    
    # Define XML namespaces
    namespaces = {
        'd': 'DAV:',
        'c': 'urn:ietf:params:xml:ns:caldav',
        'cs': 'http://calendarserver.org/ns/'
    }
    
    # Register namespaces for proper XML parsing
    for prefix, uri in namespaces.items():
        ET.register_namespace(prefix, uri)
    
    # Step 1: Discover the user's principal URL
    headers = {
        "Content-Type": "application/xml; charset=utf-8",
        "Depth": "0"
    }
    
    principal_xml = """
    <d:propfind xmlns:d="DAV:">
      <d:prop>
        <d:current-user-principal />
      </d:prop>
    </d:propfind>
    """
    
    response = requests.request("PROPFIND", caldav_url, data=principal_xml, headers=headers, auth=(username, password))
    
    if response.status_code != 207:  # 207 is Multi-Status response
        print(f"Failed to discover principal URL. Status code: {response.status_code}")
        print(f"Response: {response.text}")
        return []
    
    # Parse the XML response to get the principal URL
    root = ET.fromstring(response.text)
    principal_elem = root.find('.//d:current-user-principal/d:href', namespaces)
    
    if principal_elem is None:
        print("Could not find current-user-principal element in response")
        return []
    
    principal_url = principal_elem.text
    principal_full_url = f"{caldav_url}{principal_url}" if principal_url.startswith('/') else principal_url
    
    print(f"Principal URL: {principal_full_url}")
    
    # Step 2: Find the calendar home set
    calendar_home_xml = """
    <d:propfind xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">
      <d:prop>
        <c:calendar-home-set />
      </d:prop>
    </d:propfind>
    """
    
    response = requests.request("PROPFIND", principal_full_url, data=calendar_home_xml, headers=headers, auth=(username, password))
    
    if response.status_code != 207:
        print(f"Failed to discover calendar home set. Status code: {response.status_code}")
        print(f"Response: {response.text}")
        return []
    
    # Parse the XML response to get the calendar home set URL
    root = ET.fromstring(response.text)
    calendar_home_elem = root.find('.//c:calendar-home-set/d:href', namespaces)
    
    if calendar_home_elem is None:
        print("Could not find calendar-home-set element in response")
        return []
    
    calendar_home = calendar_home_elem.text
    calendar_home_url = f"{caldav_url}{calendar_home}" if calendar_home.startswith('/') else calendar_home
    
    print(f"Calendar Home URL: {calendar_home_url}")
    
    # Step 3: List all calendars
    headers["Depth"] = "1"  # We want to list all calendars, not just the home
    
    calendar_list_xml = """
    <d:propfind xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav" xmlns:cs="http://calendarserver.org/ns/">
      <d:prop>
        <d:resourcetype />
        <d:displayname />
        <cs:getctag />
        <c:calendar-description />
        <c:calendar-color />
      </d:prop>
    </d:propfind>
    """
    
    response = requests.request("PROPFIND", calendar_home_url, data=calendar_list_xml, headers=headers, auth=(username, password))
    
    if response.status_code != 207:
        print(f"Failed to list calendars. Status code: {response.status_code}")
        print(f"Response: {response.text}")
        return []
    
    # Parse the XML response to get the list of calendars
    root = ET.fromstring(response.text)
    responses = root.findall('.//d:response', namespaces)
    
    calendars = []
    
    for resp in responses:
        # Check if this is a calendar (has resourcetype = calendar)
        resource_type = resp.find('.//d:resourcetype/c:calendar', namespaces)
        
        # Skip if not a calendar
        if resource_type is None:
            continue
        
        # Get calendar properties
        href = resp.find('./d:href', namespaces)
        displayname = resp.find('.//d:displayname', namespaces)
        description = resp.find('.//c:calendar-description', namespaces)
        color = resp.find('.//c:calendar-color', namespaces)
        ctag = resp.find('.//cs:getctag', namespaces)
        
        calendar_info = {
            'url': href.text if href is not None else None,
            'name': displayname.text if displayname is not None else None,
            'description': description.text if description is not None else None,
            'color': color.text if color is not None else None,
            'ctag': ctag.text if ctag is not None else None
        }
        
        calendars.append(calendar_info)
    
    return calendars


def main():
    # Get list of calendars
    print("Fetching calendar list...")
    calendars = get_calendar_list()
    
    # Print calendar information
    print("\n===== Calendar List =====")
    if not calendars:
        print("No calendars found or error occurred.")
    else:
        print(f"Found {len(calendars)} calendars:")
        for i, calendar in enumerate(calendars, 1):
            print(f"\nCalendar {i}:")
            print(f"  Name: {calendar['name']}")
            print(f"  URL: {calendar['url']}")
            if calendar['description']:
                print(f"  Description: {calendar['description']}")
            if calendar['color']:
                print(f"  Color: {calendar['color']}")
    
    # Demonstrate the two-step process for fetching events
    days_to_look_back = 7
    print(f"\n===== Step 1: Get Event URLs using REPORT (Last {days_to_look_back} Days) =====")
    
    all_event_urls = []
    calendar_event_urls = {}  # Dictionary to store event URLs by calendar
    
    if calendars:
        # Process only the first calendar to reduce memory usage
        for calendar in [calendars[0]]:
            print(f"\nFetching event URLs from calendar: {calendar['name']}...")
            event_urls = get_event_urls(calendar['url'], calendar['name'], days_to_look_back)
            
            if event_urls:
                all_event_urls.extend(event_urls)
                calendar_event_urls[calendar['name']] = event_urls
                print(f"Found {len(event_urls)} events in this calendar:")
                for i, url in enumerate(event_urls, 1):
                    print(f"  {i}. {url}")
            else:
                print(f"No events found in calendar: {calendar['name']}")
        
        # Step 2: Get event details using calendar-multiget
        print(f"\n===== Step 2: Get Event Details using calendar-multiget =====")
        all_events = []
        
        for calendar_name, event_urls in calendar_event_urls.items():
            if event_urls:
                print(f"\nFetching event details for calendar: {calendar_name}...")
                events = get_event_details(event_urls, calendar_name)
                all_events.extend(events)
                print(f"Successfully fetched details for {len(events)} events.")
        
        # Sort all events by start date
        all_events.sort(key=lambda x: x['start'])
        
        # Display all events
        print("\n===== All Recent Events (Sorted by Date) =====")
        if not all_events:
            print(f"No events found in the last {days_to_look_back} days.")
        else:
            print(f"Found {len(all_events)} events in the last {days_to_look_back} days:")
            for i, event in enumerate(all_events, 1):
                print(f"\nEvent {i}:")
                print(f"  Summary: {event['summary']}")
                print(f"  Calendar: {event['calendar']}")
                print(f"  URL: {event['href']}")
                if event['is_all_day']:
                    print(f"  Date: {event['start']} (All day)")
                else:
                    if event['start'] == event['end']:
                        print(f"  Date/Time: {event['start']} ({event['start_timezone']})")
                    else:
                        print(f"  Start: {event['start']} ({event['start_timezone']})")
                        print(f"  End: {event['end']} ({event['end_timezone']})")
    else:
        print("No calendars available to fetch events from.")

if __name__ == "__main__":
    main()
