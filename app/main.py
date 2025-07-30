# app/main.py
import uvicorn
import logging
from dotenv import load_dotenv
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
from fastapi import FastAPI, Request,Header, Depends, WebSocket, HTTPException
from fastapi.responses import PlainTextResponse, FileResponse, JSONResponse, RedirectResponse # Keep RedirectResponse
from app.services.call_handler import CallHandler
from contextlib import asynccontextmanager
from fastapi import UploadFile, File
from pathlib import Path
from app.config import settings # Ensure settings is imported to access frontend_url
from app.services.backend_service import BackendHandler
from fastapi.middleware.cors import CORSMiddleware
from app.services.nango_service import NangoService # Added NangoService import back
from app.services.cinc_service import CincService # Import the new unified CincService
from app.services import cinc_webhook_service # Import the webhook service
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
cinc_service_instance = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global call_handler_instance, cinc_service_instance
    call_handler_instance = CallHandler()
    cinc_service_instance = CincService()
    yield
    # Cleanup code if needed

app.router.lifespan_context = lifespan


def get_call_handler():
    return call_handler_instance

def get_cinc_service():
    return cinc_service_instance
    
@app.post("/new-cinc-lead")
async def receive_webhook(
    request: Request,
    x_webhook_secret: Optional[str] = Header(None),
    call_handler: CallHandler = Depends(get_call_handler),
    cinc_service: CincService = Depends(get_cinc_service)
):
    try:
        if not x_webhook_secret:
            raise HTTPException(status_code=401, detail="Missing X-Webhook-Secret")
        
        logger.info(f"📥 Webhook received with secret: {x_webhook_secret}")


        # Get connection info by secret (which is actually the connection_id)
        connection = await BackendHandler().get_connection_by_id(x_webhook_secret)
       
        # Check if the connection_id from backend matches the x_webhook_secret
        if not connection or connection.get("connection_id") != x_webhook_secret:
            logger.error("❌ Webhook secret does not match any valid connection_id")
            raise HTTPException(status_code=403, detail="Invalid or unauthorized webhook secret")

        account_id = connection.get("account_id")
        connection_id = connection.get("connection_id")

        data = await request.json()
        event_type = data.get("type")

        if event_type == "lead.created":
            lead_info = data.get("lead", {})
            lead_id = lead_info.get("id")
            created_by_agent_id = lead_info.get("created_by")
            if lead_id:
                await cinc_webhook_service.fetch_and_trigger_outbound(
                    account_id, lead_id, connection_id, call_handler.update_details, created_by_agent_id
                )
        elif event_type == "agent.communications.received":
            # AI text response detected - cancel outbound call for this phone number
            communication = data.get("communication", {})
            from_info = communication.get("from", {})
            lead_phone = from_info.get("phone_number")
            
            if lead_phone:
                print(f"🤖 AI text found from {lead_phone} - canceling outbound call")
                logger.info(f"🤖 AI text found from {lead_phone} - canceling outbound call")
                await cinc_webhook_service.cancel_outbound_for_ai_response(account_id, lead_phone)
            else:
                print("🤖 AI text found - no outbound call (no phone number)")
                logger.info("🤖 AI text found - no outbound call (no phone number)")
        else:
            logger.info(f"ℹ️ Received event of type: {event_type}")

        return {"status": "success"}

    except Exception as e:
        logger.error(f"❌ Error processing webhook: {e}")
        raise HTTPException(status_code=400, detail="Invalid request")



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
    print(data)
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
    # if fromNumber == settings.boom_number:
    #     # Handle incoming call from Boom number
    #     data = {
    #         "CallDuration" : data.get("CallDuration"),
    #         "From" : fromNumber,
    #         "CallSid" : data.get("CallSid"),
    #     }
    #     response = await BackendHandler.complete_status_callback(data)
    #     return PlainTextResponse(content=str(response), media_type="application/xml")

    # else:
    return await call_handler.complete_status_callback(data)

