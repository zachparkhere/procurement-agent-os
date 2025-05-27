import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import asyncio
import requests
from typing import Dict, List
import threading
from external_communication.utils.email_utils import send_approved_drafts

# === PATH SETUP ===
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # procurement_agent_os/
sys.path.append(BASE_DIR)
sys.path.append(os.path.join(BASE_DIR, "external_communication"))
sys.path.append(os.path.join(BASE_DIR, "Vendor_email_logger_agent"))

# === IMPORTS ===
from external_communication.agents.po_agent import handle_po_message
from external_communication.agents.followup_agent import handle_followup_message
from external_communication.agents.vendor_reply_agent import handle_vendor_reply_message
from external_communication.agents.draft_sender_agent import handle_draft_send_message
from external_communication.utils.eta_updater import process_eta_updates
from external_communication.utils.po_status_updater import analyze_po_status
from external_communication.config import supabase

# === MCP AGENT ID ===
AGENT_ID = "external_comm_hub"
MCP_URL = "http://localhost:8000"

def send_to_mcp(sender: str, receiver: str, msg_type: str, payload: dict):
    """MCP 서버로 메시지 전송"""
    try:
        response = requests.post(f"{MCP_URL}/send", json={
            "sender": sender,
            "receiver": receiver,
            "content": "",
            "type": msg_type,
            "payload": payload
        })
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"[❌ MCP transmission error] {e}")
        return None

def receive_from_mcp(agent_id: str) -> List[Dict]:
    """MCP 서버에서 메시지 수신"""
    try:
        response = requests.get(f"{MCP_URL}/receive/{agent_id}")
        response.raise_for_status()
        return response.json().get("messages", [])
    except Exception as e:
        print(f"[❌ MCP reception error] {e}")
        return []

# === POLL NEW POs (status = 'issued', human_confirmed = True, submitted_at is null) ===
async def poll_new_pos():
    while True:
        try:
            result = supabase.table("purchase_orders").select("po_number", "po_id", "submitted_at") \
                .eq("human_confirmed", True) \
                .is_("submitted_at", "null") \
                .execute()

            if result.data:
                print(f"[🔔 POLL: PO] {len(result.data)} new POs found")
                for po in result.data:
                    await handle_po_message({"po_number": po["po_number"], "po_id": po["po_id"]})
        except Exception as e:
            print(f"[❌ poll_new_pos ERROR] {e}")
        await asyncio.sleep(10)

# === POLL VENDOR EMAILS (latest inbound by thread_id, unprocessed only) ===
async def poll_vendor_emails():
    while True:
        try:
            print("[📬 POLL: Vendor Email] Checking latest inbound vendor replies...")
            await handle_vendor_reply_message({})
            # 벤더 이메일 처리 후 ETA 업데이트 실행
            print("[📅 ETA Update] Checking for ETA updates from new vendor emails...")
            process_eta_updates()
            # 벤더 이메일 처리 후 PO 상태 업데이트
            print("[🔄 PO Status] Updating PO statuses based on latest email...")
            for po in supabase.table("purchase_orders").select("po_number").execute().data:
                analyze_po_status(po["po_number"])
        except Exception as e:
            print(f"[❌ poll_vendor_emails ERROR] {e}")
        await asyncio.sleep(30)

# === POLL FOLLOW-UPS (check POs with ETA for 2-day reminders) ===
async def poll_followups():
    while True:
        try:
            print("[🔁 POLL: Follow-up] Triggering ETA reminder logic...")
            await handle_followup_message({})
        except Exception as e:
            print(f"[❌ poll_followups ERROR] {e}")
        await asyncio.sleep(3600)  # every 1 hour

# === MCP DISPATCH LOOP (fallback for push-based message trigger) ===
async def mcp_dispatch_loop():
    while True:
        try:
            messages = receive_from_mcp(AGENT_ID)
            for msg in messages:
                msg_type = msg["type"]
                payload = msg["payload"]
                if msg_type == "new_po":
                    await handle_po_message(payload)
                elif msg_type == "follow_up_check":
                    await handle_followup_message(payload)
                elif msg_type == "vendor_reply":
                    await handle_vendor_reply_message(payload)
                    # 벤더 회신 처리 후 ETA 업데이트 실행
                    print("[📅 ETA Update] Checking for ETA updates from new vendor reply...")
                    process_eta_updates()
                    # 벤더 회신 처리 후 PO 상태 업데이트
                    if "po_number" in payload:
                        print(f"[🔄 PO Status] Updating status for PO {payload['po_number']}...")
                        analyze_po_status(payload["po_number"])
                elif msg_type == "send_draft_email":
                    await handle_draft_send_message(payload)
                else:
                    print(f"[⚠️ Unknown Type] {msg_type}")
        except Exception as e:
            print(f"[❌ MCP Dispatch Error] {e}")
        await asyncio.sleep(5)

def start_send_approved_worker():
    def worker():
        print("[워커] send_approved_drafts 5초마다 실행 시작")
        while True:
            send_approved_drafts()
            import time; time.sleep(5)
    t = threading.Thread(target=worker, daemon=True)
    t.start()

# === MAIN EVENT LOOP ===
if __name__ == "__main__":
    start_send_approved_worker()
    async def main():
        await asyncio.gather(
            mcp_dispatch_loop(),
            poll_new_pos(),
            poll_vendor_emails(),
            poll_followups()
            # poll_eta_updates() 제거 - 더 이상 주기적 실행이 필요 없음
        )
    asyncio.run(main())
