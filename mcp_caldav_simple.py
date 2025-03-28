#!/usr/bin/env python
"""
CalDAV MCP 서버 - 최소 의존성 버전
환경변수에서 서버 URL, 사용자 이름, 비밀번호를 읽어올 수 있습니다.
"""
import logging
import os
from datetime import datetime, timedelta
from mcp.server.fastmcp import FastMCP

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# MCP 서버 생성
mcp = FastMCP("MCP-CalDAV")

# 전역 CalDAV 클라이언트 설정
caldav_client = None
principal = None

def get_events(calendar_id: str, time_min: str, time_max: str, expand: bool = True, 
              event_type: str = "event", category: str = None) -> list:
    """
    특정 캘린더의 이벤트를 가져옵니다.
    
    Args:
        calendar_id: 캘린더 URL
        time_min: 검색 시작 시간 (ISO 포맷)
        time_max: 검색 종료 시간 (ISO 포맷)
        expand: 반복 이벤트를 확장할지 여부 (기본값: True)
        event_type: 조회할 이벤트 유형 ('event', 'todo', 'journal' 중 하나)
        category: 특정 카테고리로 필터링 (선택사항)
    """
    if caldav_client is None:
        raise ValueError("CalDAV 클라이언트가 설정되지 않았습니다. 먼저 connect_caldav를 호출하세요.")
    
    try:
        calendar = caldav_client.calendar(url=calendar_id)
        
        # 시간 범위 설정
        start_time = datetime.fromisoformat(time_min.replace('Z', '+00:00'))
        end_time = datetime.fromisoformat(time_max.replace('Z', '+00:00'))
        
        # 검색 매개변수 설정
        search_params = {
            'start': start_time,
            'end': end_time,
            'expand': expand
        }
        
        # 이벤트 유형 설정
        if event_type.lower() == 'event':
            search_params['event'] = True
        elif event_type.lower() == 'todo':
            search_params['todo'] = True
        elif event_type.lower() == 'journal':
            search_params['journal'] = True
            
        # 카테고리 필터링 추가
        if category:
            search_params['category'] = category
            
        # 이벤트 검색 - search 메서드 사용, expand 옵션 문제 발생 시 expand=False로 재시도
        try:
            events = calendar.search(**search_params)
        except Exception as e:
            logger.warning(f"search with expand parameter failed: {str(e)}. Retrying with expand=False.")
            search_params['expand'] = False
            try:
                events = calendar.search(**search_params)
            except Exception as e2:
                logger.warning(f"search with expand=False failed: {str(e2)}. Retrying without expand parameter.")
                if 'expand' in search_params:
                    del search_params['expand']
                events = calendar.search(**search_params)
        
        result = []
        for event in events:
            try:
                # icalendar_component를 우선 사용해보고, 실패하면 vobject_instance로 대체
                try:
                    ical_comp = event.icalendar_component
                    result.append({
                        "id": event.url,
                        "uid": str(ical_comp.get("uid", "")),
                        "summary": str(ical_comp.get("summary", "제목 없음")),
                        "start": str(ical_comp.get("dtstart").dt if 'dtstart' in ical_comp else None),
                        "end": str(ical_comp.get("dtend").dt if 'dtend' in ical_comp else None),
                        "location": str(ical_comp.get("location", "")),
                        "description": str(ical_comp.get("description", ""))
                    })
                except Exception:
                    # icalendar_component 접근 실패 시 vobject_instance 사용
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
            except Exception as item_err:
                logger.warning(f"이벤트 정보 처리 중 오류: {str(item_err)}")
                # 최소한의 정보만 포함
                result.append({
                    "id": event.url,
                    "summary": "정보를 가져올 수 없는 이벤트",
                    "start": None,
                    "end": None
                })
        
        return result
    except Exception as e:
        logger.error(f"이벤트 조회 오류: {str(e)}")
        error_str = str(e).lower()
        if "propfinderror" in error_str or "notfounderror" in error_str:
            logger.warning("PropfindError or NotFoundError encountered; returning empty event list.")
            return []
        raise ValueError(f"이벤트 가져오기 실패: {str(e)}")

@mcp.tool(name="connect_caldav")
def connect_caldav() -> dict:
    global caldav_client, principal
    
    try:
        # 환경변수 또는 파라미터에서 연결 정보 가져오기
        final_server_url = os.environ.get('CALDAV_URL')
        final_username = os.environ.get('CALDAV_USERNAME')
        final_password = os.environ.get('CALDAV_PASSWORD')
        
        # 필수 정보 확인
        if not final_server_url:
            raise ValueError("서버 URL이 제공되지 않았습니다. 파라미터 또는 환경변수 CALDAV_URL을 설정하세요.")
        if not final_username:
            raise ValueError("사용자 이름이 제공되지 않았습니다. 파라미터 또는 환경변수 CALDAV_USERNAME을 설정하세요.")
        if not final_password:
            raise ValueError("비밀번호가 제공되지 않았습니다. 파라미터 또는 환경변수 CALDAV_PASSWORD을 설정하세요.")
        
        # URL에 scheme이 없는 경우 https:// 추가
        if not final_server_url.startswith(('http://', 'https://')):
            logger.info("URL에 스킴이 없습니다. 'https://'를 추가합니다.")
            final_server_url = 'https://' + final_server_url
        
        # CalDAV 서버에 연결
        import caldav
        
        caldav_client = caldav.DAVClient(
            url=final_server_url,
            username=final_username,
            password=final_password
        )
        
        # 연결 테스트
        principal = caldav_client.principal()
        
        logger.info(f"CalDAV 서버 '{final_server_url}'에 사용자 '{final_username}'로 성공적으로 연결되었습니다.")
        
        return {
            "status": "connected",
            "message": "CalDAV 서버에 성공적으로 연결되었습니다."
        }
    except Exception as e:
        logger.error(f"CalDAV 연결 오류: {str(e)}")
        raise ValueError(f"CalDAV 연결 실패: {str(e)}")

