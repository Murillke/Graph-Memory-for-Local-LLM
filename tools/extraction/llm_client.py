"""
LLM client for extraction.
Supports OpenAI API and compatible endpoints.
"""

import os
import json
from typing import List, Dict, Any, Optional, Type
from pydantic import BaseModel


class LLMClient:
    """Client for calling LLM APIs with structured output."""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
        base_url: Optional[str] = None
    ):
        """
        Initialize LLM client.
        
        Args:
            api_key: OpenAI API key (or set OPENAI_API_KEY env var)
            model: Model name (default: gpt-4o-mini for cost efficiency)
            base_url: Optional base URL for API (for compatible endpoints)
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OpenAI API key required. Set OPENAI_API_KEY environment variable "
                "or pass api_key parameter."
            )
        
        self.model = model
        self.base_url = base_url
        
        # Import OpenAI client
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError(
                "OpenAI package required. Install with: pip install openai"
            )
        
        # Initialize client
        if base_url:
            self.client = OpenAI(api_key=self.api_key, base_url=base_url)
        else:
            self.client = OpenAI(api_key=self.api_key)
    
    def call(
        self,
        messages: List[Dict[str, str]],
        response_format: Optional[Type[BaseModel]] = None,
        temperature: float = 0.0,
        max_tokens: Optional[int] = None
    ) -> Any:
        """
        Call LLM with messages and optional structured output.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            response_format: Optional Pydantic model for structured output
            temperature: Sampling temperature (0.0 = deterministic)
            max_tokens: Maximum tokens to generate
        
        Returns:
            If response_format is provided: Pydantic model instance
            Otherwise: String response
        """
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        
        if max_tokens:
            kwargs["max_tokens"] = max_tokens
        
        # Use structured output if response_format provided
        if response_format:
            # OpenAI's structured output feature
            kwargs["response_format"] = response_format
            
            response = self.client.beta.chat.completions.parse(**kwargs)
            return response.choices[0].message.parsed
        else:
            # Regular text response
            response = self.client.chat.completions.create(**kwargs)
            return response.choices[0].message.content
    
    def call_with_json(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.0,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Call LLM and parse JSON response.
        
        Args:
            messages: List of message dicts
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
        
        Returns:
            Parsed JSON dict
        """
        response = self.call(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        # Parse JSON from response
        try:
            return json.loads(response)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse JSON response: {e}\nResponse: {response}")


# ============================================================
# Convenience Functions
# ============================================================

def get_default_client() -> LLMClient:
    """Get default LLM client with environment-based configuration."""
    model = os.getenv("EXTRACTION_MODEL", "gpt-4o-mini")
    base_url = os.getenv("OPENAI_BASE_URL")
    
    return LLMClient(model=model, base_url=base_url)


def test_client() -> bool:
    """Test if LLM client is working."""
    try:
        client = get_default_client()
        response = client.call([
            {"role": "user", "content": "Say 'OK' if you can hear me."}
        ])
        return "OK" in response or "ok" in response.lower()
    except Exception as e:
        print(f"LLM client test failed: {e}")
        return False


if __name__ == "__main__":
    # Test the client
    print("Testing LLM client...")
    if test_client():
        print("[OK] LLM client is working!")
    else:
        print("[ERROR] LLM client test failed")

