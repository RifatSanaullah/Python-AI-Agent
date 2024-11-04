# app/models/conversation.py
from sqlalchemy import Column, Integer, String, Text, DateTime
from datetime import datetime
from app.models.base import Base

class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(Integer, primary_key=True, index=True)
    call_id = Column(String, index=True)
    speaker = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
