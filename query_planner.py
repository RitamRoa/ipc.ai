import os
import json
from google import genai
from google.genai import types
from dotenv import load_dotenv
from prompts import SYSTEM_PROMPT

load_dotenv()

# The new SDK automatically picks up GEMINI_API_KEY from the environment
client = genai.Client()

def generate_query_plan(user_query: str) -> dict:
    """
    Takes a natural language query and returns a structured JSON intent using Gemini.
    """
    prompt = f"{SYSTEM_PROMPT}\n\nUser Question: {user_query}\nJSON:"
    try:
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            )
        )
        plan_str = response.text.strip()
        # Parse the JSON string
        return json.loads(plan_str)
    except Exception as e:
        err_str = str(e).lower()
        if '429' in err_str or 'quota' in err_str or 'exhausted' in err_str or 'rate' in err_str:
            return {"intent": "rate_limited", "message": "API rate limit exceeded."}
        elif 'json' in err_str or 'parse' in err_str:
            return {"intent": "invalid_json", "message": str(e)}
        else:
            return {"intent": "api_error", "message": str(e)}