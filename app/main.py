# app/main.py
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Depends, WebSocket, HTTPException
from fastapi.responses import PlainTextResponse, FileResponse, JSONResponse, RedirectResponse # Keep RedirectResponse
from app.services.call_handler import CallHandler
from contextlib import asynccontextmanager
from fastapi import UploadFile, File
from pathlib import Path
from app.config import settings # Ensure settings is imported to access frontend_url
from app.services.backend_service import BackendHandler
from fastapi.middleware.cors import CORSMiddleware
from app.services.nango_service import NangoService # Added NangoService import back
from app.services import cinc_service
from typing import Optional, Dict, Any # Added Dict and Any for type hinting

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
    dialed_number =  "+16692000795"
    call_id = data.get("CallSid")
    print(data.get("IsBoom"))
    data = {
        "call_sid" : call_id,
        "from" : fromNumber,
        "to" : dialed_number,
        "application_sid" : application_sid,
        "direction" : direction,
        "isBoom": data.get("IsBoom"),
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
    fromNumber = data.get('From')
    if fromNumber == settings.boom_number:
        # Handle incoming call from Boom number
        data = {
            "CallDuration" : data.get("CallDuration"),
            "From" : fromNumber,
            "CallSid" : data.get("CallSid"),
        }
        response = await BackendHandler.complete_status_callback(data)
        return PlainTextResponse(content=str(response), media_type="application/xml")

    else:
        return await call_handler.complete_status_callback(data)

@app.post("/fallback_status_callback")
async def fallback_status_callback(request: Request, call_handler: CallHandler = Depends(get_call_handler)):
    data = await request.form()
    fromNumber = data.get('From')

    if fromNumber == settings.boom_number:
        # Handle incoming call from Boom number
        data = {
            "From" : fromNumber,
        }
        response = await BackendHandler.fallback_status_callback(data)
        return PlainTextResponse(content=str(response), media_type="application/xml")

    else:
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
            print("Nango webhook callback received:{integration_id}")
            if not connection_id or not end_user_id:
                return JSONResponse(
                    status_code=400,
                    content={"status": "error", "message": "Missing required fields"}
                )
            
            
            # Store the connection ID in the user's account
            try:
                # Determine if this is Zoho or HubSpot based on the integration ID
                is_zoho = "zoho" in (integration_id or "").lower()
                is_hubspot = "hubspot" in (integration_id or "").lower()
                is_salesforce = "salesforce" in (integration_id or "").lower()
                is_calendly = "calendly" in (integration_id or "").lower()
                is_google_calendar = "google-calendar" in (integration_id or "").lower()
                is_outlook = "outlook" in (integration_id or "").lower()
                # Store the connection ID in the account
                result = await call_handler.backend_service.store_nango_connection(
                    {
                        "user_id": end_user_id,
                        "organization_id": organization_id,
                        "connection_id": connection_id,
                        "integration_type": integration_id,
                        "is_zoho": is_zoho,
                        "is_hubspot": is_hubspot,
                        "is_salesforce": is_salesforce,
                        "is_calendly": is_calendly,
                        "is_google_calendar": is_google_calendar,
                        "is_outlook": is_outlook,
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
        session_data = await call_handler.ai_service.get_nango_session_token(
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
        return JSONResponse(status_code=200, content={"status": "success", "message": "Session removed successfully" , "data": response}) # Corrected data key
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# CINC OAuth Endpoints
@app.get("/cinc/login")
async def cinc_login(request: Request, state: Optional[str] = None, account_id: Optional[str] = None):
    if not account_id:
        raise HTTPException(status_code=400, detail="account_id is required for CINC login flow initiation")
    auth_url = cinc_service.get_authorization_url(state=state, account_id=account_id) 
    return RedirectResponse(url=auth_url)

@app.get("/cinc/callback", tags=["CINC Integration"])
async def cinc_callback(
    request: Request, 
    code: Optional[str] = None, 
    error: Optional[str] = None, 
    error_description: Optional[str] = None, 
    state: Optional[str] = None 
):
    base_redirect_url = settings.frontend_url.rstrip('/') + settings.frontend_cinc_callback_path 
    
    account_id_from_state = None
    original_csrf_state = None

    if state:
        state_parts = state.split("__")
        if len(state_parts) == 2:
            original_csrf_state = state_parts[0]
            account_id_from_state = state_parts[1]
        elif len(state_parts) == 1:
            pass 

    redirect_params = {}
    if original_csrf_state: 
        redirect_params['state'] = original_csrf_state
    if account_id_from_state: 
        redirect_params['account_id'] = account_id_from_state

    if error:
        if error == "access_denied":
            redirect_params['cinc_status'] = 'cancelled'
            redirect_params['detail'] = 'User denied access in CINC.'
        else:
            redirect_params['cinc_status'] = 'error'
            redirect_params['detail'] = error_description or error
        
        query_string = "&".join([f"{k}={v}" for k, v in redirect_params.items()])
        return RedirectResponse(url=f"{base_redirect_url}?{query_string}")

    if not code:
        redirect_params['cinc_status'] = 'error'
        redirect_params['detail'] = 'Authorization code not found in CINC callback.'
        query_string = "&".join([f"{k}={v}" for k, v in redirect_params.items()])
        return RedirectResponse(url=f"{base_redirect_url}?{query_string}")

    try:
       
        token_response = await cinc_service.exchange_code_for_token(auth_code=code, composite_state=state)
        
        
        stored_account_id = token_response.get("account_id_for_storage") 

        redirect_params['cinc_status'] = 'success'
        if stored_account_id:
             redirect_params['account_id'] = stored_account_id 
        elif account_id_from_state: 
            redirect_params['account_id'] = account_id_from_state
        
        query_string = "&".join([f"{k}={v}" for k, v in redirect_params.items()])
        return RedirectResponse(url=f"{base_redirect_url}?{query_string}")
    
    except HTTPException as e:
        redirect_params['cinc_status'] = 'error'
        redirect_params['detail'] = str(e.detail)
        if account_id_from_state: 
             redirect_params['account_id'] = account_id_from_state

        query_string = "&".join([f"{k}={v}" for k, v in redirect_params.items()])
        return RedirectResponse(url=f"{base_redirect_url}?{query_string}")
        
    except Exception as e:
        print(f"Unexpected error in CINC callback processing: {str(e)}") 
        redirect_params['cinc_status'] = 'error'
        redirect_params['detail'] = "An unexpected error occurred while finalizing CINC authorization."
        if account_id_from_state:
             redirect_params['account_id'] = account_id_from_state
        
        query_string = "&".join([f"{k}={v}" for k, v in redirect_params.items()])
        return RedirectResponse(url=f"{base_redirect_url}?{query_string}")

@app.post("/cinc/account/{account_id}/disconnect")
async def disconnect_cinc_integration(account_id: str):
    try:
        await cinc_service.delete_cinc_tokens(account_id=int(account_id))
        return JSONResponse(status_code=200, content={"message": "CINC connection deleted successfully"})
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete CINC connection: {str(e)}")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
