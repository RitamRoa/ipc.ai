import os
import json
import re
import time
from groq import Groq
from dotenv import load_dotenv
from prompts import SYSTEM_PROMPT

load_dotenv()

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
MODEL_NAME = 'llama-3.3-70b-versatile'


def extract_retry_delay_seconds(error_text: str):
    retry_after_match = re.search(r"retry[-_ ]?after['\"]?\s*[:=]\s*['\"]?(\d+)", error_text, re.IGNORECASE)
    if retry_after_match:
        return int(retry_after_match.group(1))

    match = re.search(r"retryDelay['\"]?\s*:\s*['\"]?(\d+)s", error_text)
    if match:
        return int(match.group(1))
    return None


def classify_planner_error(error: Exception) -> dict:
    error_text = str(error)
    err_str = error_text.lower()

    if '429' in err_str or 'quota' in err_str or 'exhausted' in err_str or 'rate' in err_str:
        retry_after_seconds = extract_retry_delay_seconds(error_text)
        message = (
            "Groq quota or rate limit was reached. This can be a per-minute, daily, "
            "or account-level free-tier limit."
        )
        if retry_after_seconds:
            message += f" Groq suggested retrying after about {retry_after_seconds} seconds."
        return {
            "intent": "rate_limited",
            "message": message,
            "retry_after_seconds": retry_after_seconds,
            "model": MODEL_NAME,
        }
    if 'json' in err_str or 'parse' in err_str:
        return {"intent": "invalid_json", "message": error_text, "model": MODEL_NAME}
    return {"intent": "api_error", "message": error_text, "model": MODEL_NAME}


def generate_query_plan(user_query: str, max_retries: int = 1) -> dict:
    """
    Takes a natural language query and returns a structured JSON intent using Groq.
    """
    prompt = f"{SYSTEM_PROMPT}\n\nUser Question: {user_query}\nJSON:"

    for attempt in range(max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": "Return only a valid JSON object. Do not include markdown."},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0,
            )
            plan_str = response.choices[0].message.content.strip()
            return json.loads(plan_str)
        except Exception as e:
            error_plan = classify_planner_error(e)
            retry_after_seconds = error_plan.get("retry_after_seconds")
            should_retry = (
                error_plan["intent"] == "rate_limited"
                and attempt < max_retries
                and retry_after_seconds is not None
                and retry_after_seconds <= 10
            )
            if should_retry:
                time.sleep(retry_after_seconds)
                continue
            return error_plan
