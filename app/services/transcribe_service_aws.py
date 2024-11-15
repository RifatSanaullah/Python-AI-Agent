import boto3
import json
import asyncio
import websockets
from app.config import settings
from datetime import datetime
import pytz
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
import urllib.parse
from botocore.exceptions import NoCredentialsError, PartialCredentialsError
import hashlib
import hmac


class TranscribeService:
    def __init__(self):
        self.client = boto3.client(
            "transcribe",
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_region)
        self.sts_client = boto3.client(
            "sts",
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_region)

    def get_temporary_credentials(self):
        response = self.sts_client.get_session_token()
        credentials = response['Credentials']
        return credentials

    def build_websocket_url(self):
        # Get temporary credentials
        temp_credentials = self.get_temporary_credentials()

        # Set up your AWS credentials and region
        credentials = boto3.Session(
            aws_access_key_id=temp_credentials['AccessKeyId'],
            aws_secret_access_key=temp_credentials['SecretAccessKey'],
            aws_session_token=temp_credentials['SessionToken'],
            region_name=settings.aws_region
        ).get_credentials().get_frozen_credentials()
        
        # Define endpoint and canonical URI
        endpoint = f'wss://transcribestreaming.{settings.aws_region}.amazonaws.com:8443'
        canonical_uri = '/stream-transcription-websocket'
        
        # Set up parameters
        datetime_now = datetime.now(pytz.utc)
        amz_date = datetime_now.strftime('%Y%m%dT%H%M%SZ')
        date_stamp = amz_date[:8]
        session_id = datetime_now.strftime('%Y%m%d%H%M%S')
        
        # Create the canonical query string
        query_parameters = {
            'X-Amz-Algorithm': 'AWS4-HMAC-SHA256',
            'X-Amz-Credential': f"{credentials.access_key}/{date_stamp}/{settings.aws_region}/transcribe/aws4_request",
            'X-Amz-Date': amz_date,
            'X-Amz-Expires': '300',
            'X-Amz-Security-Token': credentials.token,
            'X-Amz-SignedHeaders': 'host;x-amz-date;x-amz-security-token',
            'language-code': 'en-US',
            'media-encoding': 'mulaw',
            'sample-rate': '8000',
            'session-id': session_id
        }
        
        # Sort the query parameters by name
        sorted_query_parameters = sorted(query_parameters.items())
        
        # URI-encode the query parameters
        canonical_querystring = '&'.join([f"{urllib.parse.quote_plus(k)}={urllib.parse.quote_plus(v)}" for k, v in sorted_query_parameters])

        # Create the canonical headers
        canonical_headers = (
            f"host:transcribestreaming.{settings.aws_region}.amazonaws.com:8443\n"
            f"x-amz-date:{amz_date}\n"
            f"x-amz-security-token:{credentials.token}\n"
        )

        # Create the signed headers
        signed_headers = 'host;x-amz-date;x-amz-security-token'

        # Create the payload hash
        payload_hash = hashlib.sha256(''.encode('utf-8')).hexdigest()

        # Create the canonical request
        canonical_request = (
            f"GET\n"
            f"{canonical_uri}\n"
            f"{canonical_querystring}\n"
            f"{canonical_headers}\n"
            f"{signed_headers}\n"
            f"{payload_hash}"
        )

        # Create the string to sign
        algorithm = 'AWS4-HMAC-SHA256'
        credential_scope = f"{date_stamp}/{settings.aws_region}/transcribe/aws4_request"
        string_to_sign = f"{algorithm}\n{amz_date}\n{credential_scope}\n{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"

        # Calculate the signature
        signing_key = self.get_signature_key(credentials.secret_key, date_stamp, settings.aws_region, 'transcribe')
        signature = hmac.new(signing_key, string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()

        # Create the websocket URL
        websocket_url = f"{endpoint}{canonical_uri}?{canonical_querystring}&X-Amz-Signature={signature}"

        return websocket_url

    def get_signature_key(self, key, date_stamp, region_name, service_name):
        k_date = hmac.new(('AWS4' + key).encode('utf-8'), date_stamp.encode('utf-8'), hashlib.sha256).digest()
        k_region = hmac.new(k_date, region_name.encode('utf-8'), hashlib.sha256).digest()
        k_service = hmac.new(k_region, service_name.encode('utf-8'), hashlib.sha256).digest()
        k_signing = hmac.new(k_service, 'aws4_request'.encode('utf-8'), hashlib.sha256).digest()
        return k_signing

    async def transcribe(self, audio_bytes):
        websocket_url = self.build_websocket_url()
        """Send audio to Amazon Transcribe via WebSocket and retrieve transcription text in real-time."""
        try:
            async with websockets.connect(websocket_url) as websocket:
                await websocket.send(audio_bytes)  # Send raw audio bytes
                while True:
                    response = await websocket.recv()
                    return response
                    if response:
                        try:
                            decoded_response = response.decode('utf-8')
                        except UnicodeDecodeError:
                            try:
                                decoded_response = response.decode('utf-16')
                            except UnicodeDecodeError:
                                decoded_response = response.decode('latin-1')
                        
                        # Check if the decoded response is not empty
                        if decoded_response.strip():
                            try:
                                result = json.loads(decoded_response)
                                if result.get("status") == "COMPLETED":
                                    return result["transcript"]
                                elif result.get("status") == "FAILED":
                                    return "Transcription failed."
                            except json.JSONDecodeError as json_err:
                                return f"JSON Decode error: {str(json_err)}. Raw response: {decoded_response[:100]}"
                        else:
                            return "Received empty response from the server."
                    await asyncio.sleep(1)
        except NoCredentialsError:
            return "No AWS credentials found. Please configure your AWS credentials."
        except PartialCredentialsError:
            return "Incomplete AWS credentials found. Please check your AWS credentials."
        except Exception as e:
            return f"Connection error: {str(e)}"
