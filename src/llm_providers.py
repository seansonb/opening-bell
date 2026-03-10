"""
LLM Provider abstraction for supporting multiple AI services
"""

import os
from abc import ABC, abstractmethod
from rate_limiter import RateLimiter


class LLMProvider(ABC):
    """Abstract base class for LLM providers"""

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """Generate text from a prompt"""
        pass

    def supports_batching(self) -> bool:
        """Whether this provider benefits from batching multiple stocks"""
        return False


class ClaudeProvider(LLMProvider):
    """Anthropic Claude provider - no rate limiting needed, no batching"""

    def __init__(self):
        import anthropic
        self.client = anthropic.Anthropic(api_key=os.getenv('CLAUDE_API_KEY'))
        self.model = "claude-sonnet-4-20250514"

    def generate(self, prompt: str) -> str:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text

    def supports_batching(self) -> bool:
        return False


class GeminiProvider(LLMProvider):
    """Google Gemini provider - with rate limiting and batching support"""

    def __init__(self):
        import google.generativeai as genai
        genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
        self.model = genai.GenerativeModel('gemini-flash-latest')
        self.rate_limiter = RateLimiter()

    def generate(self, prompt: str) -> str:
        self.rate_limiter.wait_if_needed()
        response = self.model.generate_content(prompt)
        return response.text

    def supports_batching(self) -> bool:
        return True


def get_provider(name: str) -> LLMProvider:
    """Factory function to get the appropriate LLM provider"""
    providers = {
        'claude': ClaudeProvider,
        'gemini': GeminiProvider
    }

    if name.lower() not in providers:
        raise ValueError(f"Unknown provider: {name}. Valid options: {list(providers.keys())}")

    return providers[name.lower()]()
