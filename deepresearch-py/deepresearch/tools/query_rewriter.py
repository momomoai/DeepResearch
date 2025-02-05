import logging
from typing import Dict, Any, Optional, Tuple, List
import google.generativeai as genai

from ..config import settings, modelConfigs
from ..types import KeywordsResponse, SearchAction
from ..utils.token_tracker import TokenTracker

async def rewrite_query(action: SearchAction, tracker: Optional[TokenTracker] = None) -> Tuple[List[str], int]:
    try:
        prompt = f"""You are an expert Information Retrieval Assistant. Transform user queries into precise keyword combinations with strategic reasoning and appropriate search operators.

<rules>
1. Generate search queries that directly include appropriate operators
2. Keep base keywords minimal: 2-3 words preferred
3. Use exact match quotes for specific phrases that must stay together
4. Split queries only when necessary for distinctly different aspects
5. Preserve crucial qualifiers while removing fluff words
6. Make the query resistant to SEO manipulation
7. When necessary, append <query-operators> at the end only when must needed

<query-operators>
A query can't only have operators; and operators can't be at the start a query;

- "phrase" : exact match for phrases
- +term : must include term; for critical terms that must appear
- -term : exclude term; exclude irrelevant or ambiguous terms
- filetype:pdf/doc : specific file type
- site:example.com : limit to specific site
- lang:xx : language filter (ISO 639-1 code)
- loc:xx : location filter (ISO 3166-1 code)
- intitle:term : term must be in title
- inbody:term : term must be in body text
</query-operators>

Now, process this query:
Input Query: {action.searchQuery}
Intention: {action.think}"""

        model = genai.GenerativeModel(
            model=modelConfigs["queryRewriter"]["model"],
            generation_config={
                "temperature": modelConfigs["queryRewriter"]["temperature"],
                "response_mime_type": "application/json",
                "response_schema": {
                    "type": "object",
                    "properties": {
                        "think": {
                            "type": "string",
                            "description": "Strategic reasoning about query complexity and search approach"
                        },
                        "queries": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "description": "Search query, must be less than 30 characters"
                            },
                            "description": "Array of search queries, orthogonal to each other",
                            "minItems": 1,
                            "maxItems": 3
                        }
                    },
                    "required": ["think", "queries"]
                }
            }
        )
        
        result = await model.generate_content_async(prompt)
        response = result.response
        usage = response.usage_metadata
        json_data = response.json()
        
        logging.info("Query rewriter: %s", json_data["queries"])
        
        tokens = usage.total_token_count if usage else 0
        if tracker:
            await tracker.track_usage("query-rewriter", tokens)
            
        return json_data["queries"], tokens
        
    except Exception as e:
        logging.error("Error in query rewriting: %s", str(e))
        raise
