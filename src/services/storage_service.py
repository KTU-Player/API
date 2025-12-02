from minio import Minio
from ..config import settings
import io


class StorageService:
    def __init__(self):
        self.client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ROOT_USER,
            secret_key=settings.MINIO_ROOT_PASSWORD,
            secure=False,  # Set to True if using HTTPS
        )
        self.bucket_name = settings.MINIO_BUCKET_NAME
        self._ensure_bucket_exists()

    def _ensure_bucket_exists(self):
        found = self.client.bucket_exists(self.bucket_name)
        if not found:
            self.client.make_bucket(self.bucket_name)

    def upload_file(
        self, object_name: str, data: io.BytesIO, length: int, content_type: str
    ):
        return self.client.put_object(
            self.bucket_name, object_name, data, length, content_type=content_type
        )

    def get_presigned_url(self, object_name: str):
        # Generate a presigned URL for 7 days
        return self.client.presigned_get_object(
            self.bucket_name,
            object_name,
        )


storage_service = StorageService()
