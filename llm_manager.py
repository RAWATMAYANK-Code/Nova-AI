"""
llm_manager.py
Manages LLM execution across multiple API keys and providers (Groq & Gemini).
Instead of calling multiple models in parallel, it uses ONE model/key at a time.
If an API key hits a rate limit, token limit, or quota error, it automatically
switches to the next key in the rotation pool and retries.
"""

import os
import json
import re
import requests
from dotenv import load_dotenv
from groq import Groq, RateLimitError

load_dotenv(override=True)

# Redact API keys from exception strings before logging/returning
API_KEY_PATTERN = re.compile(r"(key=[^&\s\"']+|gsk_[A-Za-z0-9_]+|AIzaSy[A-Za-z0-9_-]+|AQ\.[A-Za-z0-9_-]+)", re.IGNORECASE)


def redact_key(text):
    if not text:
        return ""
    return API_KEY_PATTERN.sub("key=REDACTED_KEY", str(text))


class LLMManager:
    def __init__(self):
        self.slots = []
        self.current_index = 0
        self.reload_keys()

    def reload_keys(self):
        load_dotenv(override=True)
        slots = []

        # Parse Groq Keys
        groq_raw = os.getenv("GROQ_API_KEY", "")
        groq_keys = [k.strip() for k in groq_raw.split(",") if k.strip()]
        for idx, key in enumerate(groq_keys, 1):
            slots.append({
                "provider": "groq",
                "key": key,
                "label": f"Groq (Key {idx})" if len(groq_keys) > 1 else "Groq",
                "model_heavy": "llama-3.3-70b-versatile",
                "model_fast": "llama-3.1-8b-instant"
            })

        # Parse Gemini Keys
        gemini_raw = os.getenv("GEMINI_API_KEY", "")
        gemini_keys = [k.strip() for k in gemini_raw.split(",") if k.strip()]
        for idx, key in enumerate(gemini_keys, 1):
            slots.append({
                "provider": "gemini",
                "key": key,
                "label": f"Gemini (Key {idx})" if len(gemini_keys) > 1 else "Gemini",
                "model": "gemini-2.0-flash"
            })

        self.slots = slots
        if self.current_index >= len(self.slots):
            self.current_index = 0

    def get_current_slot(self):
        if not self.slots:
            self.reload_keys()
        if not self.slots:
            raise ValueError("No API keys configured for Groq or Gemini in .env!")
        return self.slots[self.current_index]

    def advance_slot(self, reason="Rate/Token Limit"):
        if not self.slots:
            return
        old_slot = self.slots[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.slots)
        new_slot = self.slots[self.current_index]
        print(f"\n[API ROTATOR] [!] {reason} on {old_slot['label']}. Automatically switching to {new_slot['label']}...")

    def run_query(self, prompt, tools=None, fast_mode=False):
        """
        Executes a prompt using the single currently active API key.
        If a token/rate limit error occurs, automatically rotates to the next key and retries.
        """
        if not self.slots:
            self.reload_keys()
        if not self.slots:
            return {"error": "No API keys configured.", "api_used": "None", "failed": True}

        attempts = 0
        max_attempts = len(self.slots)

        while attempts < max_attempts:
            slot = self.slots[self.current_index]
            provider = slot["provider"]
            key = slot["key"]
            label = slot["label"]

            try:
                if provider == "groq":
                    res_text = self._call_groq(key, slot, prompt, tools=tools, fast_mode=fast_mode)
                    return {"text": res_text, "api_used": label, "failed": False}

                elif provider == "gemini":
                    res_text = self._call_gemini(key, slot, prompt)
                    return {"text": res_text, "api_used": label, "failed": False}

            except Exception as e:
                err_msg = str(e)
                is_rate_limit = (
                    isinstance(e, RateLimitError) or
                    "429" in err_msg or
                    "rate_limit" in err_msg.lower() or
                    "token" in err_msg.lower() or
                    "quota" in err_msg.lower() or
                    "resource_exhausted" in err_msg.lower()
                )

                if is_rate_limit:
                    self.advance_slot(reason="Token/Rate Limit Reached")
                    attempts += 1
                else:
                    print(f"[API ROTATOR] Error on {label}: {redact_key(err_msg)}")
                    self.advance_slot(reason="API Error")
                    attempts += 1

        return {
            "error": "All API keys in rotation exhausted or failed.",
            "api_used": "All Keys Exhausted",
            "failed": True
        }

    def _call_groq(self, key, slot, prompt, tools=None, fast_mode=False):
        client = Groq(api_key=key)
        model = slot["model_fast"] if fast_mode else slot["model_heavy"]
        kwargs = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2 if not fast_mode else 0.1,
            "max_tokens": 600 if not fast_mode else 150,
        }
        if "gpt-oss" in model:
            if not fast_mode:
                kwargs["reasoning_effort"] = "low"
            if tools and "browser_search" in tools:
                kwargs["tools"] = [{"type": "browser_search"}]
                kwargs["tool_choice"] = "auto"

        response = client.chat.completions.create(**kwargs)
        message = response.choices[0].message
        raw = (message.content or "").strip()
        if not raw and hasattr(message, "reasoning") and message.reasoning:
            raw = message.reasoning.strip()
        return raw

    def _call_gemini(self, key, slot, prompt):
        model = slot["model"]
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        response = requests.post(
            url,
            params={"key": key},
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=25,
        )

        if response.status_code == 429:
            raise ValueError("Gemini 429 Rate Limit Exceeded")

        response.raise_for_status()
        data = response.json()
        candidates = data.get("candidates") or []
        if not candidates:
            raise ValueError(f"Gemini returned no candidates: {data}")

        parts = candidates[0].get("content", {}).get("parts") or []
        if not parts:
            raise ValueError(f"Gemini candidate has no text parts: {candidates[0]}")

        return parts[0].get("text", "").strip()


# Global singleton instance
llm_manager = LLMManager()
