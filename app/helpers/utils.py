    
import random
from fastapi import UploadFile, WebSocketDisconnect
from docx import Document
from PyPDF2 import PdfReader
import wave
import audioop
import os
import asyncio
import random
from datetime import date, datetime
def get_interrupt_message(type = 'check_availability'):
        arrayObj = {
            'interrupt': [
                "Go ahead",
                "Please, go ahead."
                "Yes, do continue."
                "Yes, please go on."
                "I'm listening, please."
                "Yes, please continue. "
                "Of course, go ahead."
                "Go ahead, I'm listening."
                "Okay, I'm listening."
                "Sure, please continue."
            ],
            'check_availability': [
                "Are you around?",
                "Still with me?",
                "You there?",
                "Did I lose you?",
                "Are you gone?",
                "Can you hear me?",
                "Are you still online?",
                "Just checking if you're still here.",
                "Are you still listening?",
                "Hello? Still there?"
            ],
            'end_call': [
                "I understand you might be tied up. Feel free to message me when you're available. Wishing you a great day!",
                "No worries if you're busy. Just reach out when you have a moment. Take care!",
                "You may be caught up with something. Ping me whenever you're free. Have a wonderful day!",
                "Totally fine if you're busy. Let's connect when you get a chance. Hope your day is going well!",
                "If you're occupied, that's okay. Reach out anytime you're free. Have an awesome day!",
                "I get that things can get hectic. Connect with me whenever you're free. Take it easy!",
                "It seems like you might be busy. Just drop a message when you’re free. Enjoy your day!",
                "All good if you’re swamped. Let’s talk whenever you have time. Wishing you a nice day!",
                "You might have your hands full. Reach out whenever it works for you. Hope your day’s great!",
                "Understandable if you're unavailable right now. Let's chat when you're free. Have a great one!"
                ]
        } 


        return random.choice(arrayObj[type])

async def process_file(file: UploadFile):
        """
        Process the uploaded file based on its MIME type and content.

        Supports: TXT, DOC/DOCX, PDF
        """
        # Read the file content
        file_content = await file.read()

        # Process based on MIME type
        if file.content_type == "text/plain":
            # Process TXT file
            return file_content.decode("utf-8")

        elif file.content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            # Process DOCX file
            from io import BytesIO
            doc = Document(BytesIO(file_content))
            return "\n".join([paragraph.text for paragraph in doc.paragraphs])

        elif file.content_type == "application/pdf":
            # Process PDF file
            from io import BytesIO
            pdf_reader = PdfReader(BytesIO(file_content))
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text()
            return text

        else:
            # Unsupported file type
            print("Unsupported file type. Please upload TXT, DOC/DOCX, or PDF files.")
            return None

async def convert_mulaw_to_wav(mulaw_file, wav_file):
        # Define WAV file settings
        wav_fp = wave.open(wav_file, 'wb')
        wav_fp.setnchannels(1)  # Mono channel
        wav_fp.setsampwidth(2)  # 16-bit samples
        wav_fp.setframerate(8000)  # 8 kHz sampling rate

        # Read the μ-law file
        with open(mulaw_file, 'rb') as mulaw_fp:
            while True:
                chunk = mulaw_fp.read(1024)
                if not chunk:
                    break

                # Convert μ-law to linear PCM
                pcm_chunk = audioop.ulaw2lin(chunk, 2)

                # Write the PCM chunk to the WAV file
                wav_fp.writeframes(pcm_chunk)

        wav_fp.close()

def json_serial(self, obj):
        """JSON serializer for objects not serializable by default json code"""

        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        raise TypeError ("Type %s not serializable" % type(obj))


async def estimate_speech_duration(text, wpm=150, include_pauses=True):
    """
    Estimate speech duration from text.
    
    Args:
        text (str): The text to analyze
        wpm (int): Words per minute (default 150 for average speech)
        include_pauses (bool): Add time for punctuation pauses
    
    Returns:
        dict: Duration in seconds, minutes, and formatted time
    """
    import re
    
    # Count words (split by whitespace, remove empty strings)
    words = len([word for word in text.split() if word.strip()])
    
    # Calculate base duration in minutes
    base_duration_minutes = words / wpm
    
    # Add pause time for punctuation if requested
    pause_time = 0
    if include_pauses:
        # Count punctuation that typically causes pauses
        periods = text.count('.')
        commas = text.count(',')
        semicolons = text.count(';')
        colons = text.count(':')
        exclamations = text.count('!')
        questions = text.count('?')
        dashes = text.count('—') + text.count('--')
        
        # Estimate pause durations (in seconds)
        pause_time = (
            periods * 0.4 +          # Period: 0.5 sec
            commas * 0.1 +           # Comma: 0.2 sec
            semicolons * 0.2 +       # Semicolon: 0.3 sec
            colons * 0.2 +           # Colon: 0.3 sec
            exclamations * 0.3 +     # Exclamation: 0.4 sec
            questions * 0.3 +        # Question: 0.4 sec
            dashes * 0.2             # Dash: 0.3 sec
        )
    
    # Total duration in seconds
    total_seconds = (base_duration_minutes * 60) + pause_time
    
    # Format time
    minutes = int(total_seconds // 60)
    seconds = int(total_seconds % 60)
    
    return {
        'total_seconds': round(total_seconds, 1),
        'minutes': minutes,
        'seconds': seconds,
        'formatted': f"{minutes}:{seconds:02d}",
        'word_count': words,
        'estimated_wpm': wpm
    }
    