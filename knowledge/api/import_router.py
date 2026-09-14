from fastapi import APIRouter, UploadFile, Depends, BackgroundTasks

from knowledge.schema.upload_schema import UploadResponse, TaskStatusResponse
from knowledge.service.upload_service import UpLoadService
from knowledge.core.deps import get_upload_file_service
from knowledge.utils.task_util import get_task_info

router = APIRouter()


@router.post("/upload", response_model=UploadResponse)
def upload_endpoint(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    upload_service: UpLoadService = Depends(get_upload_file_service),
):
    task_id, import_file_path, file_dir = upload_service.process_upload_file(file)
    background_tasks.add_task(upload_service.run_import_graph, task_id, import_file_path, file_dir)
    return UploadResponse(message=f"{file.filename}文件上传成功", task_id=task_id)


@router.get("/status/{task_id}")
def get_task_status_endpoint(task_id: str):
    task_info = get_task_info(task_id)
    return TaskStatusResponse(**task_info)
