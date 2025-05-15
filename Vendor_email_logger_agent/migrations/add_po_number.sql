-- email_logs 테이블에 po_number 컬럼 추가
ALTER TABLE email_logs
ADD COLUMN po_number VARCHAR(50);

-- po_number에 인덱스 추가
CREATE INDEX idx_email_logs_po_number ON email_logs(po_number);

-- 기존 이메일의 PO 번호 업데이트를 위한 함수
CREATE OR REPLACE FUNCTION update_existing_po_numbers()
RETURNS void AS $$
DECLARE
    email_record RECORD;
    po_number VARCHAR(50);
BEGIN
    FOR email_record IN 
        SELECT id, subject, body, attachments 
        FROM email_logs 
        WHERE po_number IS NULL
    LOOP
        -- PO 번호 추출 로직 (정규식 패턴)
        po_number := (
            SELECT regexp_matches(
                COALESCE(email_record.subject, '') || ' ' || 
                COALESCE(email_record.body, '') || ' ' || 
                COALESCE(email_record.attachments::text, ''),
                'PO[-\s]?(\d{6,})|Purchase\s*Order[-\s]?(\d{6,})|P\.?O\.?[-\s]?(\d{6,})|Order\s*#\s*(\d{6,})|Order\s*Number[-\s]?(\d{6,})',
                'i'
            )[1]
        );
        
        IF po_number IS NOT NULL THEN
            UPDATE email_logs
            SET po_number = po_number
            WHERE id = email_record.id;
        END IF;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- 기존 데이터 업데이트 실행
SELECT update_existing_po_numbers();

-- 함수 삭제
DROP FUNCTION update_existing_po_numbers(); 