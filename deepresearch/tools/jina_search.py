import logging
from typing import Dict, Any, Optional, Tuple, List
import httpx

from ..config import settings
from ..types import SearchResponse
from ..utils.token_tracker import TokenTracker

class JinaSearch:
    @staticmethod
    async def search(query: str, tracker: Optional[TokenTracker] = None) -> Tuple[SearchResponse, int]:
        try:
            headers = {
                "Accept": "application/json",
                "Authorization": f"Bearer {settings.JINA_API_KEY}",
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.jina.ai/v1/search",
                    headers=headers,
                    json={"query": query}
                )
                response_data = response.json()
                response_obj = SearchResponse(**response_data)
                
                if response_obj.code == 402:
                    raise ValueError(response_obj.readableMessage or "Insufficient balance")
                    
                if not response_obj.data:
                    raise ValueError("Invalid response data")
                    
                logging.info("Jina search: %s", {
                    "query": query,
                    "results": len(response_obj.data) if response_obj.data else 0
                })
                
                tokens = sum(result.usage.get("tokens", 0) for result in response_obj.data) if response_obj.data else 0
                if tracker:
                    await tracker.track_usage("jina-search", tokens)
                    
                return response_obj, tokens
                
        except httpx.HTTPError as e:
            logging.error("HTTP error in Jina search: %s", str(e))
            raise
