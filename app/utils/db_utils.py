# app/utils/db_utils.py
from sqlalchemy.orm import Session
from app.models.base import SessionLocal
from app.models.conversation import Conversation

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def save_conversation(db: Session, call_id: str, speaker: str, message: str):
    conversation_entry = Conversation(call_id=call_id, speaker=speaker, message=message)
    db.add(conversation_entry)
    db.commit()
    db.refresh(conversation_entry)
    return conversation_entry
