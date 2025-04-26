# llm_extract_info_needs.py

import os
import json # Import json module
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

def llm_extract_info_needs(email_subject, email_body):
    prompt = f"""
You are a helpful procurement planning assistant.
You will receive an email from a vendor. Your task is to:

1. Understand the intent of the message.
2. Decide whether a reply is needed.
3. Determine the appropriate type of reply: 'standard' (needs context/detail), 'simple_acknowledgment' (e.g., 'Thanks for confirming'), or 'no_reply'.
4. If a 'standard' reply is needed, list the specific pieces of information (like ETA, vendor name, PO status, delivery confirmation details, etc.) from our internal system that would be helpful. If no extra info is needed, provide an empty list [].

Here is the vendor message:
---
Subject: {email_subject}
Body:
{email_body}
---

You MUST respond ONLY with a valid JSON object containing the following keys:
"intent": A short natural language description of the vendor's intent.
"reply_needed": A boolean value (true or false).
"suggested_reply_type": A string, must be one of 'standard', 'simple_acknowledgment', or 'no_reply'. Set to 'simple_acknowledgment' if the vendor just provided information and a simple thank you is sufficient. Set to 'no_reply' if reply_needed is false.
"information_needed": A list of strings representing the specific information needed for a 'standard' reply (e.g., ["ETA", "PO status"]). Use an empty list [] if the reply type is not 'standard' or no specific information is required.

Example JSON output format:
{{
  "intent": "Vendor confirmed delivery date for PO-123",
  "reply_needed": true,
  "suggested_reply_type": "simple_acknowledgment",
  "information_needed": []
}}

Another Example:
{{
  "intent": "Vendor asking for payment status of invoice INV-456",
  "reply_needed": true,
  "suggested_reply_type": "standard",
  "information_needed": ["Invoice payment status INV-456", "PO number related to INV-456"]
}}

Another Example:
{{
  "intent": "Vendor sent marketing newsletter",
  "reply_needed": false,
  "suggested_reply_type": "no_reply",
  "information_needed": []
}}
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            response_format={ "type": "json_object" },
            messages=[
                {"role": "system", "content": "You analyze vendor emails and respond ONLY with the specified JSON object."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2
        )
        
        return response.choices[0].message.content.strip()

    except Exception as e:
        print(f"❌ Error calling OpenAI API in llm_extract_info_needs: {e}")
        return json.dumps({
            "intent": "Error during analysis",
            "reply_needed": False,
            "suggested_reply_type": "no_reply",
            "information_needed": []
        })

# Example usage
if __name__ == "__main__":
    subject = "RE: PO-2025-001 Delivery Date Confirmation"
    body = "We confirm that the goods will be delivered by May 2nd."
    result_json_str = llm_extract_info_needs(subject, body)
    print("Raw JSON Output:")
    print(result_json_str)
    try:
        parsed_result = json.loads(result_json_str)
        print("\nParsed JSON Object:")
        print(parsed_result)
    except json.JSONDecodeError as e:
        print(f"\n❌ Failed to parse the returned JSON: {e}") 