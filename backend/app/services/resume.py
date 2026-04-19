import os

import aiofiles
from fastapi import UploadFile

from app.core.config import get_settings
from app.controller.file_controller import FileController
from app.core.loader import load_document
from app.db.resume_curd import create_resume
from app.schemas.resume import ResumeResponse
from uuid import UUID, uuid4
from sqlalchemy.orm import Session

settings = get_settings()

async def save_uploaded_file(upload_file: UploadFile, file_path: str, max_size_bytes: int) -> None:
    """Save an uploaded file to the specified file path asynchronously."""
    total_bytes = 0
    async with aiofiles.open(file_path, "wb") as out_file:
        while content := await upload_file.read(settings.FILE_DEFAULT_CHUNK_SIZE):  # Read in chunks
            total_bytes += len(content)
            if total_bytes > max_size_bytes:
                raise ValueError("File size exceeded the limit.")
            await out_file.write(content)


async def handle_resume_upload(db: Session, user_id: UUID, upload_file: UploadFile) -> ResumeResponse:
    """Handle the resume upload process, including validation, saving, and database record creation."""
    is_valid, validation_message = FileController.validate_uploaded_file(upload_file)
    if not is_valid:
        raise ValueError(validation_message)

    if not upload_file.filename:
        raise ValueError("Uploaded file must have a filename.")

    resume_id = uuid4()
    max_size_bytes = settings.FILE_ALLOWED_SIZE_MB * 1024 * 1024
    file_path = FileController.generate_file_path_and_make_user_directory(user_id, upload_file.filename, resume_id)
    try:
        await save_uploaded_file(upload_file, file_path, max_size_bytes)

        document = load_document(file_path)

        resume = create_resume(
            db=db,
            resume_id=resume_id,
            user_id=user_id,
            file_path=file_path,
            extracted_data=document,
        )
        return ResumeResponse.model_validate(resume)
    except ValueError:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise
    except Exception:
        db.rollback()
        if os.path.exists(file_path):
            os.remove(file_path)
        raise