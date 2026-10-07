"""S3-compatible implementation of ObjectStorageService (MinIO / AWS S3)."""

import io
import logging
from typing import BinaryIO
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.storage.base import ObjectStorageService

logger = logging.getLogger("app.storage.s3")


class S3ObjectStorageService(ObjectStorageService):
    """S3-compatible object storage service implementation using boto3."""

    def __init__(
        self,
        endpoint_url: str | None,
        access_key: str,
        secret_key: str,
        bucket_name: str,
        region_name: str = "us-east-1",
        use_ssl: bool = False,
    ) -> None:
        self.bucket_name = bucket_name
        self.endpoint_url = endpoint_url
        self.region_name = region_name

        client_kwargs = {
            "service_name": "s3",
            "region_name": region_name,
            "aws_access_key_id": access_key,
            "aws_secret_access_key": secret_key,
            "use_ssl": use_ssl,
            "config": Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
                connect_timeout=2,
                read_timeout=5,
                retries={"max_attempts": 1},
            ),
        }
        if endpoint_url:
            client_kwargs["endpoint_url"] = endpoint_url

        self.s3_client = boto3.client(**client_kwargs)
        logger.info(
            "Initialized S3ObjectStorageService (endpoint=%s, bucket=%s, region=%s, ssl=%s)",
            endpoint_url,
            bucket_name,
            region_name,
            use_ssl,
        )

    def ensure_bucket_exists(self) -> None:
        """Idempotently verify that the target bucket exists, creating it if needed."""
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            logger.debug("Bucket '%s' exists and is accessible.", self.bucket_name)
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "")
            if error_code in ("404", "NoSuchBucket"):
                logger.info("Bucket '%s' does not exist. Creating bucket...", self.bucket_name)
                try:
                    if self.region_name and self.region_name != "us-east-1":
                        self.s3_client.create_bucket(
                            Bucket=self.bucket_name,
                            CreateBucketConfiguration={"LocationConstraint": self.region_name},
                        )
                    else:
                        self.s3_client.create_bucket(Bucket=self.bucket_name)
                    logger.info("Bucket '%s' created successfully.", self.bucket_name)
                except ClientError as create_exc:
                    logger.error("Failed to create bucket '%s': %s", self.bucket_name, str(create_exc))
                    raise
            else:
                logger.warning("Error inspecting bucket '%s': %s", self.bucket_name, str(exc))
        except Exception as exc:
            logger.warning("Bucket verification skipped or storage endpoint unreachable: %s", exc)

    def upload(
        self,
        key: str,
        data: BinaryIO | bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Upload binary data or file stream to S3 under specified key."""
        try:
            if isinstance(data, bytes):
                self.s3_client.put_object(
                    Bucket=self.bucket_name,
                    Key=key,
                    Body=data,
                    ContentType=content_type,
                )
            else:
                self.s3_client.upload_fileobj(
                    Fileobj=data,
                    Bucket=self.bucket_name,
                    Key=key,
                    ExtraArgs={"ContentType": content_type},
                )
            logger.info("Uploaded object to S3 (bucket=%s, key=%s)", self.bucket_name, key)
            return key
        except Exception as exc:
            logger.error("Failed to upload object '%s' to bucket '%s': %s", key, self.bucket_name, str(exc))
            raise

    def download(self, key: str) -> BinaryIO:
        """Download object stream from S3 by key."""
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
            return response["Body"]
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "")
            if error_code in ("404", "NoSuchKey"):
                logger.warning("Object '%s' not found in bucket '%s'.", key, self.bucket_name)
                raise FileNotFoundError(f"Object '{key}' not found in storage")
            logger.error("Failed to download object '%s': %s", key, str(exc))
            raise

    def delete(self, key: str) -> bool:
        """Delete an object from S3. Return True if deleted or already absent."""
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=key)
            logger.info("Deleted object from S3 (bucket=%s, key=%s)", self.bucket_name, key)
            return True
        except Exception as exc:
            logger.warning("Error deleting object '%s' from S3: %s", key, str(exc))
            return False

    def exists(self, key: str) -> bool:
        """Check if object exists in S3."""
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=key)
            return True
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "")
            if error_code in ("404", "NoSuchKey"):
                return False
            logger.error("Error checking existence of object '%s': %s", key, str(exc))
            raise
