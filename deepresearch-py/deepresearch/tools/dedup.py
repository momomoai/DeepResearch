import logging
from typing import Dict, Any, Optional, Tuple, List
import google.generativeai as genai

from ..config import settings, modelConfigs
from ..types import DedupResponse
from ..utils.token_tracker import TokenTracker

async def dedup_queries(new_queries: List[str], existing_queries: List[str], tracker: Optional[TokenTracker] = None) -> Tuple[List[str], int]:
    try:
        prompt = f"""You are an expert in semantic similarity analysis. Given a set of queries (setA) and a set of queries (setB)

<rules>
Function FilterSetA(setA, setB, threshold):
    filteredA = empty set
    
    for each candidateQuery in setA:
        isValid = true
        
        // Check similarity with already accepted queries in filteredA
        for each acceptedQuery in filteredA:
            similarity = calculateSimilarity(candidateQuery, acceptedQuery)
            if similarity >= threshold:
                isValid = false
                break
        
        // If passed first check, compare with set B
        if isValid:
            for each queryB in setB:
                similarity = calculateSimilarity(candidateQuery, queryB)
                if similarity >= threshold:
                    isValid = false
                    break
        
        // If passed all checks, add to filtered set
        if isValid:
            add candidateQuery to filteredA
    
    return filteredA
</rules>    

<similarity-definition>
1. Consider semantic meaning and query intent, not just lexical similarity
2. Account for different phrasings of the same information need
3. Queries with same base keywords but different operators are NOT duplicates
4. Different aspects or perspectives of the same topic are not duplicates
5. Consider query specificity - a more specific query is not a duplicate of a general one
6. Search operators that make queries behave differently:
   - Different site: filters (e.g., site:youtube.com vs site:github.com)
   - Different file types (e.g., filetype:pdf vs filetype:doc)
   - Different language/location filters (e.g., lang:en vs lang:es)
   - Different exact match phrases (e.g., "exact phrase" vs no quotes)
   - Different inclusion/exclusion (+/- operators)
   - Different title/body filters (intitle: vs inbody:)
</similarity-definition>

Now with threshold set to 0.2; run FilterSetA on the following:
SetA: {new_queries}
SetB: {existing_queries}"""

        model = genai.GenerativeModel(
            model=modelConfigs["dedup"]["model"],
            generation_config={
                "temperature": modelConfigs["dedup"]["temperature"],
                "response_mime_type": "application/json",
                "response_schema": {
                    "type": "object",
                    "properties": {
                        "think": {
                            "type": "string",
                            "description": "Strategic reasoning about the overall deduplication approach"
                        },
                        "unique_queries": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "description": "Unique query that passed the deduplication process, must be less than 30 characters"
                            },
                            "description": "Array of semantically unique queries"
                        }
                    },
                    "required": ["think", "unique_queries"]
                }
            }
        )
        
        result = await model.generate_content_async(prompt)
        response = result.response
        usage = response.usage_metadata
        json_data = response.json()
        
        logging.info("Dedup: %s", json_data["unique_queries"])
        
        tokens = usage.total_token_count if usage else 0
        if tracker:
            await tracker.track_usage("dedup", tokens)
            
        return json_data["unique_queries"], tokens
        
    except Exception as e:
        logging.error("Error in deduplication analysis: %s", str(e))
        raise
