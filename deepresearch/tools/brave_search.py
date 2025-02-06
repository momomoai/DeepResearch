import logging
from typing import Dict, Any, Optional, Tuple, List
import httpx

from ..config import settings
from ..types import BraveSearchResponse
from ..utils.token_tracker import TokenTracker

class BraveSearch:
    @staticmethod
    async def search(query: str, tracker: Optional[TokenTracker] = None) -> Tuple[BraveSearchResponse, int]:
        try:
            headers = {
                "Accept": "application/json",
                "X-Subscription-Token": settings.BRAVE_API_KEY
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.search.brave.com/res/v1/web/search",
                    headers=headers,
                    params={"q": query}
                )
                response_data = response.json()
                response_obj = BraveSearchResponse(**response_data)
                
                logging.info("Brave search: %s", {
                    "query": query,
                    "results": len(response_obj.web.get("results", [])) if response_obj.web else 0
                })
                
                # Brave doesn't provide token usage, estimate based on response size
                tokens = len(str(response_data)) // 4  # Rough estimate
                if tracker:
                    await tracker.track_usage("brave-search", tokens)
                    
                return response_obj, tokens
                
        except httpx.HTTPError as e:
            logging.error("HTTP error in Brave search: %s", str(e))
            raise
