import asyncio
from typing import Union

from fastapi import APIRouter, Depends, BackgroundTasks, Request, HTTPException
from fastapi.responses import StreamingResponse

from knowledge.schema.query_schema import QueryRequest, StreamSubmitResponse, QueryResponse
from knowledge.core.deps import get_query_service
from knowledge.service.query_service import QueryService
from knowledge.utils.sse_util import create_sse_queue, sse_generator

router = APIRouter()


@router.post("/query")
async def query(
    request: QueryRequest,
    background_tasks: BackgroundTasks,
    service: QueryService = Depends(get_query_service),
) -> Union[StreamSubmitResponse, QueryResponse]:
    session_id = request.session_id or service.generate_session_id()
    task_id = service.generate_task_id()

    if request.is_stream:
        create_sse_queue(task_id=task_id)
        background_tasks.add_task(
            service.run_query_graph,
            session_id=session_id,
            task_id=task_id,
            query=request.query,
            is_stream=request.is_stream,
            image=request.image,
            image_mime=request.image_mime,
            top_k=request.top_k,
        )
        return StreamSubmitResponse(message="查询请求已经提交", session_id=session_id, task_id=task_id)

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None,
        service.run_query_graph,
        session_id,
        task_id,
        request.query,
        request.is_stream,
        request.image,
        request.image_mime,
        request.top_k,
    )
    answer = service.get_task_result(task_id)
    return QueryResponse(message="查询请求已经处理完了", session_id=session_id, answer=answer)


@router.get("/stream/{task_id}")
async def stream(task_id: str, request: Request) -> StreamingResponse:
    return StreamingResponse(content=sse_generator(task_id, request), media_type="text/event-stream")


@router.get("/history/{session_id}")
async def get_history(
    session_id: str,
    limit: int = 50,
    service: QueryService = Depends(get_query_service),
):
    try:
        items = service.get_history(session_id, limit)
        return {"session_id": session_id, "items": items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"history error: {e}")


@router.delete("/history/{session_id}")
async def clear_chat_history(
    session_id: str,
    service: QueryService = Depends(get_query_service),
):
    count = service.clear_history(session_id)
    return {"message": "History cleared", "deleted_count": count}
