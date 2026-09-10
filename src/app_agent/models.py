"""Pydantic request/response models for the Sentiva agent API."""
from pydantic import BaseModel, Field
from typing import List


class ChatRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)


class Source(BaseModel):
    title: str
    source_uri: str
    product: str
    lang: str


class Timings(BaseModel):
    retrieval_ms: float
    llm_ms: float
    total_ms: float


class ChatResponse(BaseModel):
    answer: str
    sources: List[Source] = []
    timings: Timings
    trace_id: str = ""
