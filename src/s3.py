"""
This module defines the S3StateFileManager class,
which reads and writes JSON-based state files from and to an AWS S3 bucket.
"""

import json
import boto3
from botocore.exceptions import ClientError


class S3StateFileManager:
    """
    A class to manage reading and writing state files (JSON) to/from AWS S3.
    """
    MODULE_NAME = "S3StateFileManager"

    def __init__(self, s3_bucket_name, s3_region):
        """
        Initializes the S3StateFileManager with S3 client.
        """
        self.S3_BUCKET_NAME = s3_bucket_name
        self.S3_REGION = s3_region
        self.s3_client = boto3.client("s3", region_name=self.S3_REGION)

    @classmethod
    def build_response(cls, success: bool, message: str, **kwargs) -> dict:
        """
        Utility method to return standardized responses.
        """
        response = {
            "success": success,
            "message": message,
            "module": cls.MODULE_NAME
        }
        response.update(kwargs)
        return response

    @staticmethod
    def _normalize_key(path: str, filename: str) -> str:
        """
        Normalizes S3 key path (prefix + filename).
        """
        return f"{path.strip('/')}/{filename}"

    def load_state(self, s3_file_path: str, s3_file_name: str) -> dict:
        """
        Reads a state file (JSON data) from S3 bucket and returns its content.
        """
        if not s3_file_name:
            return self.build_response(False, "S3 file name cannot be empty.")

        file_key = self._normalize_key(s3_file_path, s3_file_name)
        bucket_name = self.S3_BUCKET_NAME

        try:
            self.s3_client.head_object(Bucket=bucket_name, Key=file_key)
        except ClientError as e:
            code = e.response["Error"]["Code"]
            if code == "404":
                return self.build_response(
                    False,
                    f"{code} S3 file '{file_key}' not found in bucket '{bucket_name}'."
                )
            return self.build_response(
                False,
                (
                    f"Failed to access S3 file '{file_key}': {code} - "
                    f"{e.response['Error'].get('Message', str(e))}"
                )
            )
        try:
            response = self.s3_client.get_object(
                Bucket=bucket_name, Key=file_key)
            file_content = response["Body"].read().decode("utf-8")
            data = json.loads(file_content)

            return self.build_response(True, f"S3 file '{file_key}' loaded successfully", data=data)

        except json.JSONDecodeError as e:
            return self.build_response(False, f"Decoding failed for S3 file '{file_key}': {str(e)}")
        except Exception as e:
            return self.build_response(False, f"Error while loading S3 file '{file_key}': {str(e)}")

    def record_state(self, s3_file_path: str, s3_file_name: str, data_to_write: dict) -> dict:
        """
        Writes (or overwrites) JSON data to a S3 state file.
        """
        if not s3_file_name:
            return self.build_response(False, "S3 file name cannot be empty.")

        file_key = self._normalize_key(s3_file_path, s3_file_name)
        bucket_name = self.S3_BUCKET_NAME

        try:
            json_content = json.dumps(data_to_write, indent=4)

            self.s3_client.put_object(
                Bucket=bucket_name,
                Key=file_key,
                Body=json_content,
                ContentType='application/json'
            )

            return self.build_response(True, f"State successfully recorded to S3 file '{file_key}'")

        except ClientError as e:
            code = e.response["Error"]["Code"]
            return self.build_response(
                False,
                (
                    f"Failed to write to S3 file '{file_key}': {code} - "
                    f"{e.response['Error'].get('Message', str(e))}"
                )
            )

        except Exception as e:
            return self.build_response(False, f"Error while writing to S3 file '{file_key}': {str(e)}")
