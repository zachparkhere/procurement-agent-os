import os
from typing import List, Dict, Any, Optional
from supabase import create_client
from openai import OpenAI
import numpy as np
import logging
from .config import settings

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 클라이언트 초기화
supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
client = OpenAI(api_key=settings.OPENAI_API_KEY)

class VectorSearch:
    @staticmethod
    def cosine_similarity(a: List[float], b: List[float]) -> float:
        """코사인 유사도 계산"""
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

    @staticmethod
    def get_embedding(text: str) -> List[float]:
        """텍스트의 임베딩 벡터 생성"""
        try:
            response = client.embeddings.create(
                model="text-embedding-ada-002",
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"임베딩 생성 오류: {e}")
            raise

    def search_similar_records(self, query: str, table_name: str = None, top_k: int = 5, threshold: float = 0.7) -> List[Dict[str, Any]]:
        """유사한 레코드 검색"""
        try:
            query_embedding = self.get_embedding(query)
            
            # 검색 쿼리 구성
            search_query = supabase.rpc(
                "match_documents",
                {
                    "query_embedding": query_embedding,
                    "match_threshold": threshold,
                    "match_count": top_k,
                    "table_filter": table_name
                }
            )
            
            result = search_query.execute()
            return result.data

        except Exception as e:
            logger.error(f"유사 레코드 검색 오류: {e}")
            return []

    def find_similar_emails(self, query: str, top_k: int = 3, threshold: float = 0.7) -> List[Dict[str, Any]]:
        """이메일 로그에서 유사한 이메일 검색"""
        return self.search_similar_records(query, "email_logs", top_k, threshold)

    def find_similar_purchase_orders(self, query: str, top_k: int = 3, threshold: float = 0.7) -> List[Dict[str, Any]]:
        """구매 주문서에서 유사한 문서 검색"""
        return self.search_similar_records(query, "purchase_orders", top_k, threshold)

    def find_similar_po_items(self, query: str, top_k: int = 3, threshold: float = 0.7) -> List[Dict[str, Any]]:
        """PO 아이템에서 유사한 항목 검색"""
        return self.search_similar_records(query, "po_items", top_k, threshold)

    def find_similar_request_forms(self, query: str, top_k: int = 3, threshold: float = 0.7) -> List[Dict[str, Any]]:
        """요청 양식에서 유사한 문서 검색"""
        return self.search_similar_records(query, "request_form", top_k, threshold)

    def search_all(self, query: str, top_k: int = 3, threshold: float = 0.7) -> Dict[str, List[Dict[str, Any]]]:
        """모든 테이블에서 유사한 레코드 검색"""
        return {
            "emails": self.find_similar_emails(query, top_k, threshold),
            "purchase_orders": self.find_similar_purchase_orders(query, top_k, threshold),
            "po_items": self.find_similar_po_items(query, top_k, threshold),
            "request_forms": self.find_similar_request_forms(query, top_k, threshold)
        } 