import os
import sqlalchemy
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import datetime

from sqlalchemy.sql.expression import update

from .models import Base, User, Usage
from .settings import db_name, db_location

# Create an engine that stores data in the local directory's
# sqlalchemy_example.db file.
engine = create_engine('sqlite:///'+ db_location + '//' + db_name, connect_args={'check_same_thread': False})


if not db_name in os.listdir(db_location):
		print('Not db found, creating one')
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
			print('No usage found get_usage')

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

def update_user(tgid, subscribed = None, blocked = None, messages = None, queries = None):
	"""
		Updates user, returns 0 if it edited user and 1 if it added the user
	"""
	try: 
		user = s.query(User).filter(User.tgid == tgid).one()
		if subscribed != None:
			user.subscribed = subscribed
		if blocked != None:
			user.blocked = blocked
		if messages:
			user.messages = messages
		if queries:
			user.queries = queries
		s.add(user)
		s.commit()
		return 0
	except sqlalchemy.orm.exc.NoResultFound:
		s.add(User(tgid=tgid, subscribed=subscribed, blocked=blocked, messages=messages, queries=queries))
		s.commit()
		return 1


############################
######  FOR THE USE  #######         
############################

def subscribe_user(tgid):
	update_user(tgid, subscribed=True)

def unsubscribe_user(tgid):
	update_user(tgid, subscribed=False)

def block_user(tgid):
	update_user(tgid, blocked=True)

def unblock_user(tgid):
	update_user(tgid, blocked=False)

def get_susbcribed_ids():
	subs = get_users(subscribed=True, blocked=False)
	return [sub.tgid for sub in subs]

def add_user(tgid):
	return update_user(tgid)

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
		return 0
	except sqlalchemy.orm.exc.NoResultFound:
		print('New day usage')
		s.add(Usage(day=datetime.date.today(), messages=messages, queries=queries, users=users))
		s.commit()
		return 1

def get_usage_last(ndays):
	result = s.query(Usage).order_by(Usage.day.desc()).limit(ndays)
	if result:            
		try:
			return result.all()
		except sqlalchemy.orm.exc.NoResultFound:
			print('No usage found get_usage')
