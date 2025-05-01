import openai
import os

def summarize_text(text):
    """
    Summarize the given email draft body into 1-2 concise English sentences.
    """
    client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    prompt = f"Summarize the following email draft in 1-2 concise English sentences:\n\n{text}"
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=60,
        temperature=0.5,
    )
    return response.choices[0].message.content.strip() 