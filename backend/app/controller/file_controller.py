import os
from fastapi import UploadFile
import re
from uuid import UUID

from app.enums import FileResponse
from app.core.config import get_settings

class FileController:
    """Controller for handling file-related operations, including file uploads and directory management."""

    settings = get_settings()
    ALLOWED_EXTENSIONS = {".pdf", ".docx"}

    @classmethod
    def _get_file_upload_dir(cls) -> str:
        """Get the file upload directory path relative to the project root."""
        current_file_path = os.path.abspath(__file__)
        parent_dir = os.path.dirname(current_file_path)
        # Move up two levels to reach project root
        for _ in range(2):
            parent_dir = os.path.dirname(parent_dir)
        file_upload_dir = os.path.join(parent_dir, cls.settings.FILE_UPLOAD_DIR)
        return file_upload_dir

    @classmethod
    def make_user_directory(cls, user_id: UUID) -> str:
        """Create and return a user-specific directory path."""
        files_dir = cls._get_file_upload_dir()
        user_dir_path = os.path.join(files_dir, str(user_id))
        cls._make_directory_if_not_exists(user_dir_path)
        return user_dir_path

    @classmethod
    def _make_directory_if_not_exists(cls, directory: str) -> None:
        """Create a directory if it doesn't already exist."""
        if not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)

    @classmethod
    def file_exists(cls, file_path: str) -> bool:
        """Check if a file exists in a user's directory."""
        return os.path.isfile(file_path)

    @classmethod
    def ensure_upload_directory_exists(cls) -> None:
        """Ensure the root file upload directory exists."""
        files_dir = cls._get_file_upload_dir()
        cls._make_directory_if_not_exists(files_dir)

    @classmethod
    def get_file_extension(cls, filename: str) -> str:
        """Get the file extension from a filename."""
        _, ext = os.path.splitext(filename)
        return ext.lower()

    @classmethod
    def get_clean_filename(cls, original_filename: str) -> str:
        cleaned_filename = re.sub(r"[^\w.\s-]", "", original_filename.strip())
        return re.sub(r"\s+", "_", cleaned_filename)

    @classmethod
    def generate_file_path_and_make_user_directory(cls, user_id: UUID, filename: str, resume_id: UUID) -> str:
        """Generate a file path for a given user, filename, and interview ID."""

        full_filename = f"{resume_id}_{filename}"
        cleaned_filename = cls.get_clean_filename(full_filename)
        user_dir = cls.make_user_directory(user_id)
        file_path = os.path.join(user_dir, cleaned_filename)
        return file_path
    
    @classmethod
    def validate_uploaded_file(cls, file: UploadFile) -> tuple[bool, str]:
        """Validate the uploaded file's type and size against the application settings."""    
        if not file.filename:
            return False, FileResponse.FILE_TYPE_NOT_SUPPORTED.value

        file_extension = cls.get_file_extension(file.filename)
        if file_extension not in cls.ALLOWED_EXTENSIONS:
            return False, FileResponse.FILE_TYPE_NOT_SUPPORTED.value

        if file.content_type not in cls.settings.FILE_ALLOWED_TYPES:
            return False, FileResponse.FILE_TYPE_NOT_SUPPORTED.value

        max_size_bytes = cls.settings.FILE_ALLOWED_SIZE_MB * 1024 * 1024
        if file.size is not None and file.size > max_size_bytes:
            return False, FileResponse.FILE_SIZE_EXCEEDED.value

        return True, FileResponse.FILE_VALIDATION_SUCCESS.value
        