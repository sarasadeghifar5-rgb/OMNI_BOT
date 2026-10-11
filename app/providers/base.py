from abc import ABC, abstractmethod
from typing import AsyncGenerator, Dict, Any, List, Optional

class BaseProvider(ABC):
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key
        self.base_url = base_url

    @abstractmethod
    async def stream_chat(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        api_key: Optional[str] = None,
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Asynchronously stream responses from the AI provider.
        Yields dictionaries with keys:
          - type: 'thinking' | 'content' | 'error' | 'done'
          - content: str (the text or thinking snippet)
          - usage: Optional[dict]
        """
        pass
