import requests

MCP_BASE_URL = "http://localhost:8000"

def send_message(sender: str, receiver: str, msg_type: str, payload: dict):
    response = requests.post(f"{MCP_BASE_URL}/send", json={
        "sender": sender,
        "receiver": receiver,
        "content": "",
        "type": msg_type,
        "payload": payload
    })
    response.raise_for_status()
    return response.json()

def receive_messages(agent_id: str):
    response = requests.get(f"{MCP_BASE_URL}/receive/{agent_id}")
    response.raise_for_status()
    return response.json().get("messages", [])