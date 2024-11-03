from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get the database URL from the environment variables
DATABASE_URL = os.getenv("DATABASE_URL")

# Set up SQLAlchemy engine, session, and base class
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Define the Conversation table to store conversation details
class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    client_input = Column(Text, nullable=False)
    gpt_response = Column(Text, nullable=False)
    timestamp = Column(DateTime, nullable=False)

# Create all tables in the database (should be run once, e.g., at app startup)
def init_db():
    Base.metadata.create_all(bind=engine)