@mcp.tool(name="caldav_create_event")
def create_event(calendar_id: str, summary: str, start: str, end: str, 
               location: str = "", description: str = "", rrule: dict = None) -> dict:
    """
    캘린더에 새 이벤트를 생성합니다.
    
    Args:
        calendar_id: 캘린더 URL
        summary: 이벤트 제목
        start: 시작 시간 (ISO 포맷)
        end: 종료 시간 (ISO 포맷)
        location: 위치 (선택사항)
        description: 설명 (선택사항)
        rrule: 반복 규칙 (예: {"FREQ": "DAILY"}, 선택사항)
    """
    if principal is None:
        raise ValueError("CalDAV 클라이언트가 설정되지 않았습니다. 먼저 connect_caldav를 호출하세요.")
    
    try:
        calendar = caldav_client.calendar(url=calendar_id)
        
        # 시작 및 종료 시간 변환
        dtstart = datetime.fromisoformat(start.replace('Z', '+00:00'))
        dtend = datetime.fromisoformat(end.replace('Z', '+00:00'))
        
        # 예제 코드의 save_event 메서드 사용
        # 이 방법은 add_event 보다 더 높은 수준의 추상화를 제공합니다
        event = calendar.save_event(
            dtstart=dtstart,
            dtend=dtend, 
            summary=summary,
            location=location,
            description=description,
            rrule=rrule
        )
        
        # 이벤트 ID 추출
        uid = event.icalendar_component["uid"]
        
        return {
            "id": event.url,
            "uid": str(uid),
            "status": "created",
            "message": "이벤트가 성공적으로 생성되었습니다."
        }
    except Exception as e:
        logger.error(f"이벤트 생성 오류: {str(e)}")
        raise ValueError(f"이벤트 생성 실패: {str(e)}")

@mcp.tool(name="update_event")
def update_event(event_id: str, summary: str = None, start: str = None, 
               end: str = None, location: str = None, description: str = None) -> dict:
    """기존 이벤트를 업데이트합니다."""
    if principal is None:
        raise ValueError("CalDAV 클라이언트가 설정되지 않았습니다. 먼저 connect_caldav를 호출하세요.")
    
    try:
        event = principal.event_by_url(event_id)
        
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

@mcp.tool(name="caldav_delete_event")
def delete_event(event_id: str) -> dict:
    """이벤트를 삭제합니다."""
    if caldav_client is None:
        raise ValueError("CalDAV 클라이언트가 설정되지 않았습니다. 먼저 connect_caldav를 호출하세요.")
    
    try:
        event = caldav_client.event_by_url(event_id)
        
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

@mcp.tool(name="caldav_list_calendars")
def list_calendars() -> dict:
    """사용자의 모든 캘린더 목록을 가져옵니다."""
    if caldav_client is None or principal is None:
        raise ValueError("CalDAV 클라이언트가 설정되지 않았습니다. 먼저 connect_caldav를 호출하세요.")
    
    try:
        # 방법 1: 기본 calendars() 메서드 사용 시도
        try:
            calendars = principal.calendars()
            logger.info("calendars() 메서드를 사용하여 캘린더 목록을 가져왔습니다.")
        except Exception as e1:
            logger.warning(f"calendars() 메서드 실패: {str(e1)}")
            
            # 방법 2: calendar_home_set 속성 사용 시도
            try:
                calendar_home = principal.calendar_home_set[0]
                calendars = calendar_home.calendars()
                logger.info("calendar_home_set을 사용하여 캘린더 목록을 가져왔습니다.")
            except (IndexError, AttributeError, TypeError) as e2:
                logger.warning(f"calendar_home_set 방법 실패: {str(e2)}")
                
                # 방법 3: 직접 캘린더 URL 구성 시도
                try:
                    username = caldav_client.username
                    if isinstance(username, bytes):
                        username = username.decode('utf-8')
                    
                    # LINE Works CalDAV 서버의 캘린더 URL 패턴 사용
                    calendar_home_url = f"{caldav_client.url.rstrip('/')}/calendars/{username}/"
                    calendar_home = caldav_client.calendar(url=calendar_home_url)
                    calendars = [calendar_home]  # 캘린더 홈을 첫 번째 캘린더로 간주
                    logger.info(f"직접 URL 구성을 사용하여 캘린더 목록을 가져왔습니다: {calendar_home_url}")
                except Exception as e3:
                    logger.error(f"직접 URL 구성 방법도 실패: {str(e3)}")
                    # 모든 방법 실패 시 빈 목록 반환
                    calendars = []
        
        calendar_list = []
        for calendar in calendars:
            try:
                name = getattr(calendar, "name", "Unknown")
                # name이 None이거나 AttributeError 발생 시 URL에서 이름 추출 시도
                if name is None or name == "Unknown":
                    url_parts = calendar.url.rstrip('/').split('/')
                    name = url_parts[-1] if url_parts else "Unknown"
                
                calendar_list.append({
                    "id": calendar.url,
                    "name": name,
                    "description": getattr(calendar, "description", ""),
                    "color": getattr(calendar, "color", "")
                })
            except Exception as cal_err:
                logger.warning(f"캘린더 정보 처리 중 오류: {str(cal_err)}")
                # 최소한의 정보만 포함
                calendar_list.append({
                    "id": getattr(calendar, "url", "unknown"),
                    "name": "Unknown Calendar",
                    "description": "",
                    "color": ""
                })
        
        return {
            "calendars": calendar_list,
            "count": len(calendar_list),
            "status": "success",
            "message": f"{len(calendar_list)}개의 캘린더를 찾았습니다."
        }
    except Exception as e:
        logger.error(f"캘린더 목록 조회 오류: {str(e)}")
        raise ValueError(f"캘린더 목록 가져오기 실패: {str(e)}")

