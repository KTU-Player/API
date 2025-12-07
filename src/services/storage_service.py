import uuid
from urllib.parse import urlparse

from fastapi import UploadFile
from minio import Minio

from src.config import settings


class StorageService:
    def __init__(self):
        self.client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ROOT_USER,
            secret_key=settings.MINIO_ROOT_PASSWORD,
            secure=False,
        )
        self.audio_bucket = settings.MINIO_AUDIO_BUCKET
        self.covers_bucket = settings.MINIO_COVERS_BUCKET

    def init_buckets(self):
        if not self.client.bucket_exists(self.audio_bucket):
            self.client.make_bucket(self.audio_bucket)
        if not self.client.bucket_exists(self.covers_bucket):
            self.client.make_bucket(self.covers_bucket)

    def upload_file(self, file: UploadFile, bucket: str) -> str:
        if bucket not in [self.audio_bucket, self.covers_bucket]:
            raise ValueError(f"Invalid bucket: {bucket}")

        if file.filename is None or file.content_type is None:
            raise ValueError("File is required.")

        file_name, file_ext = file.filename.rsplit(".", 1)
        sanitized_filename = file_name.lower().replace(" ", "-")
        object_name = f"{uuid.uuid4()}_{sanitized_filename}.{file_ext}"

        self.client.put_object(
            bucket,
            object_name,
            file.file,
            length=-1,
            part_size=10 * 1024 * 1024,
            content_type=file.content_type,
        )

        return f"http://{settings.MINIO_ENDPOINT}/{bucket}/{object_name}"

    def delete_file(self, file_url: str) -> bool:
        try:
            parsed_url = urlparse(file_url)
            bucket_name = parsed_url.path.split("/")[1]
            object_name = parsed_url.path.split("/")[2]

            self.client.remove_object(bucket_name, object_name)
            return True
        except Exception as e:
            print(f"Error deleting file from MinIO: {e}")
            return False


storage_service = StorageService()
