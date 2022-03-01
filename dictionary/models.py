from sqlalchemy import Column, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import JSONB

Base = declarative_base()

class Word(Base):
	__tablename__ = 'DLE'
	lemma = Column(String(24), primary_key=True) # longest word in spanish is "electroencefalografista" with 23 characters
	definition = Column(Text)
	conjugation = Column(JSONB, nullable=True)
