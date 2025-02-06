import asyncio
import uuid
from typing import Dict, AsyncGenerator, Any, Optional, Union

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion

from .config import settings, modelConfigs
from .types import QueryRequest, QueryResponse, BaseAction
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
            raise ValueError("Invalid request ID")
            
        task = self.tasks[request_id]
        last_action_count = 0
        
        while task.status == "running":
            if len(task.actions) > last_action_count:
                for action in task.actions[last_action_count:]:
                    yield {"data": action.model_dump()}
                last_action_count = len(task.actions)
            await asyncio.sleep(settings.STEP_SLEEP / 1000)

        if task.final_answer:
            yield {"data": {"type": "final", "answer": task.final_answer}}

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
        task = self.tasks[request_id]
        try:
            if token_tracker:
                self.token_tracker = token_tracker
            if action_tracker:
                self.action_tracker = action_tracker
                
            # Process query using tools
            result = await self._process_query(request_id, QueryRequest(query=query))
            task.final_answer = result
            task.status = "completed"
        except Exception as e:
            task.status = "error"
            task.final_answer = str(e)
            
    async def _process_query(self, request_id: str, request: QueryRequest) -> str:
        task = self.tasks[request_id]
        try:
            # Initial query processing
            response = await self.client.chat.completions.create(
                model=modelConfigs["evaluator"]["model"],
                messages=[{"role": "user", "content": request.query}],
                temperature=modelConfigs["evaluator"]["temperature"]
            )
            return response.choices[0].message.content
        except Exception as e:
            task.status = "error"
            task.final_answer = str(e)
            raise
