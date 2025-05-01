import os
import json
import logging
import aiohttp
from datetime import datetime
from typing import Dict, Any

logger = logging.getLogger(__name__)

class MCPService:
    def __init__(self):
        self.base_url = os.getenv('MCP_SERVER_URL', 'http://localhost:8000')
        self.session = None

    async def ensure_session(self):
        """세션이 없으면 생성"""
        if self.session is None:
            self.session = aiohttp.ClientSession()

    async def close(self):
        """세션 종료"""
        if self.session:
            await self.session.close()
            self.session = None

    async def send_message(self, message_data: Dict[str, Any]) -> bool:
        """MCP 서버로 메시지 전송"""
        try:
            await self.ensure_session()
            
            # 메시지 데이터 준비
            payload = {
                "sender": "vendor_email_logger",
                "receiver": "external_comm_agent",
                "content": message_data.get("body_text", ""),
                "type": "vendor_email",
                "payload": {
                    "email_data": message_data,
                    "vendor_id": "",  # TODO: Implement vendor mapping
                    "status": "unread"
                }
            }

            # MCP 서버로 전송
            async with self.session.post(
                f"{self.base_url}/send",  # /api/messages 대신 /send 사용
                json=payload,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 200:
                    logger.info(f"Message sent to MCP server: {message_data.get('subject')}")
                    return True
                else:
                    logger.error(f"Failed to send message to MCP server: {response.status}")
                    return False

        except Exception as e:
            logger.error(f"Error sending message to MCP server: {e}")
            return False

    async def get_message_status(self, message_id: str) -> Dict[str, Any]:
        """메시지 상태 조회"""
        try:
            await self.ensure_session()
            
            async with self.session.get(f"{self.base_url}/status/{message_id}") as response:  # /api/messages 대신 /status 사용
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"Failed to get message status: {response.status}")
                    return None

        except Exception as e:
            logger.error(f"Error getting message status: {e}")
            return None 