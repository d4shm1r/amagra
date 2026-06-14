"""
routes/tools.py — run the agent tool loop over HTTP.

GET  /tools/list   the tools available right now (config gates applied)
POST /tools/run    drive the model through the tool loop for a prompt
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import tools.catalog as catalog
import tools.tool_loop as tool_loop

router = APIRouter(prefix="/tools", tags=["tools"])

_MAX_ITERS_CEILING = 5


class ToolRunRequest(BaseModel):
    prompt: str
    max_iters: int | None = None


def _llm_invoke(transcript):
    """Adapt a (role, content) transcript to the LangChain LLM and return text.

    Module-level so tests can monkeypatch it without a running model.
    """
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
    from models.llm import llm

    role_cls = {"system": SystemMessage, "assistant": AIMessage, "user": HumanMessage}
    msgs = [role_cls.get(role, HumanMessage)(content=content) for role, content in transcript]
    resp = llm.invoke(msgs)
    return getattr(resp, "content", str(resp))


@router.get("/list")
def list_tools():
    return {"tools": [
        {"name": n, "args": t["args"], "description": t["desc"]}
        for n, t in catalog.available_tools().items()
    ]}


@router.post("/run")
def run(req: ToolRunRequest):
    if not req.prompt or not req.prompt.strip():
        raise HTTPException(status_code=400, detail="prompt must not be empty")
    iters = req.max_iters or 3
    iters = max(1, min(iters, _MAX_ITERS_CEILING))
    try:
        return tool_loop.run_tool_loop(_llm_invoke, req.prompt, max_iters=iters)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
