import json
import logging
from typing import Dict, Any, Optional, Tuple, List
import google.generativeai as genai
from google.generativeai.types import GenerateContentResponse, PromptFeedback

from ..config import settings, modelConfigs
from ..types import ErrorAnalysisResponse
from ..utils.token_tracker import TokenTracker

async def analyze_steps(diary_context: List[str], tracker: Optional[TokenTracker] = None) -> Tuple[ErrorAnalysisResponse, int]:
    try:
        prompt = f"""You are an expert at analyzing search and reasoning processes. Your task is to analyze the given sequence of steps and identify what went wrong in the search process.

<rules>
1. The sequence of actions taken
2. The effectiveness of each step
3. The logic between consecutive steps
4. Alternative approaches that could have been taken
5. Signs of getting stuck in repetitive patterns
6. Whether the final answer matches the accumulated information

Analyze the steps and provide detailed feedback following these guidelines:
- In the recap: Summarize key actions chronologically, highlight patterns, and identify where the process started to go wrong
- In the blame: Point to specific steps or patterns that led to the inadequate answer
- In the improvement: Provide actionable suggestions that could have led to a better outcome
</rules>

{diary_context}"""

        model = genai.GenerativeModel(
            model_name=modelConfigs["errorAnalyzer"]["model"],
            generation_config={
                "temperature": modelConfigs["errorAnalyzer"]["temperature"],
                "response_mime_type": "application/json",
                "response_schema": {
                    "type": "object",
                    "properties": {
                        "recap": {
                            "type": "string",
                            "description": "Recap of the actions taken and the steps conducted"
                        },
                        "blame": {
                            "type": "string",
                            "description": "Which action or the step was the root cause of the answer rejection"
                        },
                        "improvement": {
                            "type": "string",
                            "description": "Suggested key improvement for the next iteration, do not use bullet points, be concise and hot-take vibe."
                        }
                    },
                    "required": ["recap", "blame", "improvement"]
                }
            }
        )
        
        response = await model.generate_content_async(prompt)
        usage = response.prompt_feedback
        try:
            json_data = json.loads(response.text)
        except json.JSONDecodeError as e:
            logging.error("JSON decode error: %s", str(e))
            raise
            
        logging.info("Error analysis: %s", {
            "is_valid": not json_data["blame"],
            "reason": json_data["blame"] or "No issues found"
        })
        
        tokens = usage.total_token_count if usage else 0
        if tracker:
            await tracker.track_usage("error-analyzer", tokens)
            
        return ErrorAnalysisResponse(**json_data), tokens
        
    except Exception as e:
        logging.error("Error in error analysis: %s", str(e))
        raise
