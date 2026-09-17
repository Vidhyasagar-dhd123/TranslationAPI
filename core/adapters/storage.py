"""
Storage Adapter for handling file uploads, paths, deletions, and storage size queries.
Implements the Adapter pattern with LocalStorageAdapter as the default.
"""
from abc import ABC, abstractmethod
import os
import shutil
from pathlib import Path
from django.conf import settings
from django.core.files.uploadedfile import UploadedFile


class StorageAdapterBase(ABC):
    @abstractmethod
    def save(self, tenant_id: int, file: UploadedFile, custom_filename: str = None) -> dict:
        """
        Saves the file for the given tenant.
        Returns dict with keys: 'file_path', 'file_name', 'file_size', 'relative_path'.
        """
        pass

    @abstractmethod
    def get_absolute_path(self, relative_path: str) -> str:
        """Returns the absolute filesystem path for a relative path."""
        pass

    @abstractmethod
    def delete(self, relative_path: str) -> bool:
        """Deletes the stored file."""
        pass

    @abstractmethod
    def get_size(self, relative_path: str) -> int:
        """Returns the size of the file in bytes."""
        pass


class LocalStorageAdapter(StorageAdapterBase):
    def __init__(self, base_dir: str = None):
        self.base_dir = Path(base_dir or getattr(settings, 'MEDIA_ROOT', os.path.join(settings.BASE_DIR, 'media')))
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save(self, tenant_id: int, file: UploadedFile, custom_filename: str = None) -> dict:
        tenant_dir = self.base_dir / f"tenant_{tenant_id}" / "pdfs"
        tenant_dir.mkdir(parents=True, exist_ok=True)

        filename = custom_filename or file.name
        # Sanitize filename
        safe_filename = "".join(c for c in filename if c.isalnum() or c in "._- ")
        if not safe_filename:
            safe_filename = "document.pdf"

        # Unique name if conflict
        target_path = tenant_dir / safe_filename
        counter = 1
        stem = Path(safe_filename).stem
        suffix = Path(safe_filename).suffix
        while target_path.exists():
            target_path = tenant_dir / f"{stem}_{counter}{suffix}"
            counter += 1

        file_size = 0
        with open(target_path, 'wb+') as destination:
            for chunk in file.chunks():
                destination.write(chunk)
                file_size += len(chunk)

        relative_path = str(target_path.relative_to(self.base_dir)).replace('\\', '/')
        return {
            "file_path": str(target_path),
            "relative_path": relative_path,
            "file_name": target_path.name,
            "file_size": file_size,
        }

    def get_absolute_path(self, relative_path: str) -> str:
        return str(self.base_dir / relative_path.replace('/', os.sep))

    def delete(self, relative_path: str) -> bool:
        try:
            full_path = self.base_dir / relative_path.replace('/', os.sep)
            if full_path.exists():
                full_path.unlink()
                return True
        except Exception:
            pass
        return False

    def get_size(self, relative_path: str) -> int:
        try:
            full_path = self.base_dir / relative_path.replace('/', os.sep)
            if full_path.exists():
                return full_path.stat().st_size
        except Exception:
            pass
        return 0
