import logging
from typing import Dict
from .gmail_watcher import GmailWatcher
import threading
import time

logger = logging.getLogger(__name__)

class GmailWatcherManager:
    def __init__(self):
        self.watchers: Dict[str, GmailWatcher] = {}  # user_email -> GmailWatcher 매핑
        self.watcher_threads: Dict[str, threading.Thread] = {}  # user_email -> Thread 매핑
        self.stop_flags: Dict[str, bool] = {}  # user_email -> stop flag 매핑
        
    def add_watcher(self, user_email: str, service, vendor_manager, timezone='UTC'):
        """
        새로운 사용자의 Watcher 추가
        """
        if user_email not in self.watchers:
            self.watchers[user_email] = GmailWatcher(service, vendor_manager, timezone)
            self.stop_flags[user_email] = False
            
            # Watcher 스레드 시작
            thread = threading.Thread(
                target=self._watch_emails,
                args=(user_email,)
            )
            thread.daemon = True
            thread.start()
            self.watcher_threads[user_email] = thread
            
            logger.info(f"[Manager] 새로운 Watcher 추가: {user_email}")
            
    def _watch_emails(self, user_email: str):
        """
        특정 사용자의 이메일을 감시하는 스레드 함수
        """
        watcher = self.watchers.get(user_email)
        if not watcher:
            return
            
        logger.info(f"[Manager] 사용자 {user_email}의 이메일 감시 시작")
        while not self.stop_flags.get(user_email, True):
            try:
                new_emails = watcher.get_new_emails()
                if new_emails:
                    logger.info(f"[Manager] 사용자 {user_email}의 새 이메일 {len(new_emails)}건 발견")
            except Exception as e:
                logger.error(f"[Manager] 사용자 {user_email}의 이메일 확인 중 에러: {e}")
            time.sleep(60)  # 1분마다 체크
            
    def remove_watcher(self, user_email: str):
        """
        사용자의 Watcher 제거
        """
        if user_email in self.watchers:
            # 스레드 정지
            self.stop_flags[user_email] = True
            if user_email in self.watcher_threads:
                thread = self.watcher_threads[user_email]
                thread.join(timeout=5)  # 스레드가 종료될 때까지 최대 5초 대기
                del self.watcher_threads[user_email]
            
            del self.watchers[user_email]
            del self.stop_flags[user_email]
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
            # 기존 Watcher의 service와 vendor_manager 저장
            old_watcher = self.watchers[user_email]
            service = old_watcher.service
            vendor_manager = old_watcher.vendor_manager
            
            # 기존 Watcher 제거 (스레드도 함께 정지)
            self.remove_watcher(user_email)
            
            # 새로운 timezone으로 Watcher 재생성
            self.watchers[user_email] = GmailWatcher(service, vendor_manager, new_timezone)
            self.stop_flags[user_email] = False
            
            # 새로운 Watcher로 스레드 재시작
            thread = threading.Thread(
                target=self._watch_emails,
                args=(user_email,)
            )
            thread.daemon = True
            thread.start()
            self.watcher_threads[user_email] = thread
            
            logger.info(f"[Manager] 사용자 {user_email}의 Watcher 재시작 (새 시간대: {new_timezone})")
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