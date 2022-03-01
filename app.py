from telebot import types
from credentials import bot_token, admin_id, bot_username, HOST_URL, local_server, bot_channel_username, bot_discuss_username
from db.handler import subscribe_user, unsubscribe_user, add_user, is_subscribed, get_users_ids, get_users_count, update_usage, get_usage_last, get_usage, block_user, unblock_user, get_blocked_ids
import datetime
import logging
import asyncio 
import aiohttp
from telebot.async_telebot import AsyncTeleBot
from telebot.asyncio_helper import ApiTelegramException
from aiohttp import web
from telebot import asyncio_helper
from telebot.util import smart_split
from dictionary.handler import get_definition, get_list, get_random, async_pg_session, get_word_of_the_day

import logging

LESSINFO = logging.INFO + 5
class MyLogger(logging.getLoggerClass()):
		def __init__(self, name, level=logging.NOTSET):
				super().__init__(name, level)

				logging.addLevelName(logging.INFO + 5, 'LESSINFO')

		def verbose(self, msg, *args, **kwargs):
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

if local_server != None:
	asyncio_helper.API_URL = local_server + "/bot{0}/{1}"
	asyncio_helper.FILE_URL = local_server

bot = AsyncTeleBot(bot_token)

app = web.Application()
pg_session = async_pg_session()


# Definition of constants

MSG_START = f'No es necesario que inicies un chat con el bot para que funcione, tampoco es necesario que lo agregues a ningún grupo o canal (/ayuda para más información), pero ya que estás aquí te cuento algunas cosas:\n\n - los comandos están en español porque es un bot para obtener definiciones de palabras en español 😅.\n\n -Hace un tiempo le escribí a la RAE (a través de un formulario en su página web, quizá nunca me leyeron) proponiéndoles la idea de que hicieran este bot, si quisieran problablemente Telegram les diese un @ más corto como @dle y la marca de bot oficial.\n\nPuedes ver el código del bot en [GitHub](https://github.com/studentenherz/dleraebot), y puedes recibir noticias acerca del bot en @{bot_channel_username}.'

MSG_AYUDA = f'Simplemente, envía un mensaje de texto donde solo esté la palabra que deseas buscar, respetando su correcta escritura incluyendo tildes.\n\n Si quieres acceder rápidamente a una definición desde cualquier otro chat, escribe @{bot_username}  y luego la palabra que deseas buscar, en unos segundos aparecerán las opciones compatibles. Si no te queda claro puedes ver un gif de ejemplo con /ejemplo.\n\nEn las definiciones se pueden encontrar algunas abreviaturas cuyo significado puedes ver <a href="https://t.me/dleraebotchannel/10">aquí</a>.'
MSG_EJEMPLO = 'CgACAgEAAxkBAAMWYSSF83hFhvdaCGrKA8S7RIogjn8AAqcCAAI3gSBFIvdrsiI9VIwgBA'
MSG_NO_RESULT = 'No se han encontrado resultados'
MSG_NO_RESULT_LONG = 'Lo siento, no se han encontrado resultados. Intenta letra por letra y quizá la palabra que buscas esté entre las opciones.'
MSG_PDD = '📖 Palabra del día\n\n {}'
MSG_NO_RESULT_DIRECT_MESSAGE = 'Lo siento, no se han encontrado resultados para «{}». Debes enviar un mensaje de texto que contenga solo el término que deseas buscar y respetando su correcta escritura incluyendo tildes. Si no sabes cómo se escribe intenta el modo <i>inline</i> donde verás sugerencias mientras escribes.'
MSG_PDD_SUSB = '{}, aquí puedes manejar tu suscripción a la 📖 <i>Palabra del día</i> para que la recibas diariamente. Actualmente {} estás suscrito, pero si lo prefieres puedes cambiar.'

KEY_PDD = '📖 Palabra del día'
KEY_ALEATORIO = '🎲 Palabra aleatoria'
KEY_AYUDA = '❔ Ayuda'
KEY_SUSCRIPCION = '🔔 Suscripción'

REPLY_KEYBOARD = types.ReplyKeyboardMarkup(resize_keyboard=True)
REPLY_KEYBOARD.row(types.KeyboardButton(KEY_ALEATORIO), types.KeyboardButton(KEY_PDD))
REPLY_KEYBOARD.row(types.KeyboardButton(KEY_SUSCRIPCION), types.KeyboardButton(KEY_AYUDA))

