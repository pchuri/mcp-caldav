"""
MCP-CalDAV - CalDAV 서버와 MCP를 연동하는 메인 모듈
"""
import logging
from mcp.server.fastmcp import FastMCP
from fastapi import FastAPI, HTTPException
from typing import Optional
import uvicorn

from src.resources.calendar_resources import CalendarResources
from src.tools.calendar_tools import CalendarTools

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
