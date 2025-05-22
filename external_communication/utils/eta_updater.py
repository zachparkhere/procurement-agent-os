import os
import sys
from datetime import datetime
from typing import Optional, Dict, List
from dotenv import load_dotenv
from supabase import create_client

# Load environment variables
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

def validate_eta(eta_str: str) -> Optional[str]:
    """
    ETA 문자열의 유효성을 검증하고 표준 형식으로 변환합니다.
    
    Args:
        eta_str: 검증할 ETA 문자열
        
    Returns:
        유효한 경우 'YYYY-MM-DD' 형식의 문자열, 그렇지 않은 경우 None
    """
    try:
        # 다양한 날짜 형식 처리
        date_formats = [
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%m/%d/%Y",
            "%d-%m-%Y",
            "%m-%d-%Y",
            "%Y/%m/%d"
        ]
        
        for fmt in date_formats:
            try:
                date_obj = datetime.strptime(eta_str, fmt)
                return date_obj.strftime("%Y-%m-%d")
            except ValueError:
                continue
                
        return None
    except Exception as e:
        print(f"❌ ETA validation error: {e}")
        return None

def get_latest_eta_from_email_logs(po_number: str) -> Optional[dict]:
    """
    email_logs에서 특정 PO의 가장 최근 parsed_delivery_date 정보를 가져옵니다.
    Args:
        po_number: PO 번호
    Returns:
        ETA 정보가 포함된 딕셔너리 또는 None
    """
    try:
        # parsed_delivery_date가 null이 아닌 것 중 created_at 기준 최신 1개
        response = supabase.table("email_logs") \
            .select("id, parsed_delivery_date, created_at, thread_id") \
            .eq("po_number", po_number) \
            .not_.is_("parsed_delivery_date", "null") \
            .order("created_at", desc=True) \
            .limit(1) \
            .execute()
        if not response.data:
            return None
        email = response.data[0]
        eta = email.get("parsed_delivery_date")
        if eta:
            return {
                "eta": eta,
                "email_log_id": email["id"],
                "thread_id": email["thread_id"],
                "created_at": email["created_at"]
            }
        return None
    except Exception as e:
        print(f"❌ Error fetching ETA from email logs: {e}")
        return None

def update_po_eta(po_number: str, eta_info: Dict) -> bool:
    """
    purchase_orders 테이블의 ETA 정보를 업데이트합니다.
    
    Args:
        po_number: PO 번호
        eta_info: ETA 정보가 포함된 딕셔너리
        
    Returns:
        업데이트 성공 여부
    """
    try:
        # 현재 PO의 ETA 정보 확인
        po_response = supabase.table("purchase_orders") \
            .select("eta, updated_at") \
            .eq("po_number", po_number) \
            .execute()
            
        if not po_response.data:
            print(f"⚠️ PO {po_number} not found")
            return False
            
        current_po = po_response.data[0]
        current_eta = current_po.get("eta")
        current_updated_at = current_po.get("updated_at")
        
        # ETA가 이미 있고, 새로운 ETA가 더 최근인 경우에만 업데이트
        if current_eta and current_updated_at:
            current_updated_at = datetime.fromisoformat(current_updated_at.replace('Z', '+00:00'))
            new_updated_at = datetime.fromisoformat(eta_info["created_at"].replace('Z', '+00:00'))
            
            if new_updated_at <= current_updated_at:
                print(f"ℹ️ Skipping ETA update for PO {po_number} - current ETA is more recent")
                return True
        
        # ETA 업데이트
        update_data = {
            "eta": eta_info["eta"],
            "updated_at": eta_info["created_at"],
            "eta_reference": eta_info["email_log_id"]  # email_log_id를 eta_reference에 저장
        }
        
        result = supabase.table("purchase_orders") \
            .update(update_data) \
            .eq("po_number", po_number) \
            .execute()
            
        if result.data:
            print(f"✅ Updated ETA for PO {po_number}: {eta_info['eta']} (from email_log_id: {eta_info['email_log_id']})")
            return True
        else:
            print(f"❌ Failed to update ETA for PO {po_number}")
            return False
            
    except Exception as e:
        print(f"❌ Error updating PO ETA: {e}")
        return False

def process_eta_updates():
    """
    모든 PO에 대해 ETA 업데이트를 처리합니다.
    """
    try:
        # ETA가 없는 PO들을 가져옴
        response = supabase.table("purchase_orders") \
            .select("po_number") \
            .is_("eta", "null") \
            .execute()
            
        if not response.data:
            print("ℹ️ No POs found without ETA")
            return
            
        print(f"🔍 Found {len(response.data)} POs without ETA")
        
        for po in response.data:
            po_number = po["po_number"]
            eta_info = get_latest_eta_from_email_logs(po_number)
            
            if eta_info:
                update_po_eta(po_number, eta_info)
            else:
                print(f"ℹ️ No ETA found in email logs for PO {po_number}")
                
    except Exception as e:
        print(f"❌ Error processing ETA updates: {e}")

if __name__ == "__main__":
    process_eta_updates() 