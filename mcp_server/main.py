import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# ✅ 라우터 import는 꼭 이 위치에서!
from external_communication.oauth.auth_router import router as auth_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ 라우터 등록
print("✅ Registering /auth router")
app.include_router(auth_router, prefix="/auth")

@app.get("/")
def root():
    return {"status": "MCP server alive"}

@app.post("/receive/external_comm_hub")
async def receive_external_comm_hub(request: Request):
    data = await request.json()
    print("[MCP] Received data at /receive/external_comm_hub:", data)
    return {"status": "received", "data": data}

@app.get("/receive/external_comm_hub")
async def receive_external_comm_hub_get():
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run("mcp_server.main:app", host="127.0.0.1", port=8000, reload=True)
