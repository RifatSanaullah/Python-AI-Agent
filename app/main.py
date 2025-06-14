# app/main.py
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Depends, WebSocket, HTTPException
from fastapi.responses import PlainTextResponse, FileResponse, JSONResponse, RedirectResponse
from app.services.call_handler import CallHandler
from contextlib import asynccontextmanager
from fastapi import UploadFile, File
from pathlib import Path
from app.config import settings
from app.services.backend_service import BackendHandler
from fastapi.middleware.cors import CORSMiddleware
from app.services.nango_service import NangoService
from app.services import cinc_service # Added CINC service import
from typing import Optional # Added for optional query parameters

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
    dialed_number = data.get('To')
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
        return JSONResponse(status_code=200, content={"status": "success", "message": "Session removed successfully" , "data": response}) # Corrected data key
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# CINC OAuth Endpoints
@app.get("/cinc/login")
async def cinc_login(request: Request, state: Optional[str] = None, user_id: Optional[str] = None):
    # state (CSRF token) and user_id are expected from the frontend query parameters
    if not user_id:
        return JSONResponse(
            status_code=400,
            content={"message": "user_id query parameter is required for /cinc/login"}
        )
    if not state:
        # Frontend should generate and send a CSRF state token
        return JSONResponse(
            status_code=400,
            content={"message": "state (CSRF token) query parameter is required for /cinc/login"}
        )

    # Pass both the original CSRF state and user_id to be encoded into the final composite state
    authorization_url = cinc_service.get_authorization_url(state=state, user_id=user_id)
    return RedirectResponse(authorization_url)

@app.get("/cinc/callback")
async def cinc_callback(request: Request, code: Optional[str] = None, state: Optional[str] = None, error: Optional[str] = None, error_description: Optional[str] = None):
    original_csrf_state = None
    user_id_from_state = None

    if state:
        parts = state.split(":UID:")
        if len(parts) == 2:
            original_csrf_state = parts[0]
            user_id_from_state = parts[1]
        else:
            print(f"Warning: CINC callback state format unexpected: {state}")
            error_redirect_url = f"{settings.frontend_url}{settings.frontend_cinc_callback_path}?cinc_status=error&detail=Invalid state format received from CINC"
            return RedirectResponse(error_redirect_url)
    else:
        # This should not happen if CINC is redirecting correctly, even with an error
        print("Error: CINC callback received no state parameter.")
        error_redirect_url = f"{settings.frontend_url}{settings.frontend_cinc_callback_path}?cinc_status=error&detail=Missing state parameter from CINC"
        return RedirectResponse(error_redirect_url)

    if not user_id_from_state: # Should be caught by state parsing, but as a safeguard
        error_redirect_url = f"{settings.frontend_url}{settings.frontend_cinc_callback_path}?cinc_status=error&detail=User ID missing in state&state={original_csrf_state}"
        return RedirectResponse(error_redirect_url)

    # Handle CINC authorization errors (e.g., user denied access)
    if error:
        error_detail = error_description or error
        print(f"CINC authorization error for user {user_id_from_state}: {error_detail}")
        error_redirect_url = f"{settings.frontend_url}{settings.frontend_cinc_callback_path}?cinc_status=error&detail={error_detail}&user_id={user_id_from_state}&state={original_csrf_state}"
        return RedirectResponse(error_redirect_url)

    if not code:
        # If there's no error and no code, something is wrong.
        print(f"CINC callback for user {user_id_from_state} missing authorization code and no error reported.")
        error_redirect_url = f"{settings.frontend_url}{settings.frontend_cinc_callback_path}?cinc_status=error&detail=Missing authorization code from CINC&user_id={user_id_from_state}&state={original_csrf_state}"
        return RedirectResponse(error_redirect_url)

    try:
        await cinc_service.exchange_code_for_token(auth_code=code, user_id_for_storage=user_id_from_state)
        success_redirect_url = f"{settings.frontend_url}{settings.frontend_cinc_callback_path}?cinc_status=success&user_id={user_id_from_state}&state={original_csrf_state}"
        return RedirectResponse(success_redirect_url)
    except HTTPException as e:
        error_redirect_url = f"{settings.frontend_url}{settings.frontend_cinc_callback_path}?cinc_status=error&detail={e.detail}&user_id={user_id_from_state}&state={original_csrf_state}"
        return RedirectResponse(error_redirect_url)
    except Exception as e:
        print(f"Error in CINC callback during token exchange for user {user_id_from_state}: {e}")
        error_redirect_url = f"{settings.frontend_url}{settings.frontend_cinc_callback_path}?cinc_status=error&detail=Internal Server Error during token exchange&user_id={user_id_from_state}&state={original_csrf_state}"
        return RedirectResponse(error_redirect_url)

@app.get("/cinc/user/{user_id}/status")
async def get_cinc_connection_status(user_id: str):
    tokens = await cinc_service.get_cinc_tokens(user_id)
    if tokens and tokens.get("access_token"):
        # Optionally, you could make a test API call to CINC here to be absolutely sure
        # For now, presence of tokens implies connection.
        return {"status": "connected", "user_id": user_id}
    return {"status": "disconnected", "user_id": user_id}

@app.post("/cinc/user/{user_id}/disconnect")
async def disconnect_cinc_integration(user_id: str):
    try:
        await cinc_service.delete_cinc_tokens(user_id)
        return {"message": "CINC integration disconnected successfully", "user_id": user_id}
    except HTTPException as e:
        raise e # Re-raise HTTPException from service layer
    except Exception as e:
        print(f"Error disconnecting CINC for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to disconnect CINC integration")

@app.get("/cinc/user/{user_id}/leads")
async def get_cinc_leads_for_user(user_id: str, offset: int = 0, limit: int = 10, next_page: Optional[str] = None, from_lead_id: Optional[str] = None):
    """Fetches a list of leads from CINC for the specified user."""
    try:
        leads_data = await cinc_service.get_leads(user_id, offset=offset, limit=limit, next_page=next_page, from_lead_id=from_lead_id)
        return leads_data
    except HTTPException as e:
        raise e # Forward errors from service layer
    except Exception as e:
        print(f"Error fetching CINC leads for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch CINC leads: {str(e)}")

@app.post("/cinc/user/{user_id}/leads")
async def create_cinc_lead_for_user(user_id: str, lead_data: dict): # FastAPI parses JSON body to lead_data (dict)
    """Creates a new lead in CINC for the specified user."""
    try:
        created_lead = await cinc_service.create_lead(user_id, lead_data)
        return created_lead
    except HTTPException as e:
        raise e # Forward errors from service layer (e.g., validation error from CINC)
    except Exception as e:
        print(f"Error creating CINC lead for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create CINC lead: {str(e)}")

@app.put("/cinc/user/{user_id}/leads/{lead_id}")
async def update_cinc_lead_for_user(user_id: str, lead_id: str, lead_data: dict):
    """Updates an existing lead in CINC for the specified user and lead_id."""
    try:
        updated_lead = await cinc_service.update_lead(user_id, lead_id, lead_data)
        return updated_lead
    except HTTPException as e:
        raise e # Forward errors from service layer
    except Exception as e:
        print(f"Error updating CINC lead {lead_id} for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update CINC lead: {str(e)}")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
