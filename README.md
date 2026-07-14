# youth-policy-mcp

온통청년 청년정책 API 기반 FastMCP HTTP 서버입니다.

MCP endpoint:

```text
/mcp
```

## 핵심 환경변수

실제 API 키를 Git이나 Dockerfile에 넣지 말고, 로컬에서는 `.env`, 배포 환경에서는 Secret/Environment Variable로 주입합니다.

```bash
OPEN_API_KEY=발급받은_키
YOUTH_CENTER_API_URL=https://www.youthcenter.go.kr/go/ythip/getPlcy
```

인식 가능한 키 이름은 다음과 같습니다.

- `OPEN_API_KEY` (권장)
- `YOUTH_CENTER_API_KEY`
- `YOUTHCENTER_API_KEY`
- `YOUTHCENTER_API_KEY_POLICY`

신규 API는 자동으로 `apiKeyNm`, `pageNum`, `pageSize`, `rtnType=json` 형식으로 요청합니다.
구형 OPEN API를 사용해야 할 경우 URL만 아래와 같이 바꾸면 자동으로 `openApiVlak`, `pageIndex`, `display` 형식으로 요청합니다.

```bash
YOUTH_CENTER_API_URL=https://www.youthcenter.go.kr/opi/youthPlcyList.do
```

## 로컬 실행

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m src
```

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python -m src
```

## Docker

`.dockerignore`에 `.env`가 들어 있으므로 `.env`는 이미지 안으로 복사되지 않습니다. 실행 시 외부에서 주입해야 합니다.

```bash
docker build -t youth-policy-mcp .
docker run --env-file .env -p 8000:8000 youth-policy-mcp
```

배포 플랫폼에서는 다음 두 값을 Secret/Environment Variable로 등록합니다.

```text
OPEN_API_KEY=<실제 키>
YOUTH_CENTER_API_URL=https://www.youthcenter.go.kr/go/ythip/getPlcy
```

컨테이너 포트는 `8000`, MCP 경로는 `/mcp`입니다.

## 오류 확인

수정 버전은 HTTP 상태 코드뿐 아니라 호출 URL, 응답 본문 일부, non-JSON 응답의 content-type을 오류 메시지에 포함합니다. API 키 값 자체는 오류에 노출하지 않습니다.
