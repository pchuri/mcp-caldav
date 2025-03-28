#!/usr/bin/env python
"""
CalDAV MCP 서버 독립 실행형 진입점
"""
import sys
import os
import logging
from mcp.server.fastmcp import FastMCP
from fastapi import FastAPI, HTTPException
from typing import Optional
import uvicorn
import uuid
from datetime import datetime

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 기본 클래스 및 메서드 직접 정의
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

class MCPCalDAV:
    def __init__(self, name="MCP-CalDAV"):
        # MCP 서버 초기화
        self.mcp = FastMCP(name)
        
        # CalDAV 클라이언트 저장소
        self.caldav_clients = {}
        
        # 리소스 및 도구 등록
        self.resources = CalendarResources(self.caldav_clients).register(self.mcp)
        self.tools = CalendarTools(self.caldav_clients).register(self.mcp)
        
        # FastAPI 앱 초기화 
        self.app = FastAPI(title="MCP-CalDAV API", description="CalDAV 서버와 MCP를 연동하는 API")
        self._setup_routes()
    
    def _setup_routes(self):
        # 라우트 설정
        @self.app.post("/api/caldav/connect")
        async def api_connect_caldav(server_url: str, username: str, password: str):
            try:
                result = self.tools.connect_caldav(server_url, username, password)
                return result
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/api/caldav/calendars")
        async def api_get_calendars(client_id: str):
            try:
                result = self.resources.get_calendars(client_id)
                return result
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/api/caldav/events")
        async def api_get_events(client_id: str, calendar_id: str, time_min: str, time_max: str):
            try:
                result = self.resources.get_events(client_id, calendar_id, time_min, time_max)
                return result
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/api/caldav/events")
        async def api_create_event(client_id: str, calendar_id: str, summary: str, start: str, end: str, 
                                location: Optional[str] = "", description: Optional[str] = ""):
            try:
                result = self.tools.create_event(client_id, calendar_id, summary, start, end, location, description)
                return result
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.put("/api/caldav/events/{event_id}")
        async def api_update_event(event_id: str, client_id: str, summary: Optional[str] = None, 
                                start: Optional[str] = None, end: Optional[str] = None, 
                                location: Optional[str] = None, description: Optional[str] = None):
            try:
                result = self.tools.update_event(client_id, event_id, summary, start, end, location, description)
                return result
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.delete("/api/caldav/events/{event_id}")
        async def api_delete_event(event_id: str, client_id: str):
            try:
                result = self.tools.delete_event(client_id, event_id)
                return result
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
    
    def run(self, host="0.0.0.0", port=8000):
        """MCP 서버와 FastAPI 서버를 실행합니다."""
        logger.info(f"MCP 서버를 시작합니다.")
        
        # FastAPI 앱에 MCP 서버 마운트
        # 최신 MCP SDK에서는 run_bg 대신 SSE 앱을 FastAPI 앱에 마운트하는 방식 사용
        from starlette.routing import Mount
        mcp_routes = [Mount("/mcp", app=self.mcp.sse_app())]
        self.app.router.routes.extend(mcp_routes)
        
        logger.info(f"FastAPI 서버를 시작합니다. (http://{host}:{port})")
        logger.info(f"MCP 엔드포인트: http://{host}:{port}/mcp")
        uvicorn.run(self.app, host=host, port=port)

# 메인 함수
def main():
    """메인 애플리케이션 진입점"""
    mcp_caldav = MCPCalDAV()
    mcp_caldav.run()

if __name__ == "__main__":
    main()
