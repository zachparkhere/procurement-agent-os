import os
from datetime import datetime
from supabase import create_client
from openai import OpenAI
from textwrap import wrap
import logging
from typing import List, Dict, Any, Optional
from vector_store.config import settings

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 클라이언트 초기화
supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
client = OpenAI(api_key=settings.OPENAI_API_KEY)

class VectorStoreManager:
    def __init__(self):
        self.MAX_CHARS = settings.MAX_CHARS  # OpenAI 임베딩 모델의 토큰 제한을 고려

    def generate_embedding(self, text: str) -> Optional[List[float]]:
        """텍스트를 벡터로 변환"""
        if not text:
            return None
        try:
            response = client.embeddings.create(
                model="text-embedding-ada-002",
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"임베딩 생성 오류: {e}")
            return None

    def clean_deleted_records(self):
        """삭제된 원본 레코드에 대한 임베딩 정리"""
        logger.info("삭제된 레코드의 임베딩 정리 시작...")
        
        # schema_embeddings의 모든 레코드 조회
        embeddings = supabase.table("schema_embeddings").select("*").execute().data
        
        for embedding in embeddings:
            table_name = embedding["table_name"]
            record_id = embedding["record_id"]
            
            # 원본 테이블에서 레코드 존재 여부 확인
            original_record = supabase.table(table_name).select("id").eq("id", record_id).execute().data
            
            # 원본 레코드가 없으면 임베딩도 삭제
            if not original_record:
                supabase.table("schema_embeddings").delete().eq("id", embedding["id"]).execute()
                logger.info(f"삭제된 레코드의 임베딩 제거: {table_name} ID {record_id}")

    def generate_po_items_content(self, item: Dict[str, Any]) -> str:
        """PO 아이템 정보를 문자열로 변환"""
        return (
            f"Item No: {item.get('item_no', 'N/A')}\n"
            f"Description: {item.get('description', 'N/A')}\n"
            f"Quantity: {item.get('quantity', 'N/A')}\n"
            f"Unit Price: ${item.get('unit_price', 'N/A')}\n"
            f"Subtotal: ${item.get('subtotal', 'N/A')}\n"
            f"Tax: ${item.get('tax', 'N/A')}\n"
            f"Shipping Fee: ${item.get('shipping_fee', 'N/A')}\n"
            f"Other Fee: ${item.get('other_fee', 'N/A')}\n"
            f"Total: ${item.get('total', 'N/A')}\n"
            f"Category: {item.get('category', 'N/A')}"
        )

    def generate_purchase_order_content(self, po: Dict[str, Any], items: List[Dict[str, Any]]) -> str:
        """구매 주문서 정보를 문자열로 변환"""
        items_text = "\n".join([
            f"- {item.get('description', 'N/A')} "
            f"(Quantity: {item.get('quantity', 0)}, "
            f"Unit Price: ${item.get('unit_price', 0.0)})"
            for item in items
        ]) or "No items listed."

        return f"""
        Purchase Order Number: {po.get('po_number')}
        Vendor Name: {po.get('vendor_name')}
        Delivery Date: {po.get('delivery_date')}
        Currency: {po.get('currency')}
        Shipping Terms: {po.get('shipping_terms')}
        Payment Terms: {po.get('payment_terms')}
        Ordered Items:
        {items_text}
        """.strip()

    def generate_request_form_content(self, form: Dict[str, Any]) -> str:
        """요청 양식 정보를 문자열로 변환"""
        return f"""
        Request ID: {form.get('request_id')}
        Request Date: {form.get('request_date')}
        Due Date: {form.get('due_date')}
        Category: {form.get('category')}
        Approval Status: {form.get('approval_status')}
        Priority: {form.get('priority')}
        Total Amount: {form.get('total_amount')}
        Requester Communication: {form.get('requester_comm_status', '')}
        Vendor Communication: {form.get('vendor_comm_status', '')}
        Notes: {form.get('notes', '')}
        """.strip()

    def generate_email_content(self, email: Dict[str, Any]) -> str:
        """이메일 정보를 문자열로 변환"""
        subject = email.get("subject", "") or ""
        body = email.get("body", "") or ""
        sender = email.get("sender_email", "Unknown Sender")
        sent_at = email.get("sent_at")
        direction = email.get("direction")
        role = email.get("sender_role")
        has_attachments = email.get("has_attachments", False)
        attachment_names = email.get("attachment_names")

        content = f"""
        Email from: {sender}
        Role: {role if role else 'None'}
        Direction: {direction if direction else 'None'}
        Sent at: {sent_at if sent_at else 'None'}
        Subject: {subject}
        Has attachments: {has_attachments}
        Attachment names: {attachment_names if attachment_names else 'None'}
        Body:
        {body}
        """.strip()

        # 텍스트가 너무 길면 잘라내기
        chunks = wrap(content, self.MAX_CHARS)
        return chunks[0]  # 첫 번째 청크만 사용

    def update_embeddings(self, table_name: str, record_id: str, content: str):
        """임베딩 생성 및 업데이트"""
        record_ref = f"{table_name}:{record_id}"
        embedding = self.generate_embedding(content)
        
        if not embedding:
            logger.warning(f"임베딩 생성 실패: {table_name} ID {record_id}")
            return

        try:
            # 기존 임베딩 확인
            existing = supabase.table("schema_embeddings").select("id").eq("record_ref", record_ref).execute().data

            if existing:
                # 기존 레코드 업데이트
                supabase.table("schema_embeddings").update({
                    "content": content,
                    "embedding": embedding,
                    "updated_at": datetime.utcnow().isoformat()
                }).eq("record_ref", record_ref).execute()
                logger.info(f"임베딩 업데이트 완료: {record_ref}")
            else:
                # 새 레코드 생성
                supabase.table("schema_embeddings").insert({
                    "table_name": table_name,
                    "field_name": "__row__",
                    "record_id": record_id,
                    "record_ref": record_ref,
                    "content": content,
                    "embedding": embedding,
                    "created_at": datetime.utcnow().isoformat()
                }).execute()
                logger.info(f"새 임베딩 생성 완료: {record_ref}")

        except Exception as e:
            logger.error(f"임베딩 저장 오류 ({record_ref}): {e}")

    def process_po_items(self):
        """PO 아이템 임베딩 처리"""
        logger.info("PO 아이템 임베딩 처리 시작...")
        try:
            items = supabase.table("po_items").select("*").execute().data
            for item in items:
                content = self.generate_po_items_content(item)
                self.update_embeddings("po_items", item["id"], content)
        except Exception as e:
            logger.error(f"PO 아이템 처리 오류: {e}")

    def process_purchase_orders(self):
        """구매 주문서 임베딩 처리"""
        logger.info("구매 주문서 임베딩 처리 시작...")
        try:
            orders = supabase.table("purchase_orders").select("*").execute().data
            for po in orders:
                items = supabase.table("po_items").select("*").eq("purchase_order_id", po["id"]).execute().data
                content = self.generate_purchase_order_content(po, items)
                self.update_embeddings("purchase_orders", po["id"], content)
        except Exception as e:
            logger.error(f"구매 주문서 처리 오류: {e}")

    def process_request_forms(self):
        """요청 양식 임베딩 처리"""
        logger.info("요청 양식 임베딩 처리 시작...")
        try:
            forms = supabase.table("request_form").select("*").execute().data
            for form in forms:
                content = self.generate_request_form_content(form)
                self.update_embeddings("request_form", form["id"], content)
        except Exception as e:
            logger.error(f"요청 양식 처리 오류: {e}")

    def process_email_logs(self):
        """이메일 로그 임베딩 처리"""
        logger.info("이메일 로그 임베딩 처리 시작...")
        try:
            emails = supabase.table("email_logs").select("*").execute().data
            for email in emails:
                content = self.generate_email_content(email)
                self.update_embeddings("email_logs", email["id"], content)
        except Exception as e:
            logger.error(f"이메일 로그 처리 오류: {e}")

    def process_all(self):
        """모든 테이블의 임베딩 처리"""
        logger.info("전체 임베딩 처리 시작...")
        self.clean_deleted_records()  # 삭제된 레코드의 임베딩 정리
        self.process_po_items()
        self.process_purchase_orders()
        self.process_request_forms()
        self.process_email_logs()
        logger.info("전체 임베딩 처리 완료")

if __name__ == "__main__":
    vector_store = VectorStoreManager()
    vector_store.process_all() 