@mcp.tool(name="caldav_get_events_today")
def get_events_today() -> dict:
    from datetime import datetime, time
    if principal is None:
        raise ValueError("CalDAV 클라이언트가 설정되지 않았습니다. 먼저 connect_caldav를 호출하세요.")
    try:
        calendars = principal.calendars()
        if calendars:
            calendar = calendars[0]
            calendar_id = calendar.url
        else:
            logger.warning("No calendars found. Are you sure you have any calendars on the server?")
            return {"status": "success", "events": [], "message": "캘린더가 없습니다."}
    except Exception as e:
        logger.error(f"caldav_get_events_today: 캘린더 목록 조회 실패({str(e)})")
        return {"status": "error", "events": [], "message": f"캘린더 목록 조회 오류: {str(e)}"}
    today = datetime.now().date()
    time_min = datetime.combine(today, time.min).isoformat() + 'Z'
    time_max = datetime.combine(today, time.max).isoformat() + 'Z'
    try:
        events = get_events(calendar_id, time_min, time_max)
    except Exception as err:
        error_str = str(err).lower()
        if "propfinderror" in error_str or "notfounderror" in error_str:
            logger.warning("caldav_get_events_today: PropfindError or NotFoundError encountered, returning empty event list.")
            events = []
        else:
            logger.error(f"caldav_get_events_today: 이벤트 조회 중 오류: {str(err)}")
            return {"status": "error", "events": [], "message": f"오늘의 일정 조회 중 오류 발생: {str(err)}"}
    return {"status": "success", "events": events, "message": f"오늘의 일정 {len(events)}개를 조회했습니다."}

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

@mcp.prompt()
def list_calendars_prompt() -> str:
    """캘린더 목록 조회를 위한 프롬프트"""
    return """
    CalDAV 서버에 연결된 계정의 모든 캘린더 목록을 조회합니다.
    먼저 connect_caldav를 호출하여 서버에 연결해야 합니다.
    """


# 메인 실행 코드
@mcp.tool(name="caldav_get_events_past_week")
def get_events_past_week() -> dict:
    from datetime import datetime, timedelta
    if principal is None:
        raise ValueError("CalDAV 클라이언트가 설정되지 않았습니다. 먼저 connect_caldav를 호출하세요.")
    try:
        calendars = principal.calendars()
        if not calendars:
            return {"status": "success", "events": [], "message": "캘린더가 없습니다."}
        # 타임아웃 방지를 위해 하루 단위로 나누어 조회
        now = datetime.now()
        all_events = []
        for cal in calendars:
            cal_url = cal.url
            try:
                for i in range(7):
                    day_end = now - timedelta(days=i)
                    day_start = day_end - timedelta(days=1)
                    time_min = day_start.isoformat() + 'Z'
                    time_max = day_end.isoformat() + 'Z'
                    
                    for et in ["event","todo","journal"]:
                        events = get_events(cal_url, time_min, time_max, True, et)
                        for e in events:
                            e["calendar_url"] = cal_url
                            e["type"] = et
                        all_events.extend(events)
            except Exception as e:
                logger.warning(f"Failed to get events from {cal_url}: {str(e)}")
        return {
            "status": "success",
            "events": all_events,
            "message": f"최근 7일 이벤트 {len(all_events)}개를 조회했습니다."
        }
    except Exception as err:
        logger.error(f"get_events_past_week: 오류: {str(err)}")
        return {
            "status": "error",
            "events": [],
            "message": str(err)
        }

if __name__ == "__main__":
    logger.info("MCP-CalDAV 서버를 시작합니다.")
    
    mcp.run()
