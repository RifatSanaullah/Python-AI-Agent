import boto3
from app.config import settings
from pathlib import Path
from fastapi import HTTPException
import os

class S3Service:
    def __init__(self):
        self.client = boto3.client(
            's3',
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_region
        )

    async def uploadToS3(self, file_path):
        try:
            local_file = Path(file_path)
            if not local_file.is_file():
                raise HTTPException(status_code=404, detail="File not found locally")

            if not file_path.endswith(".wav"):
                raise HTTPException(status_code=400, detail="Only .wav files are allowed")

            # Define S3 file path
            s3_file_path = f"recordings/{local_file.name}"

            # Upload the local file to S3
            with open(local_file, "rb") as file:
                self.client.upload_fileobj(
                    file,
                    settings.s3_bucket_name,
                    s3_file_path,
                    ExtraArgs={"ACL": "public-read", "ContentType": "audio/wav"},
                )
            os.remove(local_file)

            # Generate public URL
            file_url = f"https://{settings.s3_bucket_name}.s3.{settings.aws_region}.amazonaws.com/{s3_file_path}"
            return file_url
        except self.client.exceptions.InvalidSsmlException as e:
            print(f"Invalid SSML request: {e}")
            raise
        except Exception as e:
            print(f"An error occurred: {e}")
            raise