INLINE_KEYBOARD_BUSCAR_DEFINICION = types.InlineKeyboardMarkup()
INLINE_KEYBOARD_BUSCAR_DEFINICION.row(types.InlineKeyboardButton('Buscar definición', switch_inline_query=f''))

INLINE_KEYBOARD_BUSCAR_DEFINICION_CURRENT_CHAT = types.InlineKeyboardMarkup()
INLINE_KEYBOARD_BUSCAR_DEFINICION_CURRENT_CHAT.row(types.InlineKeyboardButton('Buscar definición', switch_inline_query_current_chat=f''))

# Global variables
word_of_the_day = ''
wotd_definitions = []

new_users = set()
new_inline_searches = 0
new_searches = 0
actually_new_count = 0

# Wrapper around bot.send_message for blocked users
async def bot_send_message(*args, **kwargs):
	try:
		await bot.send_message(*args, **kwargs)
	except ApiTelegramException as e:
		logger.error(f'In sendMessage({args}, {kwargs}) {e.result_json}')
		if len(args) > 0:
			id = int(args[0])
		else:
			id = int(kwargs['chat_id'])
		block_user(id)

# Bot queries

@bot.inline_handler(lambda query: len(query.query) > 0)
async def inline_query_handler(query):
	try:
		res = [] # inline query results
		async def add_res(i, entry, pg_session):
			definition, _ = await get_definition(entry, pg_session) # get definition, might be spread in several messages
			for idx, definition_text in enumerate(smart_split(definition)):
				definition = types.InputTextMessageContent(definition_text, parse_mode='HTML')
				r = types.InlineQueryResultArticle(f'{i}_{idx}', title=entry, input_message_content=definition, description=definition_text)
				res.append((f'{i}_{idx}',r))

		tasks = [] # concurrent tasks
		words_list = await get_list(query.query, pg_session)
		for i, word in enumerate(words_list):
			tasks.append(add_res(i, word, pg_session))
		await asyncio.gather(*tasks, return_exceptions=True)
		
		res.sort() # alphabetic sort
		res = [x[1] for x in res]

		if len(res) == 0:
			await bot.answer_inline_query(query.id, res, switch_pm_text=MSG_NO_RESULT, switch_pm_parameter='no_result')
		else:
			await bot.answer_inline_query(query.id, res)
		
	except Exception:
		logger.exception('Something went wrong:\n')

@bot.message_handler(commands=['start'])
async def start_handler(message):
	if message.chat.type == 'private':
		if 'no_result' in message.text:
			await bot_send_message(message.chat.id, MSG_NO_RESULT_LONG, parse_mode='markdown', disable_web_page_preview=True, reply_markup=INLINE_KEYBOARD_BUSCAR_DEFINICION)
		else:
			await bot_send_message(message.chat.id, MSG_START, parse_mode='markdown', disable_web_page_preview=True, reply_markup=REPLY_KEYBOARD)
			new_users.add(message.from_user.id)

@bot.message_handler(commands=['ayuda', 'help'])
async def help_handler(message):
	await	bot_send_message(message.chat.id, MSG_AYUDA, reply_markup=INLINE_KEYBOARD_BUSCAR_DEFINICION, parse_mode='HTML', disable_web_page_preview=True)

@bot.message_handler(commands=['ejemplo'])
async def ejemplo_handler(message):
	await bot.send_animation(message.chat.id, MSG_EJEMPLO)

@bot.message_handler(commands=['aleatorio'])
async def aleatorio_handler(message):
	await bot.send_chat_action(message.chat.id, 'typing')
	definition, _ = await get_random(pg_session)
	for page in smart_split(definition):
		await	bot_send_message(message.chat.id, page, parse_mode='HTML')

async def update_word_of_the_day():
	global word_of_the_day, wotd_definitions

	word_of_the_day = await get_word_of_the_day(datetime.date.today(), pg_session)
	wotd_definition, _ = await get_definition(word_of_the_day, pg_session) # ex.: cabalístico, ca
	wotd_definitions = smart_split(wotd_definition)

async def send_word_of_the_day(chat_id):
	if word_of_the_day == '':
		await bot.send_chat_action(chat_id, 'typing')
		await update_word_of_the_day()
	await	bot_send_message(chat_id, MSG_PDD.format(wotd_definitions[0].lstrip()), parse_mode='HTML')	
	for page in wotd_definitions[1:]:
		await	bot_send_message(chat_id, page, parse_mode='HTML')


