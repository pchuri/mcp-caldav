"""
CalendarResources 테스트
"""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

from src.resources.calendar_resources import CalendarResources

@pytest.fixture
def mock_caldav_clients():
    """CalDAV 클라이언트 모의 객체를 생성합니다."""
    return {"test_client_id": MagicMock()}

@pytest.fixture
def calendar_resources(mock_caldav_clients):
    """CalendarResources 인스턴스를 생성합니다."""
    return CalendarResources(mock_caldav_clients)

def test_get_calendars(calendar_resources, mock_caldav_clients):
    """get_calendars 메서드를 테스트합니다."""
    # Mock 설정
    mock_client = mock_caldav_clients["test_client_id"]
    mock_principal = MagicMock()
    mock_client.principal.return_value = mock_principal
    
    mock_calendar1 = MagicMock()
    mock_calendar1.url = "calendar1_url"
    mock_calendar1.name = "Calendar 1"
    mock_calendar1.description = "Description 1"
    mock_calendar1.color = "blue"
    
    mock_calendar2 = MagicMock()
    mock_calendar2.url = "calendar2_url"
    mock_calendar2.name = "Calendar 2"
    mock_calendar2.description = "Description 2"
    mock_calendar2.color = "red"
    
    mock_principal.calendars.return_value = [mock_calendar1, mock_calendar2]
    
    # 함수 호출
    result = calendar_resources.get_calendars("test_client_id")
    
    # 검증
    assert len(result) == 2
    assert result[0]["id"] == "calendar1_url"
    assert result[0]["name"] == "Calendar 1"
    assert result[0]["description"] == "Description 1"
    assert result[0]["color"] == "blue"
    assert result[1]["id"] == "calendar2_url"
    assert result[1]["name"] == "Calendar 2"
    assert result[1]["description"] == "Description 2"
    assert result[1]["color"] == "red"
    
    # 메서드 호출 검증
    mock_client.principal.assert_called_once()
    mock_principal.calendars.assert_called_once()

def test_get_calendars_invalid_client_id(calendar_resources):
    """유효하지 않은 클라이언트 ID로 get_calendars를 호출하는 경우를 테스트합니다."""
    with pytest.raises(ValueError, match="유효하지 않은 클라이언트 ID입니다"):
        calendar_resources.get_calendars("invalid_client_id")

def test_get_events(calendar_resources, mock_caldav_clients):
    """get_events 메서드를 테스트합니다."""
    # Mock 설정
    mock_client = mock_caldav_clients["test_client_id"]
    mock_calendar = MagicMock()
    mock_client.calendar.return_value = mock_calendar
    
    mock_event1 = MagicMock()
    mock_event1.url = "event1_url"
    mock_event1.data = "event1_data"
    mock_event1.vobject_instance.vevent.uid.value = "event1_uid"
    mock_event1.vobject_instance.vevent.summary.value = "Event 1"
    mock_event1.vobject_instance.vevent.dtstart.value = datetime(2025, 4, 1, 10, 0)
    mock_event1.vobject_instance.vevent.dtend.value = datetime(2025, 4, 1, 11, 0)
    mock_event1.vobject_instance.vevent.location.value = "Location 1"
    mock_event1.vobject_instance.vevent.description.value = "Description 1"
    
    mock_event2 = MagicMock()
    mock_event2.url = "event2_url"
    mock_event2.data = "event2_data"
    mock_event2.vobject_instance.vevent.uid.value = "event2_uid"
    mock_event2.vobject_instance.vevent.summary.value = "Event 2"
    mock_event2.vobject_instance.vevent.dtstart.value = datetime(2025, 4, 2, 10, 0)
    mock_event2.vobject_instance.vevent.dtend.value = datetime(2025, 4, 2, 11, 0)
    mock_event2.vobject_instance.vevent.location.value = "Location 2"
    mock_event2.vobject_instance.vevent.description.value = "Description 2"
    
    mock_calendar.date_search.return_value = [mock_event1, mock_event2]
    
    # 함수 호출
    result = calendar_resources.get_events(
        "test_client_id", 
        "calendar_id", 
        "2025-04-01T00:00:00", 
        "2025-04-30T00:00:00"
    )
    
    # 검증
    assert len(result) == 2
    assert result[0]["id"] == "event1_url"
    assert result[0]["uid"] == "event1_uid"
    assert result[0]["summary"] == "Event 1"
    assert str(result[0]["start"]) == "2025-04-01 10:00:00"
    assert str(result[0]["end"]) == "2025-04-01 11:00:00"
    assert result[0]["location"] == "Location 1"
    assert result[0]["description"] == "Description 1"
    
    assert result[1]["id"] == "event2_url"
    assert result[1]["uid"] == "event2_uid"
    assert result[1]["summary"] == "Event 2"
    assert str(result[1]["start"]) == "2025-04-02 10:00:00"
    assert str(result[1]["end"]) == "2025-04-02 11:00:00"
    assert result[1]["location"] == "Location 2"
    assert result[1]["description"] == "Description 2"
    
    # 메서드 호출 검증
    mock_client.calendar.assert_called_once_with(url="calendar_id")
    mock_calendar.date_search.assert_called_once()

def test_get_events_invalid_client_id(calendar_resources):
    """유효하지 않은 클라이언트 ID로 get_events를 호출하는 경우를 테스트합니다."""
    with pytest.raises(ValueError, match="유효하지 않은 클라이언트 ID입니다"):
        calendar_resources.get_events(
            "invalid_client_id", 
            "calendar_id", 
            "2025-04-01T00:00:00", 
            "2025-04-30T00:00:00"
        )
