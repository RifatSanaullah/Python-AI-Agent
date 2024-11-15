import json
import boto3
import websockets
from typing import AsyncGenerator, Optional
from app.config import settings
from datetime import datetime
import time
import hmac
import hashlib
from urllib.parse import quote, urlencode
import numpy as np
import soundfile as sf
import base64

class TranscribeService:
    def __init__(self, language_code: str = "en-US"):
        self.region = settings.aws_region
        self.language_code = language_code
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.sts_client = boto3.client(
            'sts',
            aws_access_key_id=settings.aws_access_key_id,      
            aws_secret_access_key=settings.aws_secret_access_key,
        )

    async def _initialize_credentials(self):
        """Initialize or refresh AWS credentials."""
        try:
            assumed_role_object = self.sts_client.assume_role(
                RoleArn=settings.aws_role_arn,
                RoleSessionName=f"TranscribeSession_{int(time.time())}",
                DurationSeconds=3600  # 60 minutes
            )
            self.credentials = assumed_role_object['Credentials']
            
            # Verify all required credentials are present
            required_keys = ['AccessKeyId', 'SecretAccessKey', 'SessionToken']
            missing_keys = [key for key in required_keys if key not in self.credentials]
            
            if missing_keys:
                raise RuntimeError(f"Missing required credentials: {', '.join(missing_keys)}")
                
            return self.credentials
        except Exception as e:
            raise RuntimeError(f"Failed to initialize credentials: {str(e)}")


    async def get_transcribe_stream_url(self) -> str:
        # Set up AWS credentials for signing using STS
        await self._initialize_credentials()

        # Step 1: Setup request parameters
        endpoint = f"transcribestreaming.{self.region}.amazonaws.com:8443"
        host = endpoint
        method = 'GET'
        service = 'transcribe'
        path = "/stream-transcription-websocket"  # Added leading slash and URL encoded
        
        # Step 2: Create canonical request elements
        amz_date = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
        date_stamp = datetime.utcnow().strftime('%Y%m%d')
        
        # Step 3: Create canonical query string with sorted parameters
        query_params = {
            "X-Amz-Algorithm": "AWS4-HMAC-SHA256",
            "X-Amz-Credential": f"{self.credentials['AccessKeyId']}/{date_stamp}/{self.region}/{service}/aws4_request",
            "X-Amz-Date": amz_date,
            "X-Amz-Expires": "300",
            "X-Amz-Security-Token": self.credentials['SessionToken'],
            "X-Amz-SignedHeaders": "host",
            "language-code": self.language_code,
            "media-encoding": "pcm",  # Changed from mulaw to pcm
            "sample-rate": "16000"    # Changed from 8000 to 16000
        }
        canonical_querystring = urlencode(sorted(query_params.items()))

        # Step 4: Create canonical headers
        canonical_headers = f"host:{host}\n"
        signed_headers = "host"

        # Step 5: Create payload hash
        payload_hash = hashlib.sha256(b"").hexdigest()

        # Step 6: Create canonical request
        canonical_request = f"{method}\n" \
                            f"{path}\n" \
                            f"{canonical_querystring}\n" \
                            f"{canonical_headers}\n" \
                            f"{signed_headers}\n" \
                            f"{payload_hash}"

        # Step 7: Create string to sign
        algorithm = "AWS4-HMAC-SHA256"
        credential_scope = f"{date_stamp}/{self.region}/{service}/aws4_request"
        string_to_sign = f"{algorithm}\n{amz_date}\n{credential_scope}\n{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"

        # Step 8: Calculate the signature
        def sign(key, msg):
            return hmac.new(key, msg.encode('utf-8'), hashlib.sha256).digest()

        k_date = sign(('AWS4' + self.credentials['SecretAccessKey']).encode('utf-8'), date_stamp)
        k_region = sign(k_date, self.region)
        k_service = sign(k_region, service)
        k_signing = sign(k_service, 'aws4_request')
        signature = hmac.new(k_signing, string_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()

        # Step 9: Create WebSocket URL with signature
        websocket_url = (
            f"wss://{endpoint}{path}?"
            f"{canonical_querystring}&X-Amz-Signature={signature}"
        )

        return websocket_url

    async def start_transcription(self):
        try:
            transcribe_url = await self.get_transcribe_stream_url()

            # Initialize WebSocket connection with required headers
            self.websocket = await websockets.connect(
                transcribe_url,
                subprotocols=['aws.transcribe'],
                ping_interval=None, 
                ping_timeout=None
            )

            # First message should be configuration
            headers = {
                ":content-type": "application/json",
                ":message-type": "event",
                ":event-type": "start_transcription"
            }
            
            payload = {
                "media-encoding": "pcm",
                "sample-rate": 16000,
                "language-code": self.language_code
            }

            # Combine into single message
            message = {
                "headers": headers,
                "body": payload
            }

            await self.websocket.send(json.dumps(message))
            print("Sent start_transcription request")
            
            # Wait for response
            response = await self.websocket.recv()
            print(f"Start response: {response}")

            print("WebSocket connection established for transcription")
            
        except Exception as e:
            error_message = str(e)
            if "The security token included in the request is invalid" in error_message or "UnrecognizedClientException" in error_message:
                print("Refreshing AWS credentials due to invalid security token or unrecognized client exception")
                await self._initialize_credentials()
                await self.start_transcription()
            else:
                print(f"Error establishing WebSocket connection: {error_message}")
                raise

    async def _convert_mulaw_to_pcm(self, audio_chunk: bytes) -> bytes:
        """Convert mulaw audio to PCM format."""
        try:
            # Convert mulaw bytes to numpy array
            mulaw_data = np.frombuffer(audio_chunk, dtype=np.uint8)
            
            # Convert mulaw to PCM (16-bit signed integer)
            pcm_data = np.empty(len(mulaw_data), dtype=np.int16)
            
            # Mulaw to PCM conversion
            for i in range(len(mulaw_data)):
                mu = mulaw_data[i]
                # Invert the first bit
                sign = 1 if (mu & 0x80) else -1
                # Extract the segment and position
                position = mu & 0x0F
                segment = (mu & 0x70) >> 4
                
                # Reconstruct linear sample
                magnitude = (1 << segment) * (position + 16.5) - 16.5
                sample = sign * magnitude
                # Convert to 16-bit PCM
                pcm_data[i] = int(sample * 8)
            
            # Convert to bytes
            return pcm_data.tobytes()
        except Exception as e:
            print(f"Error converting mulaw to PCM: {str(e)}")
            raise

    async def send_audio_chunk(self, audio_chunk: bytes):
        """Send an audio chunk to the WebSocket if it's open."""
        if self.websocket and self.websocket.open:
            # Convert 8k mulaw to 16k pcm
            pcm_audio_chunk = await self._convert_mulaw_to_pcm(audio_chunk)
            headers = {
                ":content-type": "application/octet-stream",
                ":message-type": "event",
                ":event-type": "AudioEvent"
            }
            
            message = {
                "headers": headers,
                "body": base64.b64encode(pcm_audio_chunk).decode('utf-8')
            }
            await self.websocket.send(json.dumps(message))
        else:
            raise RuntimeError("WebSocket connection is not open")

    async def receive_transcriptions(self) -> AsyncGenerator[str, None]:
        """Receive transcriptions from the WebSocket in real-time."""
        if not self.websocket:
            raise RuntimeError("WebSocket connection is not open")

        async for message in self.websocket:
            print("Received message:", message)
            data = json.loads(message)
            print("Received data:", data)
            if 'Transcript' in data:
                for result in data['Transcript']['Results']:
                    if 'Alternatives' in result and len(result['Alternatives']) > 0:
                        transcript = result['Alternatives'][0]['Transcript']
                        if transcript:
                            yield transcript

    async def close_transcription(self):
        """Close the WebSocket connection."""
        if self.websocket:
            try:
                # Send end streaming message
                headers = {
                    ":content-type": "application/json",
                    ":message-type": "event",
                    ":event-type": "end"
                }
                
                message = {
                    "headers": headers,
                    "body": ""
                }
                await self.websocket.send(json.dumps(message))
                print("Sent end_transcription request")
                
                # Wait for final response
                final_response = await self.websocket.recv()
                print(f"Final response: {final_response}")
                
                # Close the connection
                await self.websocket.close()
                print("WebSocket connection closed")
                
            except Exception as e:
                print(f"Error closing connection: {str(e)}")
                raise

