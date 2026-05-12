from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from app.core.deps import get_current_user

router = APIRouter(prefix="/stream", tags=["stream"])


@router.get("/task/{task_id}")
def task_stream(task_id: int, user=Depends(get_current_user)):
    def event_gen():
        yield "data: task stream placeholder\n\n"
    return StreamingResponse(event_gen(), media_type="text/event-stream")
