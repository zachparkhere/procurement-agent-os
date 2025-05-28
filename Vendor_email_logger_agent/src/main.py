from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from gmail.watcher_manager import watcher_manager
from gmail.gmail_auth import get_gmail_service
from services.vendor_manager import VendorManager
import logging

logger = logging.getLogger(__name__)

app = FastAPI()

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    """
    서버 시작 시 실행되는 이벤트
    """
    logger.info("🚀 Starting Vendor Email Logger Agent...")
    # 여기서 필요한 초기화 작업 수행

@app.on_event("shutdown")
async def shutdown_event():
    """
    서버 종료 시 실행되는 이벤트
    """
    logger.info("🛑 Shutting down Vendor Email Logger Agent...")
    # 여기서 필요한 정리 작업 수행

@app.get("/auth/google")
async def google_auth(user_id: str):
    """
    Google 인증 URL 생성
    """
    try:
        auth_url = get_gmail_service(user_id)
        return {"auth_url": auth_url}
    except Exception as e:
        logger.error(f"Google auth error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/watch/{user_email}")
async def start_watching(user_email: str):
    """
    특정 사용자의 이메일 감시 시작
    """
    try:
        # Gmail 서비스 가져오기
        service = get_gmail_service(user_email)
        if not service:
            raise HTTPException(status_code=400, detail="Gmail service not initialized")

        # VendorManager 생성
        vendor_manager = VendorManager()

        # DB에서 사용자의 timezone 가져오기
        from po_agent_os.supabase_client_anon import supabase
        user_data = supabase.table("users").select("timezone").eq("email", user_email).single().execute()
        timezone = user_data.data.get("timezone", "UTC") if user_data.data else "UTC"

        # WatcherManager에 Watcher 추가
        watcher_manager.add_watcher(user_email, service, vendor_manager, timezone)
        
        return {"status": "success", "message": f"Started watching emails for {user_email}"}
    except Exception as e:
        logger.error(f"Error starting watch for {user_email}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/watch/{user_email}")
async def stop_watching(user_email: str):
    """
    특정 사용자의 이메일 감시 중지
    """
    try:
        watcher_manager.remove_watcher(user_email)
        return {"status": "success", "message": f"Stopped watching emails for {user_email}"}
    except Exception as e:
        logger.error(f"Error stopping watch for {user_email}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/watch/{user_email}/timezone")
async def update_timezone(user_email: str, new_timezone: str):
    """
    특정 사용자의 timezone 업데이트
    """
    try:
        watcher_manager.update_timezone(user_email, new_timezone)
        return {"status": "success", "message": f"Updated timezone for {user_email}"}
    except Exception as e:
        logger.error(f"Error updating timezone for {user_email}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 