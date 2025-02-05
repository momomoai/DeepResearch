import logging
from typing import Dict, Any, Optional, Tuple
import google.generativeai as genai

from ..config import settings, modelConfigs
from ..types import EvaluationResponse
from ..utils.token_tracker import TokenTracker

async def evaluate_answer(question: str, answer: str, tracker: Optional[TokenTracker] = None) -> Tuple[EvaluationResponse, int]:
    try:
        prompt = f"""You are an evaluator of answer definitiveness. Analyze if the given answer provides a definitive response or not.

Core Evaluation Criterion:
- Definitiveness: "I don't know", "lack of information", "doesn't exist", "not sure" or highly uncertain/ambiguous responses are **not** definitive, must return false!

Examples:

Question: "What are the system requirements for running Python 3.9?"
Answer: "I'm not entirely sure, but I think you need a computer with some RAM."
Evaluation: {{
  "is_definitive": false,
  "reasoning": "The answer contains uncertainty markers like 'not entirely sure' and 'I think', making it non-definitive."
}}

Question: "What are the system requirements for running Python 3.9?"
Answer: "Python 3.9 requires Windows 7 or later, macOS 10.11 or later, or Linux."
Evaluation: {{
  "is_definitive": true,
  "reasoning": "The answer makes clear, definitive statements without uncertainty markers or ambiguity."
}}

Question: "what is the twitter account of jina ai's founder?"
Answer: "The provided text does not contain the Twitter account of Jina AI's founder."
Evaluation: {{
  "is_definitive": false,
  "reasoning": "The answer indicates a lack of information rather than providing a definitive response."
}}

Now evaluate this pair:
Question: {question}
Answer: {answer}"""

        model = genai.GenerativeModel(
            model=modelConfigs["evaluator"]["model"],
            generation_config={
                "temperature": modelConfigs["evaluator"]["temperature"],
                "response_mime_type": "application/json",
                "response_schema": {
                    "type": "object",
                    "properties": {
                        "is_definitive": {
                            "type": "boolean",
                            "description": "Whether the answer provides a definitive response without uncertainty or 'I don't know' type statements"
                        },
                        "reasoning": {
                            "type": "string",
                            "description": "Explanation of why the answer is or isn't definitive"
                        }
                    },
                    "required": ["is_definitive", "reasoning"]
                }
            }
        )
        
        result = await model.generate_content_async(prompt)
        response = result.response
        usage = response.usage_metadata
        json_data = response.json()
        
        logging.info("Evaluation: %s", {
            "definitive": json_data["is_definitive"],
            "reason": json_data["reasoning"]
        })
        
        tokens = usage.total_token_count if usage else 0
        if tracker:
            await tracker.track_usage("evaluator", tokens)
            
        return EvaluationResponse(**json_data), tokens
        
    except Exception as e:
        logging.error("Error in answer evaluation: %s", str(e))
        raise
