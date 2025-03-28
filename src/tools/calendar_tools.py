"""
CalDAV 도구 모듈
"""
import logging
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)

# 캘린더 도구 클래스
class CalendarTools:
    def __init__(self, caldav_clients):
        self.caldav_clients = caldav_clients

    def register(self, mcp):
        """MCP 서버에 도구 등록"""
        mcp.tool(name="connect_caldav")(self.connect_caldav)
        mcp.tool(name="create_event")(self.create_event)
        mcp.tool(name="update_event")(self.update_event)
        mcp.tool(name="delete_event")(self.delete_event)
        return self

    def connect_caldav(self, server_url: str, username: str, password: str) -> dict:
        """CalDAV 서버에 연결하고 인증합니다."""
        try:
            # CalDAV 서버에 연결
            import caldav
            client = caldav.DAVClient(
                url=server_url,
                username=username,
                password=password
            )
            
            # 연결 테스트
            principal = client.principal()
            
            # 클라이언트 ID 생성 및 저장
            client_id = str(uuid.uuid4())
            self.caldav_clients[client_id] = client
            
            return {
                "client_id": client_id,
                "status": "connected",
                "message": "CalDAV 서버에 성공적으로 연결되었습니다."
            }
        except Exception as e:
            logger.error(f"CalDAV 연결 오류: {str(e)}")
            raise ValueError(f"CalDAV 연결 실패: {str(e)}")

    def create_event(self, client_id: str, calendar_id: str, summary: str, start: str, end: str, 
                    location: str = "", description: str = "") -> dict:
        """캘린더에 새 이벤트를 생성합니다."""
        if client_id not in self.caldav_clients:
            raise ValueError("유효하지 않은 클라이언트 ID입니다. 먼저 connect_caldav를 호출하세요.")
        
        try:
            client = self.caldav_clients[client_id]
            calendar = client.calendar(url=calendar_id)
            
            # 이벤트 생성
            event_id = str(uuid.uuid4())
            
            # iCalendar 형식의 이벤트 데이터 생성
            ical_data = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Anthropic MPC-CalDAV//EN
BEGIN:VEVENT
UID:{event_id}
DTSTAMP:{datetime.now().strftime('%Y%m%dT%H%M%SZ')}
DTSTART:{datetime.fromisoformat(start.replace('Z', '+00:00')).strftime('%Y%m%dT%H%M%SZ')}
DTEND:{datetime.fromisoformat(end.replace('Z', '+00:00')).strftime('%Y%m%dT%H%M%SZ')}
SUMMARY:{summary}
LOCATION:{location}
DESCRIPTION:{description}
END:VEVENT
END:VCALENDAR"""
            
            # 이벤트 추가
            event = calendar.add_event(ical_data)
            
            return {
                "id": event.url,
                "uid": event_id,
                "status": "created",
                "message": "이벤트가 성공적으로 생성되었습니다."
            }
        except Exception as e:
            logger.error(f"이벤트 생성 오류: {str(e)}")
            raise ValueError(f"이벤트 생성 실패: {str(e)}")

    def update_event(self, client_id: str, event_id: str, summary: str = None, start: str = None, 
                    end: str = None, location: str = None, description: str = None) -> dict:
        """기존 이벤트를 업데이트합니다."""
        if client_id not in self.caldav_clients:
            raise ValueError("유효하지 않은 클라이언트 ID입니다. 먼저 connect_caldav를 호출하세요.")
        
        try:
            client = self.caldav_clients[client_id]
            event = client.event_by_url(event_id)
            
            # 이벤트 데이터 가져오기
            vevent = event.vobject_instance.vevent
            
            # 업데이트할 필드들 적용
            if summary is not None:
                vevent.summary.value = summary
            
            if start is not None:
                vevent.dtstart.value = datetime.fromisoformat(start.replace('Z', '+00:00'))
            
            if end is not None:
                vevent.dtend.value = datetime.fromisoformat(end.replace('Z', '+00:00'))
            
            if location is not None:
                if hasattr(vevent, 'location'):
                    vevent.location.value = location
                else:
                    vevent.add('location').value = location
            
            if description is not None:
                if hasattr(vevent, 'description'):
                    vevent.description.value = description
                else:
                    vevent.add('description').value = description
            
            # 이벤트 업데이트
            event.save()
            
            return {
                "id": event.url,
                "status": "updated",
                "message": "이벤트가 성공적으로 업데이트되었습니다."
            }
        except Exception as e:
            logger.error(f"이벤트 업데이트 오류: {str(e)}")
            raise ValueError(f"이벤트 업데이트 실패: {str(e)}")

    def delete_event(self, client_id: str, event_id: str) -> dict:
        """이벤트를 삭제합니다."""
        if client_id not in self.caldav_clients:
            raise ValueError("유효하지 않은 클라이언트 ID입니다. 먼저 connect_caldav를 호출하세요.")
        
        try:
            client = self.caldav_clients[client_id]
            event = client.event_by_url(event_id)
            
            # 이벤트 삭제
            event.delete()
            
            return {
                "id": event_id,
                "status": "deleted",
                "message": "이벤트가 성공적으로 삭제되었습니다."
            }
        except Exception as e:
            logger.error(f"이벤트 삭제 오류: {str(e)}")
            raise ValueError(f"이벤트 삭제 실패: {str(e)}")
