"""
Groq API client wrapper for AI-powered ERP responses.
Uses llama-3.1-70b-versatile model for high-quality roleplay.
"""
import os
from groq import Groq
from groq.types.chat import ChatCompletion


class GroqClient:
    """Client for interacting with Groq's LLM API."""

    def __init__(self):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY not found in environment variables. Check your .env file.")
        self.client = Groq(api_key=api_key)
        self.model = "llama-3.3-70b-versatile"

    def generate(self, messages: list, temperature: float = 0.85, max_tokens: int = 800) -> str:
        """
        Generate a response from the LLM.

        Args:
            messages: List of message dicts [{"role": "system/user/assistant", "content": "..."}]
            temperature: Creativity level (0.0-1.0). Higher = more creative/risque.
            max_tokens: Maximum tokens in the response.

        Returns:
            The generated text response.
        """
        try:
            response: ChatCompletion = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"❌ Groq API Error: {e}")
            return "I'm a bit speechless right now... give me a moment. 💋"