@bot.message_handler(commands=['pdd'])
async def pdd_handler(message):
	await send_word_of_the_day(message.chat.id)

@bot.message_handler(commands=['suscripcion'])
async def suscripcion_handler(message):
	if message.chat.type == 'private':
		tgid = message.from_user.id
		first_name = message.from_user.first_name
		is_sus = is_subscribed(tgid)
		text = MSG_PDD_SUSB.format(first_name, 'SÍ' if is_sus else 'NO')
		keyboard = types.InlineKeyboardMarkup()
		keyboard.row(types.InlineKeyboardButton('Desuscribirme' if is_sus else '¡Suscribirme!', callback_data='desubs' if is_sus else 'subs'))
		await	bot_send_message(message.chat.id, text, reply_markup=keyboard, parse_mode='HTML')

@bot.message_handler(commands=['users'])
async def check_users_handler(message):
	if message.from_user.id == admin_id:
		commands = message.text.split(' ') # /users command
		if len(commands) < 2:
			n = get_users_count()
		elif commands[1] == 's':
			n = get_users_count(subscribed=True)
		await	bot_send_message(admin_id, f'{n} users')

@bot.message_handler(commands=['usage'])
async def check_usage_handler(message):
	if message.from_user.id == admin_id:
		commands = message.text.split(' ') # /usage ndays
		if len(commands) < 2:
			ndays = 1
		else:
			try:
				ndays = int(commands[1])
			except:
				ndays = 1
		
		usage_list = get_usage_last(ndays)

		text = '<pre>     ....:: Usage Stats ::....      \n\n   day   | users | messages | inline\n------------------------------------</pre>\n'
		
		
		for u in usage_list:
			users = str(u.users)
			messages = str(u.messages)
			queries = str(u.queries)
			users = (' ' * (len('users') - len(users))) + users
			messages = (' ' * (len('messages') - len(messages))) + messages
			queries = (' ' * (len('inline') - len(queries))) + queries

			text += f'<pre>{u.day.strftime("%d/%m/%y")} | {users} | {messages} | {queries}\n</pre>\n'

		text += f'<pre>Total users: {get_users_count()}</pre>\n'
		text += f'<pre>Subscribed users: {get_users_count(subscribed=True)}</pre>\n'

		await	bot_send_message(admin_id, text, parse_mode='HTML')

@bot.message_handler(commands=['broadcast_all', 'broadcast'])
async def broadcast_handler(message):
	if message.from_user.id == admin_id:
		lst = message.html_text.split(' ', 1)
		text = lst[1]
		usrs = get_users_ids(only_subscribed=(lst[0] == '/broadcast'))

		keyboard = types.InlineKeyboardMarkup([[types.InlineKeyboardButton('¿Algún problema? Cuéntanos 🔧.', url=f'https://t.me/{bot_discuss_username}')]])

		tasks = []
		for usrid in usrs:
			tasks.append(bot_send_message(usrid, text, parse_mode='HTML', reply_markup=keyboard))
		
		await asyncio.gather(*tasks)

		log_text = f'Broadcasted Message\n\n {text}\n\n to {len(usrs)} users.'
		logger.lessinfo(log_text)
		await bot.send_message(admin_id,'<pre>Log: </pre>' + log_text, parse_mode='HTML')

@bot.message_handler(commands=['blocked'])
async def get_blocked_handler(message):
	if message.from_user.id == admin_id:
		list = get_blocked_ids()

		text = '<pre>.::Blocked users::.'
		for blocked_id in list:
			text += f'\n{blocked_id}'
		text += '</pre>'

		await bot.send_message(admin_id, text, parse_mode='HTML')

@bot.message_handler(commands=['block'])
async def block_user_handler(message):
	if message.from_user.id == admin_id:
		try:
			id = int(message.text.split(' ', 1)[1])
			block_user(id)
		except Exception as e:
			logger.error(f'Bad user id\n {e}')
			await bot.send_message(admin_id, '<pre>Bad user id</pre>', parse_mode='HTML')

@bot.message_handler(commands=['unblock'])
async def unblock_user_handler(message):
	if message.from_user.id == admin_id:
		try:
			id = int(message.text.split(' ', 1)[1])
			unblock_user(id)
		except Exception as e:
			logger.error(f'Bad user id\n {e}')
			await bot.send_message(admin_id, '<pre>Bad user id</pre>', parse_mode='HTML')


