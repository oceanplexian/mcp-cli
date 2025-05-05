# src/llm/providers/base.py
import abc
from typing import Any, Dict, List, Callable

class BaseLLMClient(abc.ABC):
    @abc.abstractmethod
    def create_completion(self, messages: List[Dict], tools: List = None) -> Dict[str, Any]:
        """Create a chat completion using the specified LLM provider."""
        pass

    @abc.abstractmethod
    def stream_completion(self, messages: List[Dict], stream_callback: Callable[[str], None]) -> None:
        """Stream a chat completion's text content via a callback."""
        pass
