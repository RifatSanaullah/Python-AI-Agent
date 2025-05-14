# app/main.py
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Depends, WebSocket, HTTPException
from fastapi.responses import PlainTextResponse, FileResponse, JSONResponse
from app.services.call_handler import CallHandler
from contextlib import asynccontextmanager
from fastapi import UploadFile, File
from pathlib import Path
from fastapi.middleware.cors import CORSMiddleware
from app.services.nango_service import NangoService

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
    dialed_number = data.get("To")
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


@app.post("/nango-callback")
async def nango_webhook_callback(request: Request, call_handler: CallHandler = Depends(get_call_handler)):
   
    try:
        # Parse the webhook payload
        webhook_data = await request.json()
        
        # Check if this is an auth creation webhook
        if (webhook_data.get("type") == "auth" and 
            webhook_data.get("operation") == "creation" and 
            webhook_data.get("success") is True):
            
            # Extract the important information
            connection_id = webhook_data.get("connectionId")
            end_user_id = webhook_data.get("endUser", {}).get("endUserId")
            organization_id = webhook_data.get("endUser", {}).get("organizationId")
            integration_id = webhook_data.get("providerConfigKey")  # Get the integration type (e.g., "zoho-crm", "hubspot")
            
            if not connection_id or not end_user_id:
                return JSONResponse(
                    status_code=400,
                    content={"status": "error", "message": "Missing required fields"}
                )
            
            # Log the connection info
            print(f"Received Nango connection: User {end_user_id}, Connection {connection_id}, Integration: {integration_id}")
            
            # Store the connection ID in the user's account
            try:
                # Determine if this is Zoho or HubSpot based on the integration ID
                is_zoho = "zoho" in (integration_id or "").lower()
                is_hubspot = "hubspot" in (integration_id or "").lower()
                is_salesforce = "salesforce" in (integration_id or "").lower()
                
                # Store the connection ID in the account
                result = await call_handler.backend_service.store_nango_connection(
                    {
                        "user_id": end_user_id,
                        "organization_id": organization_id,
                        "connection_id": connection_id,
                        "integration_type": integration_id,
                        "is_zoho": is_zoho,
                        "is_hubspot": is_hubspot,
                        "is_salesforce": is_salesforce
                    }
                )
                
                return JSONResponse(
                    status_code=200,
                    content={"status": "success", "message": "Connection stored successfully in account", "data": result}
                )
            except Exception as store_error:
                print(f"Error storing connection ID in account: {str(store_error)}")
                return JSONResponse(
                    status_code=500,
                    content={"status": "error", "message": f"Error storing connection ID in account: {str(store_error)}"}
                )
        return JSONResponse(
            status_code=200,
            content={"status": "acknowledged", "message": "Webhook received"}
        )
        
    except Exception as e:
        print(f"Error processing Nango webhook: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Error processing webhook: {str(e)}"}
        )

@app.post("/nango/session-token")
async def get_nango_session_token(request: Request, call_handler: CallHandler = Depends(get_call_handler)):
    data = await request.json()
    user_id = data.get('userId', 'default-user')  # Use a default user ID if not provided
    integration_id = data.get('integrationId')
    print(data)
    # Get allowed integrations (optional)
    allowed_integrations = data.get('allowed_integrations')
    print(allowed_integrations)
    # If integrationId is provided, use it as the only allowed integration
    if integration_id:
        allowed_integrations = [integration_id]
    
    # Use the ChatGPT service to get a Nango session token
    try:
        session_data = await call_handler.chatgpt_service.get_nango_session_token(
            user_id=user_id,
            allowed_integrations=allowed_integrations
        )
        print("checking if session data available",session_data)
        return session_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/remove-session")
async def remove_session(request: Request, call_handler: CallHandler = Depends(get_call_handler)):
    data = await request.json()
    connection_id = data.get('connection_id')
    connection_type = data.get('connection_type')
    account_id = data.get('account_id')
    print("removing session", connection_id)
    if not connection_id:
        raise HTTPException(status_code=400, detail="Connection ID is required")
    
    try:
        await NangoService().delete_connect_session(connection_id)
        response = await call_handler.backend_service.remove_nango_connection(
                    {

                        "account_id": account_id,
                        "connection_type": connection_type,
                    })
        return JSONResponse(status_code=200, content={"status": "success", "message": "Session removed successfully" , data: response})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
