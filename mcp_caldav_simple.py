#!/usr/bin/env python
"""
CalDAV MCP 서버 - 최소 의존성 버전
"""
import logging
import uuid
from datetime import datetime, timedelta
from mcp.server.fastmcp import FastMCP

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# MCP 서버 생성
mcp = FastMCP("MCP-CalDAV")

# CalDAV 클라이언트 저장소
caldav_clients = {}

# 리소스 관련 함수들
@mcp.resource(uri="calendars://{client_id}")
def get_calendars(client_id: str) -> list:
    """사용자의 모든 캘린더 목록을 가져옵니다."""
    if client_id not in caldav_clients:
        raise ValueError("유효하지 않은 클라이언트 ID입니다. 먼저 connect_caldav를 호출하세요.")
    
    try:
        client = caldav_clients[client_id]
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

@mcp.resource(uri="events://{client_id}/{calendar_id}")
def get_events_wrapper(client_id: str, calendar_id: str) -> list:
    """이벤트 리소스 래퍼"""
    # 현재부터 30일 범위의 이벤트를 반환
    now = datetime.now()
    time_min = now.isoformat()
    time_max = (now + timedelta(days=30)).isoformat()
    return get_events(client_id, calendar_id, time_min, time_max)

def get_events(client_id: str, calendar_id: str, time_min: str, time_max: str) -> list:
    """특정 캘린더의 이벤트를 가져옵니다."""
    if client_id not in caldav_clients:
        raise ValueError("유효하지 않은 클라이언트 ID입니다. 먼저 connect_caldav를 호출하세요.")
    
    try:
        client = caldav_clients[client_id]
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

# 도구 관련 함수들
@mcp.tool(name="connect_caldav")
def connect_caldav(server_url: str, username: str, password: str) -> dict:
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
        caldav_clients[client_id] = client
        
        return {
            "client_id": client_id,
            "status": "connected",
            "message": "CalDAV 서버에 성공적으로 연결되었습니다."
        }
    except Exception as e:
        logger.error(f"CalDAV 연결 오류: {str(e)}")
        raise ValueError(f"CalDAV 연결 실패: {str(e)}")

@mcp.tool(name="create_event")
def create_event(client_id: str, calendar_id: str, summary: str, start: str, end: str, 
               location: str = "", description: str = "") -> dict:
    """캘린더에 새 이벤트를 생성합니다."""
    if client_id not in caldav_clients:
        raise ValueError("유효하지 않은 클라이언트 ID입니다. 먼저 connect_caldav를 호출하세요.")
    
    try:
        client = caldav_clients[client_id]
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

@mcp.tool(name="update_event")
def update_event(client_id: str, event_id: str, summary: str = None, start: str = None, 
               end: str = None, location: str = None, description: str = None) -> dict:
    """기존 이벤트를 업데이트합니다."""
    if client_id not in caldav_clients:
        raise ValueError("유효하지 않은 클라이언트 ID입니다. 먼저 connect_caldav를 호출하세요.")
    
    try:
        client = caldav_clients[client_id]
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

@mcp.tool(name="delete_event")
def delete_event(client_id: str, event_id: str) -> dict:
    """이벤트를 삭제합니다."""
    if client_id not in caldav_clients:
        raise ValueError("유효하지 않은 클라이언트 ID입니다. 먼저 connect_caldav를 호출하세요.")
    
    try:
        client = caldav_clients[client_id]
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

# 사용 예시 프롬프트 추가
@mcp.prompt()
def connect_caldav_prompt() -> str:
    """CalDAV 서버 연결을 위한 프롬프트"""
    return """
    아래 정보를 입력하여 CalDAV 서버에 연결해주세요:
    
    서버 URL: (예: https://nextcloud.example.com/remote.php/dav/)
    사용자 이름: 
    비밀번호: 
    """

@mcp.prompt()
def create_event_prompt() -> str:
    """이벤트 생성을 위한 프롬프트"""
    return """
    아래 정보를 입력하여 새 이벤트를 생성해주세요:
    
    제목: 
    시작 시간: (예: 2025-04-01T10:00:00)
    종료 시간: (예: 2025-04-01T11:00:00)
    위치: (선택사항)
    설명: (선택사항)
    """

# 메인 실행 코드
if __name__ == "__main__":
    logger.info("MCP-CalDAV 서버를 시작합니다.")
    mcp.run()
