from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select
from sqlalchemy import update, func
from .models import User, DayUsage, Base
import logging
import os
from datetime import date

# Logging setup
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

log_formatter = logging.Formatter('▸ %(asctime)s:%(name)s:%(levelname)s: %(message)s')
log_file_handler = logging.FileHandler('getfulldle.log')
log_file_handler.setLevel(logging.ERROR)
log_file_handler.setFormatter(log_formatter)

log_stream_handler = logging.StreamHandler()
log_stream_handler.setFormatter(log_formatter)

logger.addHandler(log_file_handler)
logger.addHandler(log_stream_handler)

engine = create_async_engine(f'postgresql+asyncpg://{os.environ["USAGE_DB_USER"]}:{os.environ["USAGE_DB_PASSWORD"]}@{os.environ["USAGE_DB_HOST"]}:{os.environ["USAGE_DB_PORT"]}/{os.environ["USAGE_DB_NAME"]}')
async_pg_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def add_message(tgid, pg_session):
	today = date.today()

	# create usage for today if not exists
	res = await pg_session.execute(select(func.count()).select_from(DayUsage).filter(DayUsage.day == today))
	if res.scalar_one() == 0:
		pg_session.add(DayUsage(day=today))

	# check if user already exists
	res = await pg_session.execute(select(func.count()).select_from(User).filter(User.tgid == tgid))
	# update user
	if res.scalar_one() == 1:
		res = await pg_session.execute(select(User.last_used).select_from(User).filter(User.tgid == tgid))
		last_date = res.scalar_one()

		if last_date and last_date < today or not last_date:
			await pg_session.execute(update(DayUsage).where(DayUsage.day == today).values(users = DayUsage.users + 1))
		
		await pg_session.execute(update(User).where(User.tgid == tgid).values(messages = User.messages + 1, last_used = today))
	# create user
	else:
		pg_session.add(User(tgid=tgid, in_bot=True, messages=1, queries = 0, last_used = today))
		
		await pg_session.execute(update(DayUsage).where(DayUsage.day == today).values(new_users = DayUsage.new_users + 1, users = DayUsage.users + 1))
		logger.info(f'Added user {tgid} from message.')

	await pg_session.execute(update(DayUsage).where(DayUsage.day == today).values(messages = DayUsage.messages + 1))

	await pg_session.commit()




async def add_query(tgid, pg_session):
	today = date.today()

	# create usage for today if not exists
	res = await pg_session.execute(select(func.count()).select_from(DayUsage).filter(DayUsage.day == today))
	if res.scalar_one() == 0:
		pg_session.add(DayUsage(day=today))

	# check if user already exists
	res = await pg_session.execute(select(func.count()).select_from(User).filter(User.tgid == tgid))
	# update user
	if res.scalar_one() == 1:
		res = await pg_session.execute(select(User.last_used).select_from(User).filter(User.tgid == tgid))
		last_date = res.scalar_one()

		if last_date and last_date < today or not last_date:
			await pg_session.execute(update(DayUsage).where(DayUsage.day == today).values(users = DayUsage.users + 1))
		
		await pg_session.execute(update(User).where(User.tgid == tgid).values(queries = User.queries + 1, last_used = today))
	# create user
	else:
		pg_session.add(User(tgid=tgid, in_bot=False, messages=0, queries = 1, last_used = today))
		
		await pg_session.execute(update(DayUsage).where(DayUsage.day == today).values(new_users = DayUsage.new_users + 1, users = DayUsage.users + 1))
		logger.info(f'Added user {tgid} from query.')

	await pg_session.execute(update(DayUsage).where(DayUsage.day == today).values(queries = DayUsage.queries + 1))

	await pg_session.commit()
		
async def set_subscription(tgid, subs, pg_session):
	# check if user already exists
	res = await pg_session.execute(select(func.count()).select_from(User).filter(User.tgid == tgid))
	# update user
	if res.scalar_one() == 1:
		await pg_session.execute(update(User).where(User.tgid == tgid).values(subscribed = subs))

	await pg_session.commit()

async def set_blocked(tgid, blocked, pg_session):
	# check if user already exists
	res = await pg_session.execute(select(func.count()).select_from(User).filter(User.tgid == tgid))
	# update user
	if res.scalar_one() == 1:
		await pg_session.execute(update(User).where(User.tgid == tgid).values(blocked = blocked))

	await pg_session.commit()

async def set_in_bot(tgid, in_bot, pg_session):
	# check if user already exists
	res = await pg_session.execute(select(func.count()).select_from(User).filter(User.tgid == tgid))
	# update user
	if res.scalar_one() == 1:
		await pg_session.execute(update(User).where(User.tgid == tgid).values(in_bot = in_bot))

	await pg_session.commit()

async def is_subscribed(tgid, pg_session):
	# check if user already exists
	res = await pg_session.execute(select(User.subscribed).filter(User.tgid == tgid))
	# update user
	try:
		return res.scalar_one()
	except:
		logger.error(f'User {tgid} is not in the database')
		return False

async def get_users_ids(pg_session, subscribed = None, blocked = None, in_bot = None):
	stmt = select(User.tgid)
	if subscribed != None:
		stmt = stmt.filter(User.subscribed == subscribed)
	if blocked != None:
		stmt = stmt.filter(User.blocked == blocked)
	if in_bot != None:
		stmt = stmt.filter(User.in_bot == in_bot)

	res = await pg_session.execute(stmt)

	return res.scalars().all()

async def get_users_count(pg_session, subscribed = None, blocked = None, in_bot = None, since_day = None):
	stmt = select(func.count()).select_from(User)
	if subscribed != None:
		stmt = stmt.filter(User.subscribed == subscribed)
	if blocked != None:
		stmt = stmt.filter(User.blocked == blocked)
	if in_bot != None:
		stmt = stmt.filter(User.in_bot == in_bot)
	if since_day != None:
		stmt = stmt.filter(User.last_used >= since_day)

	res = await pg_session.execute(stmt)

	return res.scalar_one()

async def get_usage_last(n, pg_session):
	res = await pg_session.execute(select(DayUsage).order_by(DayUsage.day.desc()).limit(n))
	return res.scalars().all()
