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

1. 환경 변수 설정:
```bash
# 템플릿 파일 복사
cp .env.example .env
cp credentials.template credentials.json

# .env 파일 수정
# 필요한 값들을 실제 값으로 교체:
# - SUPABASE_URL
# - SUPABASE_ANON_KEY
# - OPENAI_API_KEY
# - 기타 설정값들
```

2. Gmail API 설정:
- Google Cloud Console에서 프로젝트 생성
- Gmail API 활성화
- OAuth 2.0 클라이언트 ID 생성
- 다운로드한 인증 정보를 `credentials.json`에 입력

3. 실행:
```bash
# 가상환경 활성화
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt

# 실행
python -m vector_store.main  # 벡터 스토어 서비스
python -m Vendor_email_logger_agent.main  # 벤더 이메일 로거
```

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