# Required Libraries
import asyncio
import base64
import uuid
import time, datetime
import re
import threading, requests
from websocket import WebSocketApp, ABNF
from app.config import settings


# Twilio Stream Placeholder (replace with real stream logic)
async def send_to_twilio(call_id, audio_chunk):
    print(f"[Call {call_id}] Sending {len(audio_chunk)} bytes to Twilio")

# Azure TTS WebSocket Client per call
class AzureService:
    def __init__(self, voice="en-US-AriaNeural"):
        self.call_id = None
        self.voice = voice
        self.output_callback = None
        self.ws = None
        self.request_id = str(uuid.uuid4()).replace('-', '')
        self.connected = False
        self.full_text_buffer = ''
        self.last_split_index = 0
        self.region = settings.azure_region
        self.speech_key = settings.azure_key
        self.loop = asyncio.get_event_loop()

    def get_azure_token(self):

        url = f"https://{self.region}.api.cognitive.microsoft.com/sts/v1.0/issueToken"
        headers = {
            "Ocp-Apim-Subscription-Key": self.speech_key
        }

        response = requests.post(url, headers=headers)
        response.raise_for_status()
        return response.text
    async def establish_connection(self, voice, call_id, output_callback):
        self.call_id = call_id
        self.voice = voice
        self.output_callback = output_callback
        token = self.get_azure_token()
        url = f"wss://{self.region}.tts.speech.microsoft.com/cognitiveservices/websocket/v1?X-ConnectionId={self.request_id}"
        headers = {
            "Authorization": f"Bearer {token}",
            "X-ConnectionId": self.request_id
        }
        self.ws = WebSocketApp(
            url,
            header=[f"{k}: {v}" for k, v in headers.items()],
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )
        threading.Thread(target=self.ws.run_forever, daemon=True).start()
        while not self.connected:
            time.sleep(0.1)

    def on_open(self, ws):
        self.connected = True
        print(f"[Call {self.call_id}] WebSocket opened.")

    def on_message(self, ws, message):
        print("message recived", message)
        if isinstance(message, str) and "Path:audio" in message:
            return
        elif isinstance(message, bytes):
            header_end = message.find(b'\r\n\r\n') + 4
            audio_data = message[header_end:]
            if self.output_callback:
                asyncio.run_coroutine_threadsafe(
                    self.output_callback(self.call_id, audio_data), self.loop
                )

    def on_error(self, ws, error):
        print(f"[Call {self.call_id}] Error: {error}")

    def on_close(self, ws, *args):
        print(f"[Call {self.call_id}] Connection closed.")
        self.connected = False

    async def stream_text_to_speech(self, text):
        self.full_text_buffer += text
        sentences_to_process = []

        for match in re.finditer(r'[.!?](?:\s|$)', self.full_text_buffer):
            sentence = self.full_text_buffer[self.last_split_index : match.end()].strip()
            if sentence:
                sentences_to_process.append(sentence)
            self.last_split_index = match.end()

        for sentence in sentences_to_process:
            ssml = self._wrap_ssml(sentence)
            # self._send_headers()
            self._send_text_payload(sentence)



        self.full_text_buffer = self.full_text_buffer[self.last_split_index:].strip()

    def _wrap_ssml(self, text):
        return f"""
        <speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='en-US'>
            <voice name='{self.voice}'>
                <prosody rate='medium' pitch='medium'>
                    {text}
                </prosody>
            </voice>
        </speak>
        """

    async def flush_sp_ws(self):
        return

    def _send_headers(self):
        timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        headers = (
            f"Path: ssml\r\n"
            f"X-RequestId: {self.request_id}\r\n"
            f"X-Timestamp: {timestamp}\r\n"
            f"Content-Type: text/plain\r\n"
            f"\r\n"
        )
        self.ws.send(headers, opcode=ABNF.OPCODE_TEXT)
    def _send_text_payload(self, text):
        timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        message = f"X-RequestId:{self.request_id}\r\n"
        message += "Content-Type:text/plain; charset=utf-8\r\n"
        message += f"X-Timestamp:{timestamp}Z\r\n"
        message += f"Path:text\r\n\r\n"
        message += text

        self.ws.send(message, opcode=ABNF.OPCODE_TEXT)
    def _send_ssml(self, ssml):
        self.ws.send(ssml, opcode=ABNF.OPCODE_TEXT)
        print("ws send")

    def close(self):
        if self.ws:
            self.ws.close()