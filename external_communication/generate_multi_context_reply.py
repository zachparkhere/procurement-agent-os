# generate_multi_context_reply.py

import os
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai_client = OpenAI(api_key=OPENAI_API_KEY)

def generate_multi_context_reply(email_subject, email_body, context_blocks, suggested_reply_type, email_thread_context=None):
    # Build context text from blocks
    context_text = ""
    if context_blocks:
        for table, desc in context_blocks:
            if table != "email_thread":  # Skip email thread context as it will be handled separately
                context_text += f"\nFrom {table}:\n{desc}\n"
    else:
        context_text = "\nNo additional context available."

    # Add email thread context if available
    thread_text = f"""\n\nHere is recent email conversation history:\n{email_thread_context}""" if email_thread_context else ""

    # Build the prompt
    prompt = f"""You are a helpful procurement assistant. You have received the following email from a vendor:

Subject: {email_subject}
Body:
{email_body}{thread_text}

Here is relevant information from our system:
{context_text}

Your task is to:
- Determine if a reply is needed
- If yes, generate a clear and professional email draft
- If the vendor provided a confirmed ETA, always acknowledge and ask to notify if any changes

Only output the email body.
"""

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