# Procurement Agent OS

자동화된 구매 발주 관리 시스템

## 설치 방법

1. 저장소 클론:
```bash
git clone https://github.com/zachparkhere/procurement-agent-os.git
cd procurement-agent-os
```

2. 가상환경 생성 및 활성화:
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# 또는
.venv\Scripts\activate  # Windows
```

3. 의존성 패키지 설치:
```bash
pip install -r requirements.txt
```

## 주요 기능

- 벤더 이메일 모니터링 및 처리
- PO 자동 생성 및 관리
- 이메일 드래프트 자동 생성
- 실시간 이벤트 기반 처리

## 프로젝트 구조

```
procurement-agent-os/
├── external_communication/  # 외부 통신 관리
├── Vendor_email_logger_agent/  # 벤더 이메일 처리
├── mcp_server/  # 메시지 통신 프로토콜 서버
└── requirements.txt  # 프로젝트 의존성
```

## 환경 설정

1. `.env` 파일 생성:
```
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
MCP_SERVER_URL=http://localhost:8000
```

2. Gmail API 자격 증명 설정:
- `credentials.json`을 `Vendor_email_logger_agent/credentials/` 디렉토리에 배치

## 실행 방법

1. MCP 서버 실행:
```bash
python mcp_server/main.py
```

2. 이메일 로거 에이전트 실행:
```bash
python Vendor_email_logger_agent/main.py
```

3. 외부 통신 관리자 실행:
```bash
python external_communication/main.py monitor
``` 