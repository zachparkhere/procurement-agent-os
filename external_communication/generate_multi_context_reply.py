# generate_multi_context_reply.py

import os
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai_client = OpenAI(api_key=OPENAI_API_KEY)

def generate_multi_context_reply(po_number, info, context_blocks, thread_id, email_subject, email_body):
    # Build context text from blocks
    context_text = ""
    if context_blocks:
        for table, desc, _ in context_blocks:
            if table != "email_thread":
                context_text += f"\nFrom {table}:\n{desc}\n"
    else:
        context_text = "\nNo additional context available."

    # Add email thread context if available
    email_thread_context = info.get('email_thread_context') if isinstance(info, dict) else None
    thread_text = f"""\n\nHere is recent email conversation history:\n{email_thread_context}""" if email_thread_context else ""

    # Build the prompt
    prompt = f"""
You are a professional procurement assistant. You have received the following email from a vendor:

Subject: {email_subject or '(no subject)'}
Body:
{email_body or '(no content)'}{thread_text}

Here is relevant information from our system:
{context_text}

Your task:
- If a reply is needed, write a **very concise and polite** reply.
- Only include details or context if the vendor specifically asks for them, or if it is essential for clarity.
- If the vendor simply confirms or acknowledges, reply with a short, courteous message (e.g., "Thank you for your confirmation.").
- Always maintain a professional and respectful tone.
- Do NOT add unnecessary explanations or information.
- Only output the email body (no greeting, no signature, unless context requires).
"""

    print("[📝 GPT PROMPT]", prompt)

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=1000
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"❌ Error generating reply: {e}")
        return None 