"""
CalendarTools 테스트
"""
import pytest
from unittest.mock import MagicMock, patch
import uuid
from datetime import datetime

from src.tools.calendar_tools import CalendarTools

@pytest.fixture
def mock_caldav_clients():
    """CalDAV 클라이언트 모의 객체를 생성합니다."""
    return {"test_client_id": MagicMock()}

@pytest.fixture
def calendar_tools(mock_caldav_clients):
    """CalendarTools 인스턴스를 생성합니다."""
    return CalendarTools(mock_caldav_clients)

@patch('uuid.uuid4')
def test_connect_caldav(mock_uuid4, calendar_tools):
    """connect_caldav 메서드를 테스트합니다."""
    # UUID 모의 설정
    mock_uuid = "12345678-1234-5678-1234-567812345678"
    mock_uuid4.return_value = uuid.UUID(mock_uuid)
    
    # CalDAV 모듈 모의 설정
    mock_client = MagicMock()
    mock_principal = MagicMock()
    mock_client.principal.return_value = mock_principal
    
    with patch('caldav.DAVClient', return_value=mock_client):
        # 함수 호출
        result = calendar_tools.connect_caldav(
            server_url="https://example.com/dav",
            username="testuser",
            password="testpass"
        )
        
        # 검증
        assert result["client_id"] == mock_uuid
        assert result["status"] == "connected"
        assert "성공적으로 연결되었습니다" in result["message"]
        
        # 클라이언트가 저장되었는지 확인
        assert calendar_tools.caldav_clients[mock_uuid] == mock_client
        
        # 메서드 호출 검증
        mock_client.principal.assert_called_once()

def test_create_event(calendar_tools, mock_caldav_clients):
    """create_event 메서드를 테스트합니다."""
    # Mock 설정
    mock_client = mock_caldav_clients["test_client_id"]
    mock_calendar = MagicMock()
    mock_client.calendar.return_value = mock_calendar
    
    mock_event = MagicMock()
    mock_event.url = "event_url"
    mock_calendar.add_event.return_value = mock_event
    
    # UUID 모의 설정
    mock_uuid = "87654321-4321-8765-4321-876543210987"
    with patch('uuid.uuid4', return_value=uuid.UUID(mock_uuid)):
        # 함수 호출
        result = calendar_tools.create_event(
            client_id="test_client_id",
            calendar_id="calendar_id",
            summary="Test Event",
            start="2025-04-01T10:00:00",
            end="2025-04-01T11:00:00",
            location="Test Location",
            description="Test Description"
        )
        
        # 검증
        assert result["id"] == "event_url"
        assert result["uid"] == mock_uuid
        assert result["status"] == "created"
        assert "성공적으로 생성되었습니다" in result["message"]
        
        # 메서드 호출 검증
        mock_client.calendar.assert_called_once_with(url="calendar_id")
        mock_calendar.add_event.assert_called_once()
        
        # iCalendar 데이터 검증
        ical_data = mock_calendar.add_event.call_args[0][0]
        assert "BEGIN:VCALENDAR" in ical_data
        assert "SUMMARY:Test Event" in ical_data
        assert "LOCATION:Test Location" in ical_data
        assert "DESCRIPTION:Test Description" in ical_data
        assert f"UID:{mock_uuid}" in ical_data

def test_create_event_invalid_client_id(calendar_tools):
    """유효하지 않은 클라이언트 ID로 create_event를 호출하는 경우를 테스트합니다."""
    with pytest.raises(ValueError, match="유효하지 않은 클라이언트 ID입니다"):
        calendar_tools.create_event(
            client_id="invalid_client_id",
            calendar_id="calendar_id",
            summary="Test Event",
            start="2025-04-01T10:00:00",
            end="2025-04-01T11:00:00"
        )

def test_update_event(calendar_tools, mock_caldav_clients):
    """update_event 메서드를 테스트합니다."""
    # Mock 설정
    mock_client = mock_caldav_clients["test_client_id"]
    mock_event = MagicMock()
    mock_client.event_by_url.return_value = mock_event
    
    mock_vevent = MagicMock()
    mock_event.vobject_instance.vevent = mock_vevent
    
    # 함수 호출
    result = calendar_tools.update_event(
        client_id="test_client_id",
        event_id="event_id",
        summary="Updated Event",
        start="2025-04-02T10:00:00",
        end="2025-04-02T11:00:00",
        location="Updated Location",
        description="Updated Description"
    )
    
    # 검증
    assert result["id"] == mock_event.url
    assert result["status"] == "updated"
    assert "성공적으로 업데이트되었습니다" in result["message"]
    
    # 메서드 호출 검증
    mock_client.event_by_url.assert_called_once_with("event_id")
    mock_event.save.assert_called_once()
    
    # 이벤트 데이터 업데이트 검증
    assert mock_vevent.summary.value == "Updated Event"
    assert mock_vevent.location.value == "Updated Location"
    assert mock_vevent.description.value == "Updated Description"

def test_delete_event(calendar_tools, mock_caldav_clients):
    """delete_event 메서드를 테스트합니다."""
    # Mock 설정
    mock_client = mock_caldav_clients["test_client_id"]
    mock_event = MagicMock()
    mock_client.event_by_url.return_value = mock_event
    
    # 함수 호출
    result = calendar_tools.delete_event(
        client_id="test_client_id",
        event_id="event_id"
    )
    
    # 검증
    assert result["id"] == "event_id"
    assert result["status"] == "deleted"
    assert "성공적으로 삭제되었습니다" in result["message"]
    
    # 메서드 호출 검증
    mock_client.event_by_url.assert_called_once_with("event_id")
    mock_event.delete.assert_called_once()

def test_delete_event_invalid_client_id(calendar_tools):
    """유효하지 않은 클라이언트 ID로 delete_event를 호출하는 경우를 테스트합니다."""
    with pytest.raises(ValueError, match="유효하지 않은 클라이언트 ID입니다"):
        calendar_tools.delete_event(
            client_id="invalid_client_id",
            event_id="event_id"
        )
