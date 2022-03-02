from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select
from sqlalchemy.sql.expression import func
from sqlalchemy import update
from .models import Word
import logging
import os

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

engine = create_async_engine(f'postgresql+asyncpg://{os.environ["DICT_DB_USER"]}:{os.environ["DICT_DB_PASSWORD"]}@{os.environ["DICT_DB_HOST"]}:{os.environ["DICT_DB_PORT"]}/{os.environ["DICT_DB_NAME"]}')
async_pg_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

RES_LIMIT = 10

async def get_list(entry, pg_session):
	res = await pg_session.execute(select(Word.lemma, Word.definition, Word.definition).filter(Word.lemma.ilike(f'{entry}%')).order_by(Word.lemma).limit(RES_LIMIT))
	return res.all()

async def get_definition(entry, pg_session):
	res = await pg_session.execute(select(Word.definition, Word.conjugation).filter(Word.lemma == entry))
	try:
		return res.one()
	except:
		return None, None

async def get_random(pg_session):
	res = await pg_session.execute(select(Word.definition, Word.conjugation).order_by(func.random()).limit(RES_LIMIT))
	first = res.first()
	if first:
		return first
	else:
		return None, None

async def get_word_of_the_day(date, pg_session):
	res = await pg_session.execute(select(Word.lemma).filter(Word.wotd == date))
	first = res.scalars().first()
	if first:
		return first
	else:
		while True:
			random = await pg_session.execute(select(Word.lemma, Word.wotd).order_by(func.random()).limit(RES_LIMIT))
			canditdate = random.first()
			if canditdate[1] == None:
				await pg_session.execute(update(Word).where(Word.lemma == canditdate[0]).values(wotd = date))
				await pg_session.commit()
				return canditdate[0]
