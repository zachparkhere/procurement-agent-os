from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
import json, os, uuid

from po_agent_os.supabase_client import supabase

router = APIRouter()

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CREDENTIALS_PATH = os.path.join(BASE_DIR, 'credentials.json')
REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/callback/google")
SCOPES = ["https://mail.google.com/", "https://www.googleapis.com/auth/userinfo.email", "openid"]

@router.get("/google")
def start_google_oauth(user_id: str = None):
    print(f"🔑 [OAuth] Start Google login for user_id: {user_id}")
    print(f"🔑 [OAuth] Using credentials file at: {CREDENTIALS_PATH}")
    flow = Flow.from_client_secrets_file(
        CREDENTIALS_PATH,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )
    auth_url, _ = flow.authorization_url(
        prompt="consent",
        access_type="offline",
        include_granted_scopes="true",
        state=user_id or str(uuid.uuid4())  # 임시 상태
    )
    return {"auth_url": auth_url}

@router.get("/callback/google")
def google_callback(request: Request):
    try:
        code = request.query_params.get("code")
        incoming_state = request.query_params.get("state")

        print(f"📥 [OAuth Callback] Received code with state: {incoming_state}")

        flow = Flow.from_client_secrets_file(
            CREDENTIALS_PATH,
            scopes=SCOPES,
            redirect_uri=REDIRECT_URI
        )
        flow.fetch_token(
            code=code,
            client_id=flow.client_config["client_id"],
            client_secret=flow.client_config["client_secret"]
        )

        creds = flow.credentials
        token_info = id_token.verify_oauth2_token(creds.id_token, google_requests.Request())
        user_email = token_info.get("email")

        print("✅ 인증 성공:", user_email)

        # ✅ Supabase에서 이메일로 유저 조회
        existing = supabase.table("users").select("*").eq("email", user_email).execute()

        if existing.data:
            user_id = existing.data[0]["id"]
            print(f"🔄 Supabase 유저 존재함: {user_id}")
        else:
            # ✅ 없으면 새 유저 생성
            user_id = str(uuid.uuid4())
            insert_result = supabase.table("users").insert({
                "id": user_id,
                "email": user_email,
                "name": token_info.get("name", "Unknown"),
                "role": "user"
            }).execute()
            print(f"🆕 Supabase 유저 생성됨: {user_id} →", insert_result)

        # ✅ 이메일 관련 정보 업데이트
        supabase.table("users").update({
            "email_provider": "gmail",
            "email_address": user_email,
            "email_access_token": creds.token,
            "email_refresh_token": creds.refresh_token,
            "email_token_expiry": creds.expiry.isoformat(),
            "email_token_json": json.loads(creds.to_json())
        }).eq("id", user_id).execute()

        return RedirectResponse("https://app.shiftsai.com/Login?linked=success")

    except Exception as e:
        print(f"❌ Google OAuth Callback Error: {e}")
        return {"error": str(e)}
