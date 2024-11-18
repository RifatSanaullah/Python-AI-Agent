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
from scipy import signal
import g711

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
            "sample-rate": "8000"    # Changed from 8000 to 16000
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
                ":event-type": "ConfigurationEvent",
                ":message-type": "event"
            }
            
            body = {
                "LanguageCode": "en-US",
                "MediaSampleRateHertz": 16000,
                "MediaEncoding": "pcm"
            }

            # Convert headers and body to JSON and get bytes
            headers_json = json.dumps(headers)
            body_json = json.dumps(body)
            headers_bytes = headers_json.encode('utf-8')
            body_bytes = body_json.encode('utf-8')

            # Create the prelude
            total_length = len(headers_bytes) + len(body_bytes)
            prelude = bytearray()
            prelude.extend(total_length.to_bytes(4, byteorder='big'))
            prelude.extend(len(headers_bytes).to_bytes(4, byteorder='big'))

            # Combine all parts
            message = prelude + headers_bytes + body_bytes

            if self.websocket.open:
                await self.websocket.send(message)
                print("Sent start_transcription request")
                
                # Wait for response
                response = await self.websocket.recv()
                print(f"Start response: {response}")
            else:
                raise RuntimeError("WebSocket connection is not open after sending config request")

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

    def is_blank_or_static(self, audio_chunk: bytes) -> bool:
        """Check if the audio chunk is blank or static noise."""
        print("audio_chunk", audio_chunk)
        pcm_array = np.frombuffer(audio_chunk, dtype=np.int16)
        print("pcm_array", pcm_array)
        normalized_audio = pcm_array / 32768.0
        max_amplitude = np.max(np.abs(normalized_audio))
        energy = np.mean(normalized_audio ** 2)
        print(f"Max amplitude: {max_amplitude}, Energy: {energy}")
        print(max_amplitude < 0.1 or energy < 0.01)
        return max_amplitude < 0.1 or energy < 0.01

    def upsample(self, pcm_data, original_rate=8000, target_rate=16000):
        # Use resampy for better quality resampling
        upsampled_data = signal.resample(pcm_data, int(len(pcm_data) * target_rate / original_rate))
        # Ensure the data stays within int16 bounds
        upsampled_data = np.clip(upsampled_data, -32768, 32767)
        return upsampled_data.astype(np.int16)

    async def send_audio_chunk(self, audio_chunk: bytes):
        """Send an audio chunk to the WebSocket if it's open."""
        print("Sending audio chunk")
        if self.websocket and self.websocket.open:
            # Convert 8k mulaw to 16k pcm
            pcm_chunk = g711.decode_ulaw(audio_chunk)

            if not self.is_blank_or_static(pcm_chunk):
                
                headers = {
                    ":content-type": "application/octet-stream",
                    ":event-type": "AudioEvent",
                    ":message-type": "event"
                }
                
                # Convert headers to JSON and get bytes
                headers_json = json.dumps(headers)
                headers_bytes = headers_json.encode('utf-8')

                # Create the prelude (total byte length and headers length)
                total_length = len(headers_bytes) + len(pcm_chunk)
                prelude = bytearray()
                prelude.extend(total_length.to_bytes(4, byteorder='big'))
                prelude.extend(len(headers_bytes).to_bytes(4, byteorder='big'))

                message = bytearray()
                message.extend(prelude)
                message.extend(headers_bytes)
                message.extend(pcm_chunk)

                # Combine all parts into final message
                # message = prelude + headers_bytes + upsampled_chunk

                # print(f"Sending audio chunk of size {len(chunk_to_send)}")
                await self.websocket.send(message)
            else:
                print("Blank or static audio detected, skipping chunk.")
        else:
            raise RuntimeError("WebSocket connection is not open when sending audio chunk")

    async def receive_transcriptions(self) -> AsyncGenerator[str, None]:
        """Receive transcriptions from the WebSocket in real-time."""
        if not self.websocket or not self.websocket.open:
            raise RuntimeError("WebSocket connection is not open when receiving transcriptions")

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
        if self.websocket and self.websocket.open:
            try:
                # Send end streaming message
 
                headers = {
                    ":content-type": "application/octet-stream",
                    ":event-type": "AudioEvent",
                    ":message-type": "event"
                }
                body = b""  # Empty audio chunk

                headers_json = json.dumps(headers)
                headers_bytes = headers_json.encode('utf-8')

                # Create the prelude (total byte length and headers length)
                total_length = len(headers_bytes) + len(body)
                prelude = bytearray()
                prelude.extend(total_length.to_bytes(4, byteorder='big'))
                prelude.extend(len(headers_bytes).to_bytes(4, byteorder='big'))

                message = prelude + headers_bytes + body

                await self.websocket.send(message)
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
        else:
            print("WebSocket connection is already closed")

