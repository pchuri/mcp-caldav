"""
CalDAV 리소스 모듈
"""
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# 캘린더 리소스 클래스
class CalendarResources:
    def __init__(self, caldav_clients):
        self.caldav_clients = caldav_clients

    def register(self, mcp):
        """MCP 서버에 리소스 등록"""
        mcp.resource(uri="calendars://{client_id}")(self.get_calendars)
        
        # 쿼리 매개변수가 아니라 함수 시그니처 변경 방식으로 해결
        @mcp.resource(uri="events://{client_id}/{calendar_id}")
        def get_events_wrapper(client_id: str, calendar_id: str) -> list:
            """이벤트 리소스 래퍼"""
            # URI에서 time_min과 time_max를 가져올 수 없으므로 기본값 사용
            # 현재부터 30일 범위의 이벤트를 반환
            from datetime import datetime, timedelta
            now = datetime.now()
            time_min = now.isoformat()
            time_max = (now + timedelta(days=30)).isoformat()
            return self.get_events(client_id, calendar_id, time_min, time_max)
            
        return self

    def get_calendars(self, client_id: str) -> list:
        """사용자의 모든 캘린더 목록을 가져옵니다."""
        if client_id not in self.caldav_clients:
            raise ValueError("유효하지 않은 클라이언트 ID입니다. 먼저 connect_caldav를 호출하세요.")
        
        try:
            client = self.caldav_clients[client_id]
            principal = client.principal()
            calendars = principal.calendars()
            
            result = []
            for calendar in calendars:
                result.append({
                    "id": calendar.url,
                    "name": calendar.name,
                    "description": getattr(calendar, "description", ""),
                    "color": getattr(calendar, "color", "")
                })
            
            return result
        except Exception as e:
            logger.error(f"캘린더 목록 조회 오류: {str(e)}")
            raise ValueError(f"캘린더 목록 가져오기 실패: {str(e)}")

    def get_events(self, client_id: str, calendar_id: str, time_min: str, time_max: str) -> list:
        """특정 캘린더의 이벤트를 가져옵니다."""
        if client_id not in self.caldav_clients:
            raise ValueError("유효하지 않은 클라이언트 ID입니다. 먼저 connect_caldav를 호출하세요.")
        
        try:
            client = self.caldav_clients[client_id]
            calendar = client.calendar(url=calendar_id)
            
            # 시간 범위 설정
            start_time = datetime.fromisoformat(time_min.replace('Z', '+00:00'))
            end_time = datetime.fromisoformat(time_max.replace('Z', '+00:00'))
            
            # 이벤트 조회
            events = calendar.date_search(start=start_time, end=end_time)
            
            result = []
            for event in events:
                event_data = event.data
                vevent = event.vobject_instance.vevent
                
                result.append({
                    "id": event.url,
                    "uid": str(vevent.uid.value) if hasattr(vevent, 'uid') else None,
                    "summary": str(vevent.summary.value) if hasattr(vevent, 'summary') else "제목 없음",
                    "start": str(vevent.dtstart.value) if hasattr(vevent, 'dtstart') else None,
                    "end": str(vevent.dtend.value) if hasattr(vevent, 'dtend') else None,
                    "location": str(vevent.location.value) if hasattr(vevent, 'location') else "",
                    "description": str(vevent.description.value) if hasattr(vevent, 'description') else ""
                })
            
            return result
        except Exception as e:
            logger.error(f"이벤트 조회 오류: {str(e)}")
            raise ValueError(f"이벤트 가져오기 실패: {str(e)}")
