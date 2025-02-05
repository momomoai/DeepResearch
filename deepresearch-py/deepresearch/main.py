import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, AsyncGenerator

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel

from .agent import Agent
from .types import QueryRequest, StreamMessage, StepAction
from .utils.token_tracker import TokenTracker
from .utils.action_tracker import ActionTracker

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class QueryBody(BaseModel):
    q: str
    budget: Optional[int] = None
    maxBadAttempt: Optional[int] = None

# Store trackers for each request
trackers: Dict[str, Dict[str, TokenTracker | ActionTracker]] = {}

def create_progress_message(request_id: str, budget: Optional[int] = None) -> StreamMessage:
    context = trackers[request_id]
    token_tracker: TokenTracker = context["token_tracker"]
    action_tracker: ActionTracker = context["action_tracker"]
    
    state = action_tracker.get_state()
    budget_info = {
        "used": token_tracker.get_total_usage(),
        "total": budget or 1_000_000,
        "percentage": f"{(token_tracker.get_total_usage() / (budget or 1_000_000)) * 100:.2f}"
    }
    
    return StreamMessage(
        type="progress",
        data=state["this_step"],
        step=state["total_step"],
        budget=budget_info
    )

async def store_task_result(request_id: str, result: StepAction) -> None:
    task_dir = Path.cwd() / "tasks"
    task_dir.mkdir(exist_ok=True)
    
    task_path = task_dir / f"{request_id}.json"
    task_path.write_text(json.dumps(result.model_dump(), indent=2))

@app.post("/api/v1/query")
async def query(request: QueryBody) -> Dict[str, str]:
    if not request.q:
        raise HTTPException(status_code=400, detail="Query (q) is required")
    
    request_id = str(int(datetime.now().timestamp() * 1000))
    
    # Create new trackers for this request
    trackers[request_id] = {
        "token_tracker": TokenTracker(request.budget),
        "action_tracker": ActionTracker()
    }
    
    # Start query processing in background
    agent = Agent()
    asyncio.create_task(agent.process_query(
        request_id=request_id,
        query=request.q,
        budget=request.budget,
        max_bad_attempt=request.maxBadAttempt,
        token_tracker=trackers[request_id]["token_tracker"],
        action_tracker=trackers[request_id]["action_tracker"]
    ))
    
    return {"requestId": request_id}

@app.get("/api/v1/stream/{request_id}")
async def stream(request_id: str, request: Request) -> EventSourceResponse:
    if request_id not in trackers:
        raise HTTPException(status_code=404, detail="Invalid request ID")
    
    async def event_generator() -> AsyncGenerator[Dict, None]:
        try:
            # Send initial connection confirmation
            yield {
                "event": "connected",
                "data": {
                    "requestId": request_id,
                    "trackers": {
                        "tokenUsage": trackers[request_id]["token_tracker"].get_total_usage(),
                        "actionState": trackers[request_id]["action_tracker"].get_state()
                    }
                }
            }
            
            agent = Agent()
            async for event in agent.stream_events(request_id):
                if await request.is_disconnected():
                    break
                yield {"data": event.model_dump()}
                
        except Exception as e:
            yield {
                "event": "error",
                "data": {
                    "message": str(e),
                    "trackers": {
                        "tokenUsage": trackers[request_id]["token_tracker"].get_total_usage(),
                        "actionState": trackers[request_id]["action_tracker"].get_state()
                    }
                }
            }
        finally:
            if request_id in trackers:
                del trackers[request_id]
    
    return EventSourceResponse(event_generator())

@app.get("/api/v1/task/{request_id}")
async def get_task(request_id: str) -> Dict:
    task_path = Path.cwd() / "tasks" / f"{request_id}.json"
    try:
        return json.loads(task_path.read_text())
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Task not found")
