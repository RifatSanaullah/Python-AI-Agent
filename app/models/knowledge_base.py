from sqlalchemy import Column, Integer, String, Text
from app.models.base import Base

class KnowledgeBase(Base):
    __tablename__ = "knowledge_base"

    id = Column(Integer, primary_key=True, index=True)
    question = Column(String(255), unique=True, index=True)
    answer = Column(Text, nullable=False)

    def __repr__(self):
        return f"<KnowledgeBase(id={self.id}, question={self.question})>"
