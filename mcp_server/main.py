from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, List
from datetime import datetime
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI()

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

# 메시지 큐 (agent_id 기준)
message_queues: Dict[str, List[Dict]] = {}

class MCPMessage(BaseModel):
    sender: str
    receiver: str
    content: str
    type: str
    payload: dict

@app.post("/send")
def send_message(msg: MCPMessage):
    if msg.receiver not in message_queues:
        message_queues[msg.receiver] = []
    message_queues[msg.receiver].append({
        "sender": msg.sender,
        "type": msg.type,
        "payload": msg.payload,
        "timestamp": datetime.utcnow().isoformat()
    })
    return {"status": "message queued", "to": msg.receiver}

@app.get("/receive/{agent_id}")
def receive_messages(agent_id: str):
    messages = message_queues.get(agent_id, [])
    message_queues[agent_id] = []  # 메시지 수신 후 큐 비우기
    return {"messages": messages}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
