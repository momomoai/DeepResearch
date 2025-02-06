import httpx
import logging
from typing import Dict, Any, Optional, Tuple

from ..config import settings
from ..types import ReadResponse
from ..utils.token_tracker import TokenTracker

class Reader:
    @staticmethod
    async def read_url(url: str, tracker: Optional[TokenTracker] = None) -> Tuple[ReadResponse, int]:
        data = {"url": url}
        
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {settings.JINA_API_KEY}",
            "Content-Type": "application/json",
            "X-Retain-Images": "none",
            "X-Return-Format": "markdown"
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    "https://r.jina.ai/",
                    headers=headers,
                    json=data
                )
                response_data = response.json()
                response_obj = ReadResponse(**response_data)
                
                if response_obj.code == 402:
                    raise ValueError(response_obj.readableMessage or "Insufficient balance")
                    
                if not response_obj.data:
                    raise ValueError("Invalid response data")
                    
                logging.info("Read: %s", {
                    "title": response_obj.data.title,
                    "url": response_obj.data.url,
                    "tokens": response_obj.data.usage.get("tokens", 0) if response_obj.data.usage else 0
                })
                
                tokens = response_obj.data.usage.get("tokens", 0) if response_obj.data.usage else 0
                if tracker:
                    await tracker.track_usage("read", tokens)
                    
                return response_obj, tokens
                
            except httpx.HTTPError as e:
                logging.error("HTTP error in read_url: %s", str(e))
                raise
