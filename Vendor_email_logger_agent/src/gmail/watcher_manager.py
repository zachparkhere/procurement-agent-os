import logging
from typing import Dict
from .gmail_watcher import GmailWatcher
import threading
import time
from datetime import datetime
from pytz import timezone

logger = logging.getLogger(__name__)

class GmailWatcherManager:
    def __init__(self):
        self.watchers: Dict[str, GmailWatcher] = {}  # user_email -> GmailWatcher 매핑
        self.watcher_threads: Dict[str, threading.Thread] = {}  # user_email -> Thread 매핑
        self.stop_flags: Dict[str, bool] = {}  # user_email -> stop flag 매핑
        
    def add_watcher(self, user_email: str, service, vendor_manager, timezone='UTC'):
        """Add a new watcher for a user"""
        logger.info(f"[WatcherManager] 사용자 {user_email}의 Watcher 추가 시작")
        if user_email not in self.watchers:
            self.watchers[user_email] = GmailWatcher(service, vendor_manager, user_email, timezone)
            self.stop_flags[user_email] = False
            self.watcher_threads[user_email] = threading.Thread(
                target=self._watch_emails,
                args=(user_email,)
            )
            self.watcher_threads[user_email].start()
            logger.info(f"[WatcherManager] 사용자 {user_email}의 Watcher 스레드 시작됨")
            
    def _watch_emails(self, user_email: str):
        """Watch emails for a user"""
        logger.info(f"[WatcherManager] 사용자 {user_email}의 이메일 감시 시작")
        watcher = self.watchers.get(user_email)
        if not watcher:
            logger.error(f"[WatcherManager] 사용자 {user_email}의 Watcher를 찾을 수 없음")
            return
        
        while not self.stop_flags.get(user_email, True):
            try:
                new_emails = watcher.get_new_emails()
                if new_emails:
                    logger.info(f"[WatcherManager] 사용자 {user_email}의 새 이메일 {len(new_emails)}건 처리")
            except Exception as e:
                logger.error(f"[WatcherManager] 사용자 {user_email}의 이메일 감시 중 오류 발생: {e}")
            time.sleep(5)
            
    def remove_watcher(self, user_email: str):
        """Remove a watcher for a user"""
        logger.info(f"[WatcherManager] 사용자 {user_email}의 Watcher 제거 시작")
        if user_email in self.watchers:
            self.stop_flags[user_email] = True
            if user_email in self.watcher_threads:
                self.watcher_threads[user_email].join()
                logger.info(f"[WatcherManager] 사용자 {user_email}의 Watcher 스레드 종료됨")
            del self.watchers[user_email]
            del self.watcher_threads[user_email]
            del self.stop_flags[user_email]
            
    def get_watcher(self, user_email: str) -> GmailWatcher:
        """Get a watcher for a user"""
        return self.watchers.get(user_email)
        
    def update_timezone(self, user_email: str, new_timezone: str):
        """Update timezone for a user's watcher"""
        logger.info(f"[WatcherManager] 사용자 {user_email}의 timezone 업데이트 시작: {new_timezone}")
        if user_email in self.watchers:
            # 기존 스레드 정지
            self.stop_flags[user_email] = True
            if user_email in self.watcher_threads:
                self.watcher_threads[user_email].join()
                logger.info(f"[WatcherManager] 사용자 {user_email}의 기존 Watcher 스레드 종료됨")
            
            # 새로운 timezone으로 Watcher 업데이트
            watcher = self.watchers[user_email]
            watcher.update_timezone(new_timezone)
            logger.info(f"[WatcherManager] 사용자 {user_email}의 Watcher timezone 업데이트됨: {new_timezone}")
            
            # 새로운 스레드 시작
            self.stop_flags[user_email] = False
            self.watcher_threads[user_email] = threading.Thread(
                target=self._watch_emails,
                args=(user_email,)
            )
            self.watcher_threads[user_email].start()
            logger.info(f"[WatcherManager] 사용자 {user_email}의 새로운 Watcher 스레드 시작됨")

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