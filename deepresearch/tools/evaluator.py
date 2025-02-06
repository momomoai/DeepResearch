import json
import logging
from typing import Dict, Any, Optional, Tuple

from openai import AsyncOpenAI

from ..config import settings, modelConfigs
from ..types import EvaluationResponse
from ..utils.token_tracker import TokenTracker

class Evaluator:
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    
    @staticmethod
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

            response = await Evaluator.client.chat.completions.create(
                model=modelConfigs["evaluator"]["model"],
                temperature=modelConfigs["evaluator"]["temperature"],
                functions=[{
                    "name": "evaluate_answer",
                    "parameters": {
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
                }],
                messages=[{"role": "user", "content": prompt}]
            )
            
            try:
                json_data = json.loads(response.choices[0].message.function_call.arguments)
            except (json.JSONDecodeError, AttributeError) as e:
                logging.error("JSON decode error: %s", str(e))
                raise
                
            logging.info("Evaluation: %s", {
                "definitive": json_data["is_definitive"],
                "reason": json_data["reasoning"]
            })
            
            if tracker:
                await tracker.track_usage("evaluator", response)
                    
            return EvaluationResponse(**json_data), response.usage.total_tokens
                
        except Exception as e:
            logging.error("Error in answer evaluation: %s", str(e))
            raise
