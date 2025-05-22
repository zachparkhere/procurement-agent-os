from external_communication.follow_up_vendor_email import send_follow_up_emails

def mcp_dispatch_loop():
    while True:
        try:
            # ... existing code ...
            
            # ETA follow-up 처리
            print("\n[🔄 ETA FOLLOW-UP] Processing ETA follow-ups...")
            send_follow_up_emails()
            
            # ... existing code ...
        except Exception as e:
            print(f"Error in mcp_dispatch_loop: {e}")
            time.sleep(5)  # Wait before retrying 