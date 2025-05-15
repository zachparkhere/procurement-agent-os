import sys
import os
import asyncio

# === PATH SETUP ===
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # po_agent_os/
sys.path.append(BASE_DIR)
sys.path.append(os.path.join(BASE_DIR, "external_communication"))
sys.path.append(os.path.join(BASE_DIR, "Vendor_email_logger_agent"))

# === IMPORTS ===
from agents.po_agent import handle_po_message
from agents.followup_agent import handle_followup_message
from agents.vendor_reply_agent import handle_vendor_reply_message
from agents.draft_sender_agent import handle_draft_send_message
from mcp_service import receive_messages
from config import supabase

# === MCP AGENT ID ===
AGENT_ID = "external_comm_hub"

# === POLL NEW POs (status = 'issued', human_confirmed = True, submitted_at is null) ===
async def poll_new_pos():
    while True:
        try:
            result = supabase.table("purchase_orders").select("po_number", "submitted_at") \
                .eq("update_status", "issued") \
                .eq("human_confirmed", True) \
                .is_("submitted_at", "null") \
                .execute()

            if result.data:
                print(f"[🔔 POLL: PO] {len(result.data)} new POs found")
                for po in result.data:
                    await handle_po_message({"po_number": po["po_number"]})
        except Exception as e:
            print(f"[❌ poll_new_pos ERROR] {e}")
        await asyncio.sleep(10)

# === POLL VENDOR EMAILS (latest inbound by thread_id, unprocessed only) ===
async def poll_vendor_emails():
    while True:
        try:
            print("[📬 POLL: Vendor Email] Checking latest inbound vendor replies...")
            await handle_vendor_reply_message({})
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
            messages = receive_messages(AGENT_ID)
            for msg in messages:
                msg_type = msg["type"]
                payload = msg["payload"]
                if msg_type == "new_po":
                    await handle_po_message(payload)
                elif msg_type == "follow_up_check":
                    await handle_followup_message(payload)
                elif msg_type == "vendor_reply":
                    await handle_vendor_reply_message(payload)
                elif msg_type == "send_draft_email":
                    await handle_draft_send_message(payload)
                else:
                    print(f"[⚠️ Unknown Type] {msg_type}")
        except Exception as e:
            print(f"[❌ MCP Dispatch Error] {e}")
        await asyncio.sleep(5)

# === MAIN EVENT LOOP ===
if __name__ == "__main__":
    async def main():
        await asyncio.gather(
            mcp_dispatch_loop(),
            poll_new_pos(),
            poll_vendor_emails(),
            poll_followups()
        )
    asyncio.run(main())
