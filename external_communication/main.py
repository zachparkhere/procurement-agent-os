import argparse
import asyncio
from datetime import datetime
import os
import logging
from typing import Optional, Dict, List
from dotenv import load_dotenv
import json
from supabase import create_client, Client

from handle_general_vendor_email import handle_general_vendor_email
from follow_up_vendor_email import send_follow_up_emails
from email_draft_confirm import confirm_and_send_drafts

# Load environment variables
load_dotenv()

# Initialize Supabase client
supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('external_communication.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class MonitoringStats:
    def __init__(self):
        self.reset()
    
    def reset(self):
        self.vendor_emails_processed = 0
        self.drafts_created = 0
        self.drafts_sent = 0
        self.pos_sent = 0
        self.follow_ups_sent = 0
        self.errors = []
        
    def add_error(self, task: str, error: Exception):
        self.errors.append({
            'task': task,
            'error': str(error),
            'timestamp': datetime.now().isoformat()
        })

class EmailProcessor:
    def __init__(self):
        self.last_po_check = datetime.now()
        self.last_follow_up_check = datetime.now()
        self.stats = MonitoringStats()

    async def watch_new_pos(self):
        """
        새로운 PO 생성을 실시간으로 감지하고 처리
        """
        while True:
            try:
                current_time = datetime.now()
                
                # 새로 생성된 PO 확인
                response = supabase.table("purchase_orders") \
                    .select("*") \
                    .gt("created_at", self.last_po_check.isoformat()) \
                    .is_("submitted_at", "null") \
                    .execute()
                
                if response.data:
                    logger.info(f"새로운 PO {len(response.data)}건 감지됨")
                    await self.process_po_emails(response.data)
                
                self.last_po_check = current_time
                await asyncio.sleep(10)  # 10초마다 체크
                
            except Exception as e:
                logger.error(f"PO 감지 중 오류: {e}")
                await asyncio.sleep(30)

    async def watch_vendor_emails(self):
        """
        새로운 벤더 이메일을 실시간으로 감지하고 처리
        """
        while True:
            try:
                result = handle_general_vendor_email()
                if result:
                    self.stats.vendor_emails_processed = len(result)
                    self.stats.drafts_created = len([r for r in result if r.get('draft_body')])
                    logger.info(f"✅ {self.stats.drafts_created} 개의 드래프트 생성됨")
                
                await asyncio.sleep(30)  # 30초마다 체크
                
            except Exception as e:
                logger.error(f"벤더 이메일 처리 중 오류: {e}")
                await asyncio.sleep(30)

    async def watch_drafts(self):
        """
        생성된 드래프트를 실시간으로 감지하고 처리
        """
        while True:
            try:
                # 자동 승인이 필요한 드래프트 확인
                response = supabase.table("email_logs") \
                    .select("*") \
                    .eq("status", "draft") \
                    .execute()
                
                if response.data:
                    logger.info(f"자동 승인 대상 드래프트 {len(response.data)}건 감지됨")
                    await confirm_and_send_drafts()
                
                await asyncio.sleep(10)  # 10초마다 체크
                
            except Exception as e:
                logger.error(f"드래프트 처리 중 오류: {e}")
                await asyncio.sleep(30)

    async def check_follow_ups(self):
        """
        후속 조치가 필요한 건들을 주기적으로 확인
        """
        while True:
            try:
                current_time = datetime.now()
                
                # 후속 조치 필요 여부 확인 (1시간마다)
                if (current_time - self.last_follow_up_check).total_seconds() >= 3600:
                    await send_follow_up_emails()
                    self.last_follow_up_check = current_time
                
                await asyncio.sleep(600)  # 10분마다 체크
                
            except Exception as e:
                logger.error(f"후속 조치 확인 중 오류: {e}")
                await asyncio.sleep(300)

    async def start(self):
        """
        모든 워커를 동시에 시작
        """
        await asyncio.gather(
            self.watch_new_pos(),
            self.watch_vendor_emails(),
            self.watch_drafts(),
            self.check_follow_ups()
        )

def print_monitoring_summary(stats: MonitoringStats):
    """모니터링 결과 요약 출력"""
    print(f"\n{'='*50}")
    print("모니터링 결과 요약")
    print(f"{'='*50}")
    print(f"- 처리된 벤더 이메일: {stats.vendor_emails_processed}")
    print(f"- 생성된 드래프트: {stats.drafts_created}")
    print(f"- 발송된 드래프트: {stats.drafts_sent}")
    print(f"- 발송된 PO 이메일: {stats.pos_sent}")
    print(f"- 발송된 후속 조치: {stats.follow_ups_sent}")
    
    if stats.errors:
        print("\n⚠️ 발생한 오류:")
        for error in stats.errors:
            print(f"- [{error['timestamp']}] {error['task']}: {error['error']}")
    print(f"{'='*50}\n")

async def monitor_all(interval: int):
    """
    모든 이메일 관련 작업을 주기적으로 모니터링합니다.
    
    Args:
        interval: 모니터링 간격(초)
    """
    stats = MonitoringStats()
    
    while True:
        try:
            start_time = datetime.now()
            logger.info(f"작업 시작: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # 통계 초기화
            stats.reset()
            
            # 1. 벤더 이메일 처리
            await process_vendor_emails(stats)
            
            # 2. 드래프트 확인 및 발송
            await process_drafts(stats)
            
            # 3. PO 이메일 발송
            await process_po_emails(stats)
            
            # 4. 후속 조치 이메일
            await process_follow_ups(stats)
            
            # 결과 요약 출력
            print_monitoring_summary(stats)
            
            # 다음 실행까지 대기
            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()
            wait_time = max(0, interval - execution_time)
            
            logger.info(f"작업 완료. 실행 시간: {execution_time:.1f}초")
            logger.info(f"다음 실행까지 {wait_time:.1f}초 대기")
            
            await asyncio.sleep(wait_time)
            
        except Exception as e:
            logger.error(f"모니터링 중 오류 발생: {e}")
            stats.add_error('monitoring', e)
            print_monitoring_summary(stats)
            await asyncio.sleep(60)  # 오류 발생 시 1분 후 재시도

def setup_argparse():
    parser = argparse.ArgumentParser(description='PO Agent External Communication Manager')
    parser.add_argument('action', choices=[
        'handle_vendor_email',     # 벤더 이메일 처리
        'send_po',                 # PO 발행 이메일 발송
        'follow_up',              # 후속 조치 이메일 발송
        'update_threads',         # 이메일 스레드 업데이트
        'confirm_drafts',         # 드래프트 확인 및 발송
        'monitor'                 # 모든 기능 모니터링
    ], help='실행할 작업을 선택하세요')
    
    parser.add_argument('--interval', type=int, default=300,
                      help='모니터링 간격(초), 기본값: 300초')
    
    return parser.parse_args()

async def main():
    args = setup_argparse()
    processor = EmailProcessor()
    
    try:
        if args.action == 'monitor':
            logger.info("이벤트 기반 모니터링 시작")
            await processor.start()
        else:
            # 기존의 단일 작업 실행 로직 유지
            if args.action == 'handle_vendor_email':
                result = handle_general_vendor_email()
                if result:
                    print(f"✅ {len(result)} 개의 드래프트 생성됨")
            elif args.action == 'send_po':
                pass
            elif args.action == 'follow_up':
                await send_follow_up_emails()
            elif args.action == 'update_threads':
                pass
            elif args.action == 'confirm_drafts':
                await confirm_and_send_drafts()
            
    except KeyboardInterrupt:
        logger.warning("\n⚠️ 프로그램이 사용자에 의해 중단되었습니다.")
    except Exception as e:
        logger.error(f"\n❌ 오류 발생: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main()) 