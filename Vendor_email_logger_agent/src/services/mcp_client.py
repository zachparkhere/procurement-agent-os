# mcp/mcp_client.py
import requests
from typing import Dict

MCP_URL = "http://localhost:8000"

def send_to_mcp(message: Dict):
    """
    Send a message to the MCP server
    """
    try:
        response = requests.post(f"{MCP_URL}/send", json=message)
        print(f"📨 Sent to MCP: {response.status_code}")
        if response.status_code != 200:
            print(f"❌ Error sending to MCP: {response.text}")
    except Exception as e:
        print(f"❌ MCP transmission error: {e}")

def receive_from_mcp(agent_id: str) -> Dict:
    """
    Receive messages from the MCP server
    """
    try:
        response = requests.get(f"{MCP_URL}/receive/{agent_id}")
        if response.status_code == 200:
            return response.json()
        else:
            print(f"❌ Error receiving from MCP: {response.text}")
            return {"messages": []}
    except Exception as e:
        print(f"❌ MCP reception error: {e}")
        return {"messages": []}
