# MCP-CalDAV Connector

Model Context Protocol (MCP)와 CalDAV 서버를 연동하는 Python 기반 커넥터입니다.

## 개요

이 프로젝트는 Anthropic의 Model Context Protocol(MCP)을 사용하여 CalDAV 서버와 연동할 수 있는 인터페이스를 제공합니다. MCP를 통해 AI 모델이 캘린더 데이터에 접근하고 관리할 수 있습니다.

## 기능

- CalDAV 서버 연결 및 인증
- 캘린더 목록 조회
- 이벤트 조회, 생성, 업데이트, 삭제
- FastAPI 기반 웹 API 인터페이스 제공

## 설치 방법

### 의존성 설치

```bash
pip install mcp caldav fastapi uvicorn
```

또는 uv를 사용하는 경우:

```bash
uv add "mcp[cli]" caldav fastapi uvicorn
```

### 클론 및 설치

```bash
git clone https://github.com/yourusername/mcp-caldav-connector.git
cd mcp-caldav-connector
pip install -e .
```

## 사용 방법

### MCP 서버 실행

```bash
python -m src.caldav_mcp
```

### API 엔드포인트

- **CalDAV 연결**: `POST /api/caldav/connect`
- **캘린더 목록 조회**: `GET /api/caldav/calendars`
- **이벤트 조회**: `GET /api/caldav/events`
- **이벤트 생성**: `POST /api/caldav/events`
- **이벤트 업데이트**: `PUT /api/caldav/events/{event_id}`
- **이벤트 삭제**: `DELETE /api/caldav/events/{event_id}`

## 개발

### 모듈 구조

- `src/caldav_mcp.py`: 메인 MCP 서버 및 CalDAV 연동 로직
- `src/resources/`: MCP 리소스 모듈
- `src/tools/`: MCP 도구 모듈

## 기여하기

1. 저장소를 포크합니다
2. 새 브랜치를 생성합니다 (`git checkout -b feature/amazing-feature`)
3. 변경사항을 커밋합니다 (`git commit -m 'Add some amazing feature'`)
4. 브랜치에 푸시합니다 (`git push origin feature/amazing-feature`)
5. Pull Request를 작성합니다

## 라이센스

이 프로젝트는 MIT 라이센스 하에 배포됩니다. 자세한 내용은 [LICENSE](LICENSE) 파일을 참조하세요.
