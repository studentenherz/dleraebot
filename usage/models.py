from sqlalchemy import Column, BigInteger, Integer, Boolean, Date
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class User(Base):
	__tablename__ = 'users'
	tgid = Column(BigInteger, primary_key=True)
	subscribed = Column(Boolean, default=False)
	blocked = Column(Boolean, default=False)
	in_bot = Column(Boolean, default=False)
	messages = Column(Integer, default=0)
	queries = Column(Integer, default=0)
	last_used = Column(Date, nullable=True)

class DayUsage(Base):
	__tablename__ = 'day_usage'
	day = Column(Date, primary_key=True)
	messages = Column(Integer, default=0)
	queries = Column(Integer, default=0)
	users = Column(Integer, default=0)
	new_users = Column(Integer, default=0)
