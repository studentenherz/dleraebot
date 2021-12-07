from sqlalchemy import Column, Integer, Boolean, Date
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class User(Base):
	__tablename__ = 'user'
	tgid = Column(Integer, primary_key=True)
	subscribed = Column(Boolean, default=False)
	blocked = Column(Boolean, default=False)
	messages = Column(Integer, nullable=True)
	queries = Column(Integer, nullable=True)

class Usage(Base):
	__tablename__ = 'usage'
	day = Column(Date, primary_key=True)
	messages = Column(Integer, nullable=True)
	queries = Column(Integer, nullable=True)
	users = Column(Integer, nullable=True)
