from enum import Enum
from typing import List, Optional, Dict, Any, Union, Literal
from pydantic import BaseModel, Field

class ActionType(str, Enum):
    SEARCH = "search"
    ANSWER = "answer"
    REFLECT = "reflect"
    VISIT = "visit"

class BaseAction(BaseModel):
    action: ActionType
    think: str

class SearchAction(BaseAction):
    action: Literal[ActionType.SEARCH] = ActionType.SEARCH
    searchQuery: str

class Reference(BaseModel):
    exactQuote: str
    url: str

class AnswerAction(BaseAction):
    action: Literal[ActionType.ANSWER] = ActionType.ANSWER
    answer: str
    references: List[Reference]

class ReflectAction(BaseAction):
    action: Literal[ActionType.REFLECT] = ActionType.REFLECT
    questionsToAnswer: List[str]

class VisitAction(BaseAction):
    action: Literal[ActionType.VISIT] = ActionType.VISIT
    URLTargets: List[str]

StepAction = Union[SearchAction, AnswerAction, ReflectAction, VisitAction]

class TokenUsage(BaseModel):
    tool: str
    tokens: int

class SearchResult(BaseModel):
    title: str
    description: str
    url: str
    content: str
    usage: Dict[str, int]

class SearchResponse(BaseModel):
    code: int
    status: int
    data: Optional[List[SearchResult]] = None
    name: Optional[str] = None
    message: Optional[str] = None
    readableMessage: Optional[str] = None

class BraveSearchResult(BaseModel):
    title: str
    description: str
    url: str

class BraveSearchResponse(BaseModel):
    web: Dict[str, List[BraveSearchResult]]

class DedupResponse(BaseModel):
    think: str
    unique_queries: List[str]

class ReadResponse(BaseModel):
    code: int
    status: int
    data: Optional[SearchResult] = None
    name: Optional[str] = None
    message: Optional[str] = None
    readableMessage: Optional[str] = None

class EvaluationResponse(BaseModel):
    is_definitive: bool
    reasoning: str

class ErrorAnalysisResponse(BaseModel):
    recap: str
    blame: str
    improvement: str

class SearchResultBase(BaseModel):
    title: str
    url: str
    description: str

class QueryResult(BaseModel):
    query: str
    results: List[SearchResultBase]

class StepData(BaseModel):
    step: int
    question: str
    action: str
    reasoning: str
    searchQuery: Optional[str] = None
    result: Optional[List[QueryResult]] = None

class KeywordsResponse(BaseModel):
    think: str
    queries: List[str]

class SchemaProperty(BaseModel):
    type: str
    description: str
    enum: Optional[List[str]] = None
    items: Optional[Dict[str, Any]] = None
    properties: Optional[Dict[str, 'SchemaProperty']] = None
    required: Optional[List[str]] = None
    maxItems: Optional[int] = None

class ResponseSchema(BaseModel):
    type: str
    properties: Dict[str, SchemaProperty]
    required: List[str]

class StreamMessage(BaseModel):
    type: Literal["progress", "answer", "error"]
    data: Union[str, StepAction]
    step: Optional[int] = None
    budget: Optional[Dict[str, Union[int, str]]] = Field(
        None,
        description="Budget information with used, total, and percentage"
    )

class QueryRequest(BaseModel):
    query: str
    context: Optional[Dict[str, Any]] = None

class QueryResponse(BaseModel):
    request_id: str
    status: str
    actions: List[BaseAction]
    final_answer: Optional[str] = None
