import logging
from typing import Dict
from .gmail_watcher import GmailWatcher

logger = logging.getLogger(__name__)

class GmailWatcherManager:
    def __init__(self):
        self.watchers: Dict[str, GmailWatcher] = {}  # user_email -> GmailWatcher 매핑
        
    def add_watcher(self, user_email: str, service, vendor_manager, timezone='UTC'):
        """
        새로운 사용자의 Watcher 추가
        """
        if user_email not in self.watchers:
            self.watchers[user_email] = GmailWatcher(service, vendor_manager, timezone)
            logger.info(f"[Manager] 새로운 Watcher 추가: {user_email}")
            
    def remove_watcher(self, user_email: str):
        """
        사용자의 Watcher 제거
        """
        if user_email in self.watchers:
            del self.watchers[user_email]
            logger.info(f"[Manager] Watcher 제거: {user_email}")
            
    def get_watcher(self, user_email: str) -> GmailWatcher:
        """
        사용자의 Watcher 가져오기
        """
        return self.watchers.get(user_email)
        
    def update_watcher_timezone(self, user_email: str, new_timezone: str):
        """
        특정 사용자의 Watcher 시간대 업데이트
        """
        if user_email in self.watchers:
            self.watchers[user_email].update_timezone(new_timezone)
            logger.info(f"[Manager] 사용자 {user_email}의 시간대 업데이트: {new_timezone}")
        else:
            logger.warning(f"[Manager] 사용자 {user_email}의 Watcher를 찾을 수 없음")
        
    def check_all_emails(self):
        """
        모든 Watcher의 이메일 확인
        """
        for user_email, watcher in self.watchers.items():
            try:
                new_emails = watcher.get_new_emails()
                if new_emails:
                    logger.info(f"[Manager] 사용자 {user_email}의 새 이메일 {len(new_emails)}건 발견")
            except Exception as e:
                logger.error(f"[Manager] 사용자 {user_email}의 이메일 확인 중 에러: {e}")

# 전역 WatcherManager 인스턴스
watcher_manager = GmailWatcherManager() 