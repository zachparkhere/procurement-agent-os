import logging
from typing import Dict
from .gmail_watcher import GmailWatcher
import asyncio
from datetime import datetime
from pytz import timezone

logger = logging.getLogger(__name__)

class GmailWatcherManager:
    def __init__(self):
        self.watchers: Dict[str, GmailWatcher] = {}  # user_email -> GmailWatcher 매핑
        self.watcher_tasks: Dict[str, asyncio.Task] = {}  # user_email -> asyncio Task 매핑
        self.stop_flags: Dict[str, bool] = {}  # user_email -> stop flag 매핑
        self.watcher_args: Dict[str, dict] = {}  # user_email -> watcher 인자 dict

    async def add_watcher(self, user_email: str, service, vendor_manager, timezone_str='UTC', email_processor=None, mcp_service=None, user_id=None, process_callback=None):
        """Add a new watcher for a user (asyncio 기반)"""
        logger.info(f"[WatcherManager] 사용자 {user_email}의 Watcher 추가 시작")
        if user_email not in self.watchers:
            watcher = GmailWatcher(
                service, vendor_manager, user_email, timezone_str,
                email_processor=email_processor,
                mcp_service=mcp_service,
                user_id=user_id,
                process_callback=process_callback
            )
            self.watchers[user_email] = watcher
            self.stop_flags[user_email] = False
            self.watcher_tasks[user_email] = asyncio.create_task(watcher.run())
            # 인자 저장
            self.watcher_args[user_email] = {
                'service': service,
                'vendor_manager': vendor_manager,
                'timezone_str': timezone_str,
                'email_processor': email_processor,
                'mcp_service': mcp_service,
                'user_id': user_id,
                'process_callback': process_callback
            }
            logger.info(f"[WatcherManager] 사용자 {user_email}의 Watcher Task 시작됨")

    async def remove_watcher(self, user_email: str):
        """Remove a watcher for a user (asyncio 기반)"""
        logger.info(f"[WatcherManager] 사용자 {user_email}의 Watcher 제거 시작")
        if user_email in self.watchers:
            self.stop_flags[user_email] = True
            task = self.watcher_tasks.get(user_email)
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            del self.watchers[user_email]
            del self.watcher_tasks[user_email]
            del self.stop_flags[user_email]
            if user_email in self.watcher_args:
                del self.watcher_args[user_email]

    def get_watcher(self, user_email: str) -> GmailWatcher:
        """Get a watcher for a user"""
        return self.watchers.get(user_email)

    async def update_timezone(self, user_email: str, new_timezone: str):
        """Update timezone for a user's watcher (asyncio 기반)"""
        logger.info(f"[WatcherManager] 사용자 {user_email}의 timezone 업데이트 시작: {new_timezone}")
        if user_email in self.watchers:
            # 기존 Task 정지
            await self.remove_watcher(user_email)
            # 저장된 인자 꺼내서 새로 watcher 생성
            args = self.watcher_args.get(user_email)
            if args:
                args = args.copy()  # 원본 보호
                args['timezone_str'] = new_timezone  # 타임존만 새 값으로
                await self.add_watcher(user_email, **args)
                logger.info(f"[WatcherManager] 사용자 {user_email}의 새로운 Watcher Task 시작됨 (timezone 변경)")
            else:
                logger.error(f"[WatcherManager] {user_email}의 watcher 인자 정보가 없습니다.")

    async def check_all_emails(self):
        """
        모든 Watcher의 이메일 확인 (asyncio 기반)
        """
        for user_email, watcher in self.watchers.items():
            try:
                await watcher.poll_emails()
            except Exception as e:
                logger.error(f"[Manager] 사용자 {user_email}의 이메일 확인 중 에러: {e}")

# 전역 WatcherManager 인스턴스
watcher_manager = GmailWatcherManager() 