from fastapi import APIRouter, Depends
from typing import List
from sqlalchemy.orm import Session
from app.models.base import SessionLocal
from app.models.knowledge_base import KnowledgeBase
from app.services.knowledge_base_service import (
    create_knowledge_entry,
    get_knowledge_entry,
    update_knowledge_entry,
    delete_knowledge_entry,
    list_knowledge_entries
)

router = APIRouter()

# Dependency to get the DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/knowledge/")
def create_knowledge(question: str, answer: str, db: Session = Depends(get_db)):
    return create_knowledge_entry(db, question, answer)

@router.get("/knowledge/{question}")
def read_knowledge(question: str, db: Session = Depends(get_db)):
    return get_knowledge_entry(db, question)

@router.put("/knowledge/{entry_id}")
def update_knowledge(entry_id: int, question: str, answer: str, db: Session = Depends(get_db)):
    return update_knowledge_entry(db, entry_id, question, answer)

@router.delete("/knowledge/{entry_id}")
def delete_knowledge(entry_id: int, db: Session = Depends(get_db)):
    return delete_knowledge_entry(db, entry_id)

@router.get("/knowledge/")
def list_knowledge(db: Session = Depends(get_db)):
    return list_knowledge_entries(db)
