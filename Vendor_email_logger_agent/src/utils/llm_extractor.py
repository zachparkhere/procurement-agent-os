import json
from typing import Optional, Dict, List
from ..services.openai_service import get_openai_client

class LLMExtractor:
    def __init__(self):
        self.client = get_openai_client()

    def extract_po_number(self, subject: str, body: str, thread_context: Optional[List[Dict]] = None) -> Optional[str]:
        """
        LLM을 사용하여 이메일 제목, 본문, 그리고 스레드 컨텍스트에서 PO 번호를 추출합니다.
        
        Args:
            subject: 이메일 제목
            body: 이메일 본문
            thread_context: 이전 이메일들의 컨텍스트 (옵션)
            
        Returns:
            추출된 PO 번호 또는 None
        """
        # 프롬프트 구성
        prompt = f"""
        다음 이메일에서 PO(Purchase Order) 번호를 찾아주세요.
        PO 번호는 다음과 같은 형식일 수 있습니다:
        1. PO-YYYY-XXX (예: PO-2024-001)
        2. POYYYYXXX (예: PO2024001)
        3. PO/YYYY/XXX (예: PO/2024/001)
        4. 또는 "귀사의 PO 번호 XXXX 관련하여" 와 같은 문맥에서 언급될 수 있습니다.

        이메일 제목: {subject}
        이메일 본문: {body}
        """
        
        if thread_context:
            prompt += "\n\n이전 이메일들:\n"
            for email in thread_context:
                prompt += f"""
                시간: {email.get('created_at', '')}
                제목: {email.get('subject', '')}
                본문: {email.get('body', '')}
                ---
                """
        
        prompt += """
        JSON 형식으로 응답해주세요:
        {
            "po_number": "찾은 PO 번호 또는 null",
            "confidence": "high/medium/low",
            "explanation": "PO 번호를 찾은 방법에 대한 설명"
        }
        """
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {"role": "system", "content": "이메일에서 PO 번호를 정확하게 추출하는 전문가입니다."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0
            )
            
            result = json.loads(response.choices[0].message.content)
            
            if result["confidence"] in ["high", "medium"] and result["po_number"]:
                return result["po_number"]
            
            return None
            
        except Exception as e:
            print(f"LLM PO 번호 추출 중 오류 발생: {e}")
            return None 