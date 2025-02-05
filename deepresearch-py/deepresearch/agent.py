import asyncio
import uuid
from typing import Dict, AsyncGenerator, Any

import google.generativeai as genai

from .config import settings
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
        genai.configure(api_key=settings.GOOGLE_API_KEY)
        self.token_tracker = TokenTracker()
        self.action_tracker = ActionTracker()
        self.tasks: Dict[str, QueryResponse] = {}
        
        # Initialize tools
        self.search = JinaSearch() if settings.SEARCH_PROVIDER == "jina" else BraveSearch()
        self.reader = Reader()
        self.evaluator = Evaluator()
        self.error_analyzer = ErrorAnalyzer()
        self.query_rewriter = QueryRewriter()
        self.deduplicator = Deduplicator()

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

    async def _process_query(self, request_id: str, request: QueryRequest) -> None:
        task = self.tasks[request_id]
        try:
            # Query processing logic will be implemented here
            pass
        except Exception as e:
            task.status = "error"
            task.final_answer = str(e)
        else:
            task.status = "completed"
