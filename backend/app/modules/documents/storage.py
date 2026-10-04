"""Lab Manual Document Storage Service.

Provides safe, sandboxed file storage on the local filesystem with:
- Server-generated safe filenames (UUID-based).
- Path traversal prevention and sandboxing.
- Streaming chunked I/O with hard byte-limit enforcement.
- Magic byte file signature validation (PDF and DOCX).
- Automatic cleanup of partial files on failure.
"""

from dataclasses import dataclass
import logging
import os
from pathlib import Path
import re
from typing import Optional
import uuid
import zipfile

from fastapi import HTTPException, UploadFile, status

from app.core.config import settings

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS: set[str] = {".pdf", ".docx"}

MIME_TYPE_MAP: dict[str, str] = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

PDF_MAGIC: bytes = b"%PDF-"
DOCX_MAGIC: bytes = b"PK\x03\x04"


@dataclass(frozen=True)
class StoredDocumentInfo:
    """Metadata resulting from a safely stored upload."""

    storage_path: str
    file_size_bytes: int
    original_filename: str
    mime_type: str
    absolute_path: Path


class DocumentStorageService:
    """Handles sandboxed local filesystem persistence for uploaded manual documents."""

    def __init__(self, base_dir: Optional[Path | str] = None) -> None:
        if base_dir is None:
            self._base_dir = Path(settings.UPLOAD_DIR).resolve()
        else:
            self._base_dir = Path(base_dir).resolve()
        self._base_dir.mkdir(parents=True, exist_ok=True)

    @property
    def base_dir(self) -> Path:
        """Return the base storage directory."""
        return self._base_dir

    def sanitize_filename(self, filename: Optional[str]) -> str:
        """Strip directory paths and dangerous characters from user filename."""
        if not filename:
            return "uploaded_manual.pdf"
        # Extract base filename ignoring any leading path
        clean_name = os.path.basename(filename).strip()
        # Remove null bytes and control chars
        clean_name = re.sub(r"[\x00-\x1f\x7f]", "", clean_name)
        return clean_name or "uploaded_manual.pdf"

    def _validate_extension(self, filename: str) -> str:
        """Validate and return normalized lowercase extension."""
        ext = Path(filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"Unsupported file format '{ext}'. Only PDF (.pdf) and Word (.docx) documents are supported.",
            )
        return ext

    def _validate_signature(self, first_chunk: bytes, extension: str, dest_path: Path) -> None:
        """Inspect file header signature to reject extension/content mismatches."""
        if extension == ".pdf":
            # PDF magic signature %PDF- should appear in the first 1024 bytes
            if PDF_MAGIC not in first_chunk[:1024]:
                raise HTTPException(
                    status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                    detail="Invalid PDF file. The file content does not match the PDF format signature.",
                )
        elif extension == ".docx":
            # DOCX is a zip package starting with PK\x03\x04
            if not first_chunk.startswith(DOCX_MAGIC):
                raise HTTPException(
                    status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                    detail="Invalid DOCX file. The file content does not match the DOCX format signature.",
                )

    async def save_upload_file(
        self,
        file: UploadFile,
        user_id: uuid.UUID,
        experiment_id: uuid.UUID,
        max_size_bytes: Optional[int] = None,
    ) -> StoredDocumentInfo:
        """Safely stream an UploadFile to disk with validation and size capping.

        Raises:
            HTTPException(415): If extension or content signature is invalid.
            HTTPException(413): If file exceeds maximum allowed size.
            HTTPException(422): If file is empty (0 bytes).
        """
        max_bytes = max_size_bytes or settings.MAX_UPLOAD_SIZE_BYTES
        original_name = self.sanitize_filename(file.filename)
        extension = self._validate_extension(original_name)

        # Build sandboxed destination directory: base_dir / user_id / experiment_id
        dest_dir = (self._base_dir / str(user_id) / str(experiment_id)).resolve()
        # Verify no directory escape
        if not str(dest_dir).startswith(str(self._base_dir)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid storage path resolution.",
            )
        dest_dir.mkdir(parents=True, exist_ok=True)

        # Generate unique server-controlled filename
        unique_file_id = uuid.uuid4().hex
        stored_filename = f"{unique_file_id}{extension}"
        dest_path = (dest_dir / stored_filename).resolve()

        if not str(dest_path).startswith(str(self._base_dir)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Path traversal detected.",
            )

        total_bytes = 0
        chunk_size = 64 * 1024  # 64 KB chunks
        first_chunk: Optional[bytes] = None

        try:
            # Rewind file pointer in case it was previously read
            await file.seek(0)

            with open(dest_path, "wb") as out_file:
                while True:
                    chunk = await file.read(chunk_size)
                    if not chunk:
                        break

                    if first_chunk is None:
                        first_chunk = chunk
                        # Validate magic bytes on first chunk before writing much data
                        self._validate_signature(first_chunk, extension, dest_path)

                    total_bytes += len(chunk)
                    if total_bytes > max_bytes:
                        raise HTTPException(
                            status_code=413,
                            detail=f"File exceeds maximum allowed size of {max_bytes} bytes ({max_bytes // (1024 * 1024)} MB).",
                        )

                    out_file.write(chunk)

            # Check for empty file
            if total_bytes == 0:
                raise HTTPException(
                    status_code=422,
                    detail="Uploaded file is empty (0 bytes).",
                )

            # Secondary deep validation for DOCX archive structure
            if extension == ".docx":
                try:
                    if not zipfile.is_zipfile(dest_path):
                        raise HTTPException(
                            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                            detail="Invalid DOCX file. File is not a valid OpenXML document archive.",
                        )
                except Exception as zip_err:
                    if isinstance(zip_err, HTTPException):
                        raise
                    raise HTTPException(
                        status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                        detail="Invalid DOCX file. File is not a valid OpenXML document archive.",
                    )

        except Exception:
            # Clean up partial/invalid file on disk
            if dest_path.exists():
                dest_path.unlink(missing_ok=True)
            raise

        # Relative path within storage directory
        relative_path = f"{user_id}/{experiment_id}/{stored_filename}"
        mime_type = MIME_TYPE_MAP.get(extension, "application/octet-stream")

        return StoredDocumentInfo(
            storage_path=relative_path,
            file_size_bytes=total_bytes,
            original_filename=original_name,
            mime_type=mime_type,
            absolute_path=dest_path,
        )

    def delete_file(self, relative_storage_path: Optional[str]) -> bool:
        """Safely delete a stored file if it exists within the storage base directory."""
        if not relative_storage_path:
            return False
        try:
            target_path = (self._base_dir / relative_storage_path).resolve()
            if not str(target_path).startswith(str(self._base_dir)):
                return False
            if target_path.is_file():
                target_path.unlink(missing_ok=True)
                return True
        except Exception:
            pass
        return False

    def get_file_path(self, relative_storage_path: str) -> Optional[Path]:
        """Resolve a relative storage path safely, returning None if outside sandbox or missing."""
        try:
            target_path = (self._base_dir / relative_storage_path).resolve()
            if not str(target_path).startswith(str(self._base_dir)):
                return None
            if target_path.is_file():
                return target_path
        except Exception:
            pass
        return None

    def cleanup_user_files(
        self,
        user_id: uuid.UUID,
        storage_paths: list[str],
    ) -> int:
        """Safely delete all stored manual files belonging to a user.

        Identifies, sandboxes, and removes physical files associated with a student account.

        Guarantees:
        - Strict path validation: files must resolve within self._base_dir and the designated
          user directory (self._base_dir / str(user_id)).
        - Path traversal prevention: references attempting to escape the storage root or user directory
          are rejected and never deleted.
        - Missing file safety: already deleted or missing files are safely ignored without error.
        - Permission/OS error propagation: if an existing file cannot be deleted due to permission
          or OS errors, raises an explicit OSError/PermissionError so the caller can abort database
          commit and prevent partial/inconsistent cleanup.
        - Directory cleanup: removes empty experiment subdirectories and the user directory itself.
        - Does not expose absolute filesystem paths in error messages or logs.

        Args:
            user_id: The UUID of the user owning the files.
            storage_paths: List of relative storage paths gathered from database records.

        Returns:
            The count of physical files actually unlinked from the filesystem.

        Raises:
            PermissionError: If file permissions prevent unlinking an existing file.
            OSError: If an operating system error prevents unlinking an existing file.
        """
        user_id_str = str(user_id)
        user_dir = (self._base_dir / user_id_str).resolve()

        # Validate that user_dir is within base_dir sandbox
        if not str(user_dir).startswith(str(self._base_dir)):
            logger.error("User storage path traversal detected for user_id=%s", user_id_str)
            raise ValueError("Invalid user storage directory resolution.")

        deleted_count = 0
        for raw_path in storage_paths:
            if not raw_path or not isinstance(raw_path, str):
                continue

            # Strip leading slashes to prevent Path root escaping
            clean_rel = raw_path.lstrip("/\\")
            try:
                target_path = (self._base_dir / clean_rel).resolve()
            except Exception as resolve_err:
                logger.warning(
                    "Could not resolve file path for user %s: %s",
                    user_id_str,
                    resolve_err,
                )
                continue

            # Enforce storage root boundary
            if not str(target_path).startswith(str(self._base_dir)):
                logger.warning(
                    "Path traversal attempt blocked: path outside base directory for user %s",
                    user_id_str,
                )
                continue

            # Enforce user boundary: file must reside within user_dir
            if not str(target_path).startswith(str(user_dir)):
                logger.warning(
                    "Cross-user path deletion attempt blocked for user %s",
                    user_id_str,
                )
                continue

            if target_path.is_file():
                try:
                    target_path.unlink()
                    deleted_count += 1
                except FileNotFoundError:
                    # Missing file is completely safe
                    pass
                except (PermissionError, OSError) as err:
                    logger.error(
                        "Failed to delete stored file '%s' for user %s: %s",
                        target_path.name,
                        user_id_str,
                        type(err).__name__,
                    )
                    raise

        # Prune empty subdirectories and user directory
        if user_dir.is_dir() and str(user_dir).startswith(str(self._base_dir)):
            try:
                for root, dirs, files in os.walk(user_dir, topdown=False):
                    for d in dirs:
                        dir_path = Path(root) / d
                        try:
                            dir_path.rmdir()
                        except OSError:
                            pass
                user_dir.rmdir()
            except OSError:
                pass

        return deleted_count


# Global storage service instance
default_storage_service = DocumentStorageService()


def get_storage_service() -> DocumentStorageService:
    """FastAPI dependency provider for DocumentStorageService."""
    return default_storage_service
