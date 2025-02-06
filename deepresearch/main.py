import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, AsyncGenerator, Any

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
trackers: Dict[str, Dict[str, Any]] = {}

def create_progress_message(request_id: str, budget: Optional[int] = None) -> StreamMessage:
    """创建进度消息。
    
    Args:
        request_id (str): 请求 ID
        budget (Optional[int]): token 预算限制，默认为 None
    
    Returns:
        StreamMessage: 包含进度信息的消息对象，包括：
            - 当前步骤信息
            - 总步骤数
            - 预算使用情况
    """
    context = trackers[request_id]
    token_tracker = context["token_tracker"]
    action_tracker = context["action_tracker"]
    
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
    """存储任务结果到文件系统。
    
    Args:
        request_id (str): 请求 ID
        result (StepAction): 任务结果对象
    
    Note:
        - 在当前工作目录下创建 tasks 目录
        - 以 JSON 格式保存结果
        - 文件名为 {request_id}.json
    """
    task_dir = Path.cwd() / "tasks"
    task_dir.mkdir(exist_ok=True)
    
    task_path = task_dir / f"{request_id}.json"
    task_path.write_text(json.dumps(result.model_dump(), indent=2))

@app.post("/api/v1/query")
async def query(request: QueryBody) -> Dict[str, str]:
    """处理查询请求的入口接口。
    
    Args:
        request (QueryBody): 查询请求体，包含：
            - q (str): 必填，查询字符串
            - budget (Optional[int]): 可选，token 预算限制
            - maxBadAttempt (Optional[int]): 可选，最大失败尝试次数
    
    Returns:
        Dict[str, str]: 包含请求 ID 的字典，格式为 {"requestId": "<timestamp>"}
    
    Raises:
        HTTPException: 当查询字符串为空时抛出 400 错误
    
    Note:
        - 生成基于时间戳的唯一请求 ID
        - 为每个请求创建 token 和 action 追踪器
        - 异步启动查询处理任务
    """
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
    """处理实时流式事件的接口。
    
    Args:
        request_id (str): 请求 ID，由 query 接口生成
        request (Request): FastAPI 请求对象
    
    Returns:
        EventSourceResponse: SSE 事件流响应
    
    Raises:
        HTTPException: 当请求 ID 无效时抛出 404 错误
    
    Note:
        - 建立 SSE 连接后发送初始确认消息
        - 流式返回处理过程中的事件
        - 支持客户端断开连接检测
        - 发生错误时返回错误信息和追踪器状态
        - 完成后自动清理追踪器资源
    """
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
                if isinstance(event, dict):
                    yield {"data": event}
                else:
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
    """获取指定任务的完整结果。
    
    Args:
        request_id (str): 请求 ID，由 query 接口生成
    
    Returns:
        Dict: 任务的完整结果数据
    
    Raises:
        HTTPException: 当任务文件不存在时抛出 404 错误
    
    Note:
        - 从本地文件系统读取任务结果
        - 结果以 JSON 格式存储在 tasks 目录下
    """
    task_path = Path.cwd() / "tasks" / f"{request_id}.json"
    try:
        return json.loads(task_path.read_text())
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Task not found")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m deepresearch.main 'your query'")
        sys.exit(1)
    
    query = sys.argv[1]
    agent = Agent()
    request_id = str(int(datetime.now().timestamp() * 1000))
    
    token_tracker = TokenTracker()
    action_tracker = ActionTracker()
    
    async def process_and_stream():
        process_task = asyncio.create_task(agent.process_query(
            request_id=request_id,
            query=query,
            token_tracker=token_tracker,
            action_tracker=action_tracker
        ))
        
        async for event in agent.stream_events(request_id):
            if isinstance(event, dict):
                print(json.dumps(event, indent=2))
            else:
                print(json.dumps(event.model_dump(), indent=2))
        
        await process_task
    
    asyncio.run(process_and_stream())
