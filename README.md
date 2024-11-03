# FastAPI ML Application with Twilio, Amazon Polly, Amazon Transcribe, and OpenAI

## Overview

This project sets up a FastAPI application that integrates Twilio, Amazon Polly, Amazon Transcribe, and OpenAI's GPT model. It 
enables natural conversation flow through automated phone calls.

## Features

1. **Real-time Audio Processing** - Twilio receives calls, transcribes audio, and sends it to the application.
2. **ChatGPT Integration** - Uses ChatGPT to process and respond to user queries.
3. **Amazon Polly for Audio Response** - Converts text responses into audio using Amazon Polly.
4. **MySQL Database** - Stores conversation transcripts.

## Prerequisites

- **AWS Account** with Polly and Transcribe access
- **Twilio Account**
- **OpenAI API Key**
- **MySQL Database**
- **Python 3.8+**

## Installation

1. **Clone the repository:**
    ```bash
    git clone https://gitlab.com/boom-dev/com.boomershub.ai.agent.git
    cd com.boomershub.ai.agent
    ```

2. **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3. **Setup Environment Variables**:
    Create a `.env` file in the root of the project from `.env.example`
    ```bash
    cp .env.example .env
    ```

4. **Database Setup**:
    Ensure your `.env` file contains the correct `DATABASE_URL` for MySQL.

5. **Configure Twilio for Incoming Calls**:
   Set Up Webhook for Incoming Calls:
   - In the Twilio Console, navigate to the Phone Numbers section.
   - Click on your purchased phone number.
   - Under Voice & Fax, set the A CALL COMES IN webhook URL:
    ```bash
    https://yourdomain.com/incoming_call/
    ```
    * For local testing, consider using ngrok to expose your local server.

6. **Configure Twilio for Outgoing Calls**:
   Create an Outgoing Call Endpoint:
   The FastAPI application includes the `/make_call/` endpoint for initiating calls.

7. **Run the FastAPI Application**:
    ```bash
    uvicorn main:app --reload
    ```

8. **Testing Your Configuration**:
   - Test Incoming Calls: Call your Twilio number and verify the FastAPI application responds as expected.
   - Test Outgoing Calls: Send a POST request to the `/make_call/` endpoint with the recipient's phone number:
   ```bash
   curl -X POST "http://localhost:8000/make_call/" -H "Content-Type: application/json" -d '{"to_phone_number": "+1234567890"}'
   ```

9. **Additional Information**:
    - Ensure you keep your .env file secure and add it to your .gitignore to prevent it from being tracked by version control.
    - Monitor logs for any issues and debug as necessary.

### Let me know if additional changes are needed!

