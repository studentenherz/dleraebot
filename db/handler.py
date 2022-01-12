import os
import sqlalchemy
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import datetime

from .models import Base, User, Usage
from .settings import db_name, db_location

import logging

LESSINFO = logging.INFO + 5
class MyLogger(logging.getLoggerClass()):
    def __init__(self, name, level=logging.NOTSET):
        super().__init__(name, level)

        logging.addLevelName(logging.INFO + 5, 'LESSINFO')

    def lessinfo(self, msg, *args, **kwargs):
        if self.isEnabledFor(LESSINFO):
            self._log(LESSINFO, msg, args, **kwargs)

logging.setLoggerClass(MyLogger)
logger = logging.getLogger(__name__)

formatter = logging.Formatter(
    '%(asctime)s (%(filename)s:%(lineno)d %(threadName)s) %(levelname)s - %(name)s: "%(message)s"'
)

console_output_handler = logging.StreamHandler()
console_output_handler.setFormatter(formatter)
logger.addHandler(console_output_handler)

logger.setLevel(LESSINFO)

# Create an engine that stores data in the local directory's
# sqlalchemy_example.db file.
engine = create_engine('sqlite:///'+ db_location + '//' + db_name, connect_args={'check_same_thread': False})


if not db_name in os.listdir(db_location):
		logger.lessinfo('Not db found, creating one...')
		# Create all tables in the engine. This is equivalent to "Create Table"
		# statements in raw SQL.
		Base.metadata.create_all(engine)
else:
		# Bind the engine to the metadata of the Base class so that the
		# declaratives can be accessed through a DBSession instance
		Base.metadata.bind = engine


DBSession = sessionmaker(bind=engine)
# A DBSession() instance establishes all conversations with the database
# and represents a "staging zone" for all the objects loaded into the
# database session object. 
s = DBSession()

############################
###### GETTING DATA  #######         
############################

def get_usage(day):
	result = s.query(Usage).filter(Usage.day == day)
	if result:            
		try:
			return result.one()
		except sqlalchemy.orm.exc.NoResultFound:
			logger.lessinfo(f'No usage found for {day}')
			update_usage(0, 0, 0)
			# try again
			return get_usage(day)

def get_users_count(subscribed = None, blocked = None):
	result = s.query(User)
	if subscribed != None:
		result = result.filter(User.subscribed == subscribed)
	if blocked != None:
		result = result.filter(User.blocked == blocked)
	return result.count()

def get_users(subscribed = None, blocked = None):
	result = s.query(User)
	if subscribed != None:
		result = result.filter(User.subscribed == subscribed)
	if blocked != None:
		result = result.filter(User.blocked == blocked)
	return result.all()

def get_users(subscribed = None, blocked = None):
	result = s.query(User)
	if subscribed != None:
		result = result.filter(User.subscribed == subscribed)
	if blocked != None:
		result = result.filter(User.blocked == blocked)
	return result.all()

def get_user(tgid):
	try: 
		user = s.query(User).filter(User.tgid == tgid).one()
		return user
	except sqlalchemy.orm.exc.NoResultFound:
		pass

############################
###### SETTING DATA  #######         
############################

def update_user(tgid, subscribed = None, blocked = None, messages = None, queries = None, strict = None):
	"""
		Updates user, returns 0 if it edited user and 1 if it added the user
	"""
	try: 
		user = s.query(User).filter(User.tgid == tgid).one()
		updated = False
		if subscribed != None:
			updated = updated or (user.subscribed != subscribed)
			user.subscribed = subscribed
		if blocked != None:
			updated = updated or (user.blocked != blocked)
			user.blocked = blocked
		if messages:
			updated = updated or (user.messages != messages)
			user.messages = messages
		if queries:
			updated = updated or (user.queries != queries)
			user.queries = queries
		s.add(user)
		s.commit()
		if updated: 
			logger.lessinfo(f'Update user ==> id: {user.tgid}; subscribed: {user.subscribed}; blocked: {user.blocked}; messages: {user.messages}; queries: {user.queries};')
		return 0
	except sqlalchemy.orm.exc.NoResultFound:
		if strict: # dont create
			return 0
		s.add(User(tgid=tgid, subscribed=subscribed, blocked=blocked, messages=messages, queries=queries))
		s.commit()
		logger.lessinfo(f'Added user ==> id: {tgid}; subscribed: {subscribed}; blocked: {blocked}; messages: {messages}; queries: {queries};')
		return 1


############################
######  FOR THE USE  #######         	
############################

def subscribe_user(tgid):
	update_user(tgid, subscribed=True)

def unsubscribe_user(tgid):
	update_user(tgid, subscribed=False)

def block_user(tgid):
	update_user(tgid, blocked=True, strict=True)
	logger.lessinfo(f'Blocked user {tgid}')

def unblock_user(tgid):
	update_user(tgid, blocked=False, strict=True)
	logger.lessinfo(f'Unblocked user {tgid}')

def get_susbcribed_ids():
	subs = get_users(subscribed=True, blocked=False)
	return [sub.tgid for sub in subs]

def get_blocked_ids():
	blocked_list = get_users(blocked=True)
	return [blocked.tgid for blocked in blocked_list]

def add_user(tgid):
	return update_user(tgid, blocked=False)

def is_subscribed(tgid):
	user = get_user(tgid)
	if not user:
		add_user(tgid)
		return False
	else:
		return user.subscribed


def update_usage(messages, queries, users):
	"""
		Updates usage, returns 0 if it edited usage and 1 if it added the usage
	"""
	try:
		day_usage = s.query(Usage).filter(Usage.day == datetime.date.today()).one()
		day_usage.messages = messages
		day_usage.queries = queries
		day_usage.users = users
		s.add(day_usage)
		s.commit()
		# logger.lessinfo('Usage data updated')
		return 0
	except sqlalchemy.orm.exc.NoResultFound:
		logger.lessinfo('Creating new day usage row.')
		s.add(Usage(day=datetime.date.today(), messages=messages, queries=queries, users=users))
		s.commit()
		return 1

def get_usage_last(ndays):
	result = s.query(Usage).order_by(Usage.day.desc()).limit(ndays)
	if result:            
		try:
			return result.all()
		except sqlalchemy.orm.exc.NoResultFound:
			logger.lessinfo(f'No usage data found.')
			update_usage(0, 0, 0)
			# try again
			return get_usage_last(ndays)