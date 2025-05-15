import asyncio
import logging
from datetime import datetime
from typing import Optional
from vector_store.embed_records import VectorStoreManager
from vector_store.config import settings

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class VectorStoreService:
    def __init__(self):
        self.vector_store = VectorStoreManager()
        self.last_cleanup_time: Optional[datetime] = None
        self.cleanup_interval = settings.CLEANUP_INTERVAL
        self.update_interval = settings.UPDATE_INTERVAL

    async def cleanup_task(self):
        """주기적으로 삭제된 레코드의 임베딩을 정리"""
        while True:
            try:
                current_time = datetime.now()
                if (not self.last_cleanup_time or 
                    current_time - self.last_cleanup_time >= self.cleanup_interval):
                    logger.info("삭제된 레코드 임베딩 정리 작업 시작")
                    self.vector_store.clean_deleted_records()
                    self.last_cleanup_time = current_time
                    logger.info("임베딩 정리 작업 완료")
            except Exception as e:
                logger.error(f"임베딩 정리 중 오류 발생: {e}")
            
            await asyncio.sleep(self.cleanup_interval)

    async def update_task(self):
        """주기적으로 새로운 레코드의 임베딩을 생성/업데이트"""
        while True:
            try:
                logger.info("임베딩 업데이트 작업 시작")
                self.vector_store.process_all()
                logger.info("임베딩 업데이트 작업 완료")
            except Exception as e:
                logger.error(f"임베딩 업데이트 중 오류 발생: {e}")
            
            await asyncio.sleep(self.update_interval)

    async def start(self):
        """서비스 시작"""
        logger.info("벡터 스토어 서비스 시작")
        tasks = [
            self.cleanup_task(),
            self.update_task()
        ]
        await asyncio.gather(*tasks)

async def main():
    try:
        service = VectorStoreService()
        await service.start()
    except KeyboardInterrupt:
        logger.info("서비스 종료 요청 받음")
    except Exception as e:
        logger.error(f"서비스 실행 중 오류 발생: {e}")
    finally:
        logger.info("벡터 스토어 서비스 종료")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("프로그램 종료") 