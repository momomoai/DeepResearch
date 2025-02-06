import asyncio
import uuid
from typing import Dict, AsyncGenerator, Any, Optional, Union

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion

from .config import settings, modelConfigs
from .types import (
    QueryRequest, QueryResponse, BaseAction,
    ActionType, SearchAction, AnswerAction,
    Reference, SearchResult
)
from .utils.token_tracker import TokenTracker
from .utils.action_tracker import ActionTracker
from .tools.jina_search import JinaSearch
from .tools.brave_search import BraveSearch
from .tools.read import Reader
from .tools.evaluator import Evaluator
from .tools.error_analyzer import ErrorAnalyzer
from .tools.query_rewriter import QueryRewriter
from .tools.dedup import Deduplicator

class Agent:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.token_tracker = TokenTracker()
        self.action_tracker = ActionTracker()
        self.tasks: Dict[str, QueryResponse] = {}
        
        # Initialize search function
        self.search = JinaSearch.search if settings.SEARCH_PROVIDER == "jina" else BraveSearch.search

    async def start_query(self, request: QueryRequest) -> str:
        request_id = str(uuid.uuid4())
        self.tasks[request_id] = QueryResponse(
            request_id=request_id,
            status="running",
            actions=[]
        )
        asyncio.create_task(self._process_query(request_id, request))
        return request_id

    async def stream_events(self, request_id: str) -> AsyncGenerator[Dict[str, Any], None]:
        if request_id not in self.tasks:
            self.tasks[request_id] = QueryResponse(
                request_id=request_id,
                status="running",
                actions=[]
            )
            
        task = self.tasks[request_id]
        last_action_count = 0
        
        # Send initial state
        yield {
            "type": "progress",
            "trackers": {
                "tokenUsage": self.token_tracker.get_total_usage(),
                "tokenBreakdown": self.token_tracker.get_usage_breakdown(),
                "actionState": {
                    "action": "search",
                    "think": "",
                    "URLTargets": [],
                    "answer": "",
                    "questionsToAnswer": [],
                    "references": [],
                    "searchQuery": ""
                },
                "step": 0,
                "badAttempts": 0,
                "gaps": []
            }
        }
        
        while task.status == "running":
            if len(task.actions) > last_action_count:
                for action in task.actions[last_action_count:]:
                    yield {
                        "type": "progress",
                        "trackers": {
                            "tokenUsage": self.token_tracker.get_total_usage(),
                            "tokenBreakdown": self.token_tracker.get_usage_breakdown(),
                            "actionState": action.model_dump(),
                            "step": len(task.actions),
                            "badAttempts": 0,
                            "gaps": []
                        }
                    }
                last_action_count = len(task.actions)
            await asyncio.sleep(settings.STEP_SLEEP / 1000)

        if task.final_answer:
            yield {
                "type": "final",
                "answer": task.final_answer,
                "trackers": {
                    "tokenUsage": self.token_tracker.get_total_usage(),
                    "tokenBreakdown": self.token_tracker.get_usage_breakdown()
                }
            }

    async def get_task(self, request_id: str) -> QueryResponse:
        if request_id not in self.tasks:
            raise ValueError("Invalid request ID")
        return self.tasks[request_id]

    async def process_query(
        self,
        request_id: str,
        query: str,
        budget: int | None = None,
        max_bad_attempt: int | None = None,
        token_tracker: TokenTracker | None = None,
        action_tracker: ActionTracker | None = None
    ) -> None:
        print(f"Starting process_query for request_id: {request_id}")
        if token_tracker:
            self.token_tracker = token_tracker
        if action_tracker:
            self.action_tracker = action_tracker

        self.tasks[request_id] = QueryResponse(
            request_id=request_id,
            status="running",
            actions=[]
        )
        task = self.tasks[request_id]
        try:
            print(f"Processing query: {query}")
            result = await self._process_query(request_id, QueryRequest(query=query))
            print(f"Got result: {result}")
            task.final_answer = result
            task.status = "completed"
            print("Query processing completed")
        except Exception as e:
            print(f"Error in process_query: {str(e)}")
            task.status = "error"
            task.final_answer = str(e)
            
    async def _process_query(self, request_id: str, request: QueryRequest) -> str:
        if request_id not in self.tasks:
            self.tasks[request_id] = QueryResponse(
                request_id=request_id,
                status="running",
                actions=[]
            )
        task = self.tasks[request_id]
        try:
            # Initial query processing
            response = await self.client.chat.completions.create(
                model=modelConfigs["evaluator"]["model"],
                messages=[{"role": "user", "content": request.query}],
                temperature=modelConfigs["evaluator"]["temperature"]
            )
            answer = response.choices[0].message.content
            
            # Add search action with token tracking
            search_action = SearchAction(
                action=ActionType.SEARCH,
                think=f"Searching to verify: {request.query}",
                searchQuery=request.query
            )
            task.actions.append(search_action)
            self.token_tracker.add_usage("agent", len(request.query))
            
            # Perform search
            search_response, search_tokens = await self.search(request.query, self.token_tracker)
            search_results = search_response.data if search_response.data else []
            
            # Add answer action
            answer_action = AnswerAction(
                action=ActionType.ANSWER,
                think="Based on the search results and verification",
                answer=answer,
                references=[Reference(exactQuote=result.content[:100], url=result.url) for result in search_results]
            )
            task.actions.append(answer_action)
            self.token_tracker.add_usage("agent", len(answer))
            
            task.final_answer = answer
            task.status = "completed"
            return answer
        except Exception as e:
            task.status = "error"
            task.final_answer = str(e)
            raise