@app.post("/fallback_status_callback")
async def fallback_status_callback(request: Request, call_handler: CallHandler = Depends(get_call_handler)):
    data = await request.form()
    fromNumber = data.get('From')

    # if fromNumber == settings.boom_number:
    #     # Handle incoming call from Boom number
    #     data = {
    #         "From" : fromNumber,
    #     }
    #     response = await BackendHandler.fallback_status_callback(data)
    #     return PlainTextResponse(content=str(response), media_type="application/xml")

    # else:
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
    if not connection_type:
        raise HTTPException(status_code=400, detail="Connection type is required")
    
    try:
        await NangoService().delete_connect_session(connection_id, connection_type)
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
async def cinc_login(request: Request, state: Optional[str] = None, account_id: Optional[str] = None, cinc_service: CincService = Depends(get_cinc_service)):
    if not account_id:
        raise HTTPException(status_code=400, detail="account_id is required")
    auth_url = cinc_service.get_authorization_url(state=state, account_id=account_id) 
    return RedirectResponse(url=auth_url)

@app.get("/cinc/callback", tags=["CINC Integration"])
async def cinc_callback(
    request: Request, 
    code: Optional[str] = None, 
    error: Optional[str] = None, 
    error_description: Optional[str] = None, 
    state: Optional[str] = None,
    cinc_service: CincService = Depends(get_cinc_service)
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
        redirect_params['error'] = error
        redirect_params['error_description'] = error_description
    elif code:
        try:
            # Exchange code for token
            token_data = await cinc_service.exchange_code_for_token(code, state)
            
            # Extract connection_id and account_id for the redirect
            redirect_params['connection_id'] = token_data.get('connection_id')
            redirect_params['account_id'] = account_id_from_state
            redirect_params['success'] = 'true'

        except HTTPException as e:
            redirect_params['error'] = 'token_exchange_failed'
            redirect_params['error_description'] = str(e.detail)
        except Exception as e:
            redirect_params['error'] = 'unknown_error'
            redirect_params['error_description'] = str(e)
    
    # Construct final redirect URL
    redirect_url = f"{base_redirect_url}?{'&'.join([f'{k}={v}' for k, v in redirect_params.items()])}"
    return RedirectResponse(url=redirect_url)


@app.post("/cinc/account/{account_id}/disconnect")
async def disconnect_cinc_integration(account_id: str, cinc_service: CincService = Depends(get_cinc_service)):
    try:
        # Delete CINC tokens using the correct method name
        await cinc_service.delete_tokens(int(account_id))
        return {"status": "success", "message": f"Integration for account {account_id} disconnected."}
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error disconnecting CINC integration for account {account_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to disconnect integration.")
     
# ==================== OUTBOUND CADENCE ENDPOINTS ====================

@app.get("/api/leads/check-phone-status/{phone}")
async def check_lead_phone_status(
    phone: str,
    account_id: int,
    connection_id: Optional[str] = None,
    cinc_service: CincService = Depends(get_cinc_service)
):
    """
    Get lead pipeline info by phone number for outbound cadence checking.
    """
    try:
        logger.info(f"Checking phone status for {phone} with account_id {account_id}")
        
        # Get pipeline info by phone number
        pipeline_info = await cinc_service.get_pipeline_by_phone(account_id, phone, connection_id)
        print("Pipeline info:", pipeline_info)
        
        # Check if lead exists and what stage it's in
        lead_exists = pipeline_info is not None and pipeline_info.get('lead_exists', False)
        current_stage = pipeline_info.get('stage') if pipeline_info else None
        is_contacted = current_stage == 'Contacted' if current_stage else False
        
        response_data = {
            "phone": phone,
            "pipeline_info": pipeline_info,
            "lead_exists": lead_exists,
            "current_stage": current_stage,
            "is_contacted": is_contacted,
            "account_id": account_id,
            "status": "success"
        }
        
        logger.info(f"Lead status for {phone}: exists={lead_exists}, stage={current_stage}, contacted={is_contacted}")
        return JSONResponse(
            status_code=200,
            content=response_data,
            headers={"Connection": "close"}
        )
        
    except Exception as e:
        logger.error(f"Error fetching pipeline info for phone {phone}: {e}")
        error_response = {
            "phone": phone,
            "pipeline_info": None,
            "error": str(e),
            "account_id": account_id,
            "status": "error"
        }
        return JSONResponse(
            status_code=500,
            content=error_response,
            headers={"Connection": "close"}
        )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
