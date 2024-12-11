# app/main.py
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Depends, WebSocket
from fastapi.responses import PlainTextResponse
from app.models.base import init_db
from app.services.call_handler import CallHandler
from app.utils.db_utils import get_db
from app.routes import knowledge_base
from contextlib import asynccontextmanager

load_dotenv()

app = FastAPI(
    title="BoomerCall API",
    description="API for Voice Assistant",
    version="0.0.2",
)

app.include_router(knowledge_base.router, prefix="/api", tags=["knowledge_base"])

# Initialize
init_db()

# Create a global CallHandler instance
call_handler_instance = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global call_handler_instance
    db = next(get_db())
    call_handler_instance = CallHandler(db)
    yield
    # Cleanup code if needed

app.router.lifespan_context = lifespan

def get_call_handler():
    return call_handler_instance

@app.websocket("/audio-stream")
async def audio_stream(websocket: WebSocket, call_handler: CallHandler = Depends(get_call_handler)):
    await call_handler.process_input(websocket)

@app.post("/incoming_call")
async def incoming_call(request: Request, call_handler: CallHandler = Depends(get_call_handler)):
    data = await request.form()
    call_id = data.get("CallSid")
    response = await call_handler.handle_call(call_id)
    return PlainTextResponse(content=str(response), media_type="application/xml")

@app.post("/outgoing_call")
async def outgoing_call(phone_number: str, call_handler: CallHandler = Depends(get_call_handler)):
    call_sid = await call_handler.make_outgoing_call(phone_number)
    return {"call_sid": call_sid}

@app.post("/stream_callback")
async def stream_callback(request: Request, call_handler: CallHandler = Depends(get_call_handler)):
    data = await request.form()
    return await call_handler.handle_stream_callback(data)

@app.get('/robots.txt', response_class=PlainTextResponse,include_in_schema=False)
def robots():
    data = """User-agent: *\nDisallow: /"""
    return data
