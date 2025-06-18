
import re

class StreamingChunker:
    def __init__(self, max_length=200, onTTS=None, conversation_id=None):
        self.buffer = ""  # Store incoming characters
        self.max_length = max_length
        self.send_to_tts= onTTS
        self.conversation_id= conversation_id

    async def add_stream_data(self, char):
        self.buffer = char  # Append incoming characters
        
        # Check if we have a complete sentence AND at least 200 chars
        if len(self.buffer) >= self.max_length:
            chunk, remaining = self._split_at_sentence()
            if chunk:
                chunk = self.filter_message(chunk)
                print("chunk : " ,chunk)
                # self.buffer = remaining  # Keep the leftover text for the next chunk
                await self.send_to_tts(chunk, self.conversation_id)  # Process the completed chunk
                await self.add_stream_data(remaining)

    async def flush(self):
        """Force send any remaining text when stream ends."""
        if self.buffer.strip():
            chunk = self.filter_message(self.buffer)
            print("chunk : ", chunk)
            await self.send_to_tts(chunk, self.conversation_id)
            self.buffer = ""

    def _split_at_sentence(self):
        """Find the nearest full sentence before max_length."""
        # sentences = re.split(r'(?<=[.!?])\s+', self.buffer)  # Split at sentence end
        sentences = re.findall(r'[^.!?]*[.!?]', self.buffer, re.DOTALL)
        chunk, remaining = "", ""

        for sentence in sentences:
            if len(chunk) + len(sentence) <= self.max_length:
                chunk += " " + sentence if chunk else sentence
            else:
                remaining = " ".join(sentences[sentences.index(sentence):])  # Save leftover
                break
        
        return chunk.strip(), remaining.strip()  # Return cleanly formatted chunks

    def filter_message(self, message):
        if 'End Call Message' in message or 'Routing Message' in message:
            message = message.replace('End Call Message', '')
            message = message.replace('Routing Message', '')
        return message