@bot.callback_query_handler(lambda query: True)
async def handle_callback_query(query):
	if query.data in ['desubs', 'subs']:
		tgid = query.from_user.id
		new_text = query.message.text
		query_answer= ''

		if query.data == 'subs':
			subscribe_user(tgid)
			new_text += '\n\n ¡Listo!, te has suscrito.'
			query_answer = '✅ ¡Te has suscrito!'
		if query.data == 'desubs':
			unsubscribe_user(tgid)
			new_text += '\n\n ¡Listo!, ya no estás suscrito.'
			query_answer = '❌ Te has desuscrito.'

		await bot.answer_callback_query(query.id, query_answer)
		await bot.edit_message_text(new_text, query.message.chat.id, query.message.id)

keyboard_command_function = {
	KEY_PDD : pdd_handler,
	KEY_ALEATORIO: aleatorio_handler,
	KEY_AYUDA: help_handler,
	KEY_SUSCRIPCION: suscripcion_handler
}

@bot.message_handler(content_types=['text'])
async def text_messages_handler(message):
	global new_searches, new_users

	if message.chat.type == 'private':
		new_users.add(message.from_user.id) # add user
		if message.text in keyboard_command_function:
			await keyboard_command_function[message.text](message)
		elif not message.via_bot or message.via_bot.id != (await bot.get_me()).id:
			new_searches += 1 # incdrement searches
			word = message.text.split()[0].lower()

			list = await get_list(word, pg_session)
			if word in list:
				await bot.send_chat_action(message.chat.id, 'typing')
				definition, _ = await get_definition(word, pg_session)
				for definition_text in smart_split(definition):
					await bot_send_message(message.chat.id, definition_text, parse_mode='HTML', reply_markup=REPLY_KEYBOARD)
			else:
				await bot_send_message(message.chat.id, MSG_NO_RESULT_DIRECT_MESSAGE.format(word), parse_mode='HTML',reply_markup=INLINE_KEYBOARD_BUSCAR_DEFINICION_CURRENT_CHAT)

@bot.chosen_inline_handler(lambda query: True)
async def handle_chosen_inline(result):
	global new_users, new_inline_searches
	new_users.add(result.from_user.id) # add user
	new_inline_searches += 1 # increment inline searches


async def broadcast_word_of_the_day(req = word_of_the_day):
	# logger.lessinfo('Broadcasting')
	await update_word_of_the_day()
	subs = get_users_ids()

	tasks = []
	for sub_id in subs:
		tasks.append(send_word_of_the_day(sub_id))

	await asyncio.gather(*tasks)

	log_text = f'Broadcasted Word Of The Day to {len(subs)} users.'
	logger.lessinfo(log_text)
	await bot.send_message(admin_id,'<pre>Log: </pre>' + log_text, parse_mode='HTML')

	return web.Response()

async def update_database(req = None):
	# logger.lessinfo('Updating database')
	global actually_new_count, new_searches, new_inline_searches

	# update users
	for utgid in new_users:
		actually_new_count += add_user(utgid)

	#update usage
	is_new_day = update_usage(new_searches, new_inline_searches, actually_new_count)

	if is_new_day == 1:
		new_searches = 0
		new_inline_searches = 0
		actually_new_count = 0
		new_users.clear()

	return web.Response()

def init():
	global actually_new_count, new_searches, new_inline_searches
	today_usage = get_usage(datetime.date.today())

	if today_usage:
		actually_new_count = today_usage.users
		new_inline_searches = today_usage.queries
		new_searches = today_usage.messages

# Webapp 
async def handle_webhook(request):
	request_body_dict = await request.json()
	print(request_body_dict)
	update = types.Update.de_json(request_body_dict)
	await bot.process_new_updates([update])
	return web.Response()

async def handle_set_webhook(request):
	await bot.set_webhook(url=f'{HOST_URL}/{bot_token}')
	return web.Response(text='Webhook set (hopefully)!')

app.router.add_post(f'/{bot_token}', handle_webhook)
app.router.add_get(f'/{bot_token}/updateDB', update_database)
app.router.add_get(f'/{bot_token}/broadcastWOTD', broadcast_word_of_the_day)
app.router.add_get(f'/{bot_token}/setWebhook', handle_set_webhook)

init()

if __name__ == '__main__':
	web.run_app(
		app
	)