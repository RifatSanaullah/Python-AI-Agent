from sqlalchemy.orm import Session
from app.models.knowledge_base import KnowledgeBase

def create_knowledge_entry(db: Session, question: str, answer: str):
    db_entry = KnowledgeBase(question=question, answer=answer)
    db.add(db_entry)
    db.commit()
    db.refresh(db_entry)
    return db_entry

def get_knowledge_entry(db: Session, question: str):
    return db.query(KnowledgeBase).filter(KnowledgeBase.question == question).first()

def update_knowledge_entry(db: Session, entry_id: int, question: str, answer: str):
    entry = db.query(KnowledgeBase).filter(KnowledgeBase.id == entry_id).first()
    if entry:
        entry.question = question
        entry.answer = answer
        db.commit()
        return entry
    return None

def delete_knowledge_entry(db: Session, entry_id: int):
    entry = db.query(KnowledgeBase).filter(KnowledgeBase.id == entry_id).first()
    if entry:
        db.delete(entry)
        db.commit()
        return True
    return False

def list_knowledge_entries(db: Session):
    return db.query(KnowledgeBase).all()
