"""
OpenRouter API client for AI-powered forensic report generation.
Replaces Ollama with cloud-based LLM inference via OpenRouter.
"""

import os
import json
import logging
from typing import Optional, Dict, Any

import requests

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def get_openrouter_key() -> Optional[str]:
    """Get OpenRouter API key from environment variable."""
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        key = os.environ.get("OPENROUTER_KEY")
    return key


def generate_with_openrouter(
    prompt: str,
    model: str = "google/gemini-2.0-flash-001",
    temperature: float = 0.1,
    max_tokens: int = 4096,
) -> Optional[str]:
    """
    Generate text using OpenRouter API (OpenAI-compatible).

    Args:
        prompt: The prompt to send
        model: Model identifier on OpenRouter
        temperature: Sampling temperature (0.0-2.0)
        max_tokens: Maximum tokens in response

    Returns:
        Generated text or None on failure
    """
    api_key = get_openrouter_key()
    if not api_key:
        logger.error("OPENROUTER_API_KEY not set in environment")
        return None

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/labmoon/hops",
        "X-Title": "HOPS Bitcoin Forensics",
    }

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }

    try:
        response = requests.post(OPENROUTER_URL, json=payload, headers=headers, timeout=120)
        response.raise_for_status()
        result = response.json()

        choices = result.get("choices", [])
        if not choices:
            logger.warning("OpenRouter returned no choices")
            return None

        text = choices[0].get("message", {}).get("content", "").strip()
        if not text:
            logger.warning("OpenRouter returned empty content")
            return None

        return text

    except requests.exceptions.ConnectionError:
        logger.error("Cannot connect to OpenRouter API")
        return None
    except requests.exceptions.Timeout:
        logger.error("Timeout connecting to OpenRouter API")
        return None
    except requests.exceptions.HTTPError as e:
        logger.error(f"OpenRouter HTTP error: {e}")
        if response is not None:
            logger.error(f"Response: {response.text[:500]}")
        return None
    except Exception as e:
        logger.error(f"OpenRouter error: {e}")
        return None


AVAILABLE_MODELS = [
    "google/gemini-2.0-flash-001",
    "google/gemini-2.0-flash-lite-001",
    "openai/gpt-4o-mini",
    "openai/gpt-4o",
    "anthropic/claude-3.5-haiku",
    "anthropic/claude-3.5-sonnet",
    "meta-llama/llama-3.1-8b-instruct",
    "meta-llama/llama-3.1-70b-instruct",
    "mistralai/mistral-7b-instruct",
    "deepseek/deepseek-chat",
    "qwen/qwen-2.5-7b-instruct",
]
