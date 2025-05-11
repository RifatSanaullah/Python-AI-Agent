# app/main.py
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Depends, WebSocket, HTTPException
from fastapi.responses import PlainTextResponse, FileResponse, JSONResponse
from app.services.call_handler import CallHandler
from contextlib import asynccontextmanager
from fastapi import UploadFile, File
from pathlib import Path
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

app = FastAPI(
    title="BoomerCall API",
    description="API for Voice Assistant",
    version="0.0.2",
)

# Add CORS middleware to allow requests from frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



# Create global service instance
call_handler_instance = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global call_handler_instance
    call_handler_instance = CallHandler()
    yield
    # Cleanup code if needed

app.router.lifespan_context = lifespan


def get_call_handler():
    return call_handler_instance

@app.websocket("/audio-stream/{call_id}")
async def audio_stream(call_id : str, websocket: WebSocket, call_handler: CallHandler = Depends(get_call_handler)):
    await call_handler.process_input(call_id, websocket)

@app.post("/incoming_call")
async def incoming_call(request: Request, call_handler: CallHandler = Depends(get_call_handler)):
    data = await request.form()
    application_sid = data.get('ApplicationSid')
    direction = data.get('Direction')
    fromNumber = data.get('From')
    dialed_number = "+16692000795" 
    call_id = data.get("CallSid")
    
    data = {
        "call_sid": call_id,
        "from": fromNumber,
        "to": dialed_number,
        "application_sid": application_sid,
        "direction": direction
    }
    response = await call_handler.handle_call(call_id, data)
    return PlainTextResponse(content=str(response), media_type="application/xml")

@app.post("/outgoing_call")
async def outgoing_call(phone_number: str, call_handler: CallHandler = Depends(get_call_handler)):
    call_sid = await call_handler.make_outgoing_call(phone_number)
    return {"call_sid": call_sid}

@app.post("/stream_callback")
async def stream_callback(request: Request, call_handler: CallHandler = Depends(get_call_handler)):
    data = await request.form()
    return await call_handler.handle_stream_callback(data)

@app.post("/process-file/")
async def process_uploaded_file(file: UploadFile = File(...)):
        try:        
            content = await CallHandler.process_file(file)
            return {"filename": file.filename, "content": content}
        except ValueError as e:
            return
        
@app.get('/robots.txt', response_class=PlainTextResponse,include_in_schema=False)
def robots():
    data = """User-agent: *\nDisallow: /"""
    return data

@app.post("/recording_status_callback")
async def recording_status_callback(request: Request, call_handler: CallHandler = Depends(get_call_handler)):
    data = await request.form()
    print(data)

@app.post("/complete_status_callback")
async def complete_status_callback(request: Request, call_handler: CallHandler = Depends(get_call_handler)):
    data = await request.form()
    return await call_handler.complete_status_callback(data)

@app.post("/fallback_status_callback")
async def fallback_status_callback(request: Request, call_handler: CallHandler = Depends(get_call_handler)):
    data = await request.form()
    return await call_handler.fallback_status_callback(data)



@app.post("/nango/session-token")
async def get_nango_session_token(request: Request, call_handler: CallHandler = Depends(get_call_handler)):
    data = await request.json()
    user_id = data.get('userId', 'default-user')  # Use a default user ID if not provided
    integration_id = data.get('integrationId')
    print(data)
    # Get allowed integrations (optional)
    allowed_integrations = data.get('allowed_integrations')
    # Get connection_config if provided - will be used for server-side connection creation
    connection_config = data.get('connection_config')
    print(f"allowed_integrations: {allowed_integrations}, connection_config: {connection_config}")
    
    # If integrationId is provided, use it as the only allowed integration
    if integration_id:
        allowed_integrations = [integration_id]
    
    # Prepare Zoho configuration if needed
    # This will be used for server-side connection creation via the /configs endpoint
    if ((allowed_integrations and any(integ.startswith('zoho') for integ in allowed_integrations)) or 
        (integration_id and integration_id.startswith('zoho'))):
        
        # Initialize connection_config if not provided
        if not connection_config:
            connection_config = {}
            
        # Set default extension if not specified
        if "extension" not in connection_config:
            connection_config["extension"] = "com"  # Default to US region
            print(f"Using default Zoho region extension: {connection_config['extension']}")
        
        # Log the configuration to help with debugging
        print(f"Zoho CRM integration detected - connection_config: {connection_config}")
    
    # Use the ChatGPT service to get a Nango session token
    # The service will handle server-side connection creation with the config
    try:
        session_data = await call_handler.get_nango_session_token(
            user_id=user_id,
            allowed_integrations=allowed_integrations,
            connection_config=connection_config
        )
        print("checking if session data available",session_data)
        return session_data
    except Exception as e:
        print(f"Error getting Nango session token: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    from pyngrok import ngrok
    # Get the ngrok tunnel
    public_url = ngrok.connect(8000)
    print(f"Public URL: {public_url}")
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)