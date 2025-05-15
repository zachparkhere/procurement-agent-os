def extract_text_from_attachments(attachment_urls: list[str]) -> str:
    """
    Given a list of Supabase-hosted attachment URLs, return extracted combined text.
    Stub function — safe to call even if attachments are missing.
    """
    if not attachment_urls:
        return ""
    return "[ATTACHMENT TEXT PLACEHOLDER]"