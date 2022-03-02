from telebot import types
from credentials import bot_token, admin_id, bot_username, HOST_URL, local_server, bot_channel_username, bot_discuss_username
import datetime
import logging
import asyncio 
from telebot.async_telebot import AsyncTeleBot
from telebot.asyncio_helper import ApiTelegramException
from aiohttp import web
from telebot import asyncio_helper
from telebot.util import smart_split
from dictionary.handler import get_definition, get_list, get_random, get_word_of_the_day
from dictionary.handler import async_pg_session as dict_session_maker
from usage.handler import add_message, add_query, set_blocked, set_subscription, is_subscribed, get_users_count, get_users_ids, set_in_bot, get_usage_last
from usage.handler import async_pg_session as usage_session_maker
from random import random

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

# db's sessions
dict_pg_session = dict_session_maker()
usage_pg_session = usage_session_maker()


# Definition of constants

MSG_START = f'No es necesario que inicies un chat con el bot para que funcione, tampoco es necesario que lo agregues a ningún grupo o canal (/ayuda para más información), pero ya que estás aquí te cuento algunas cosas:\n\n - los comandos están en español porque es un bot para obtener definiciones de palabras en español 😅.\n\n -Hace un tiempo le escribí a la RAE (a través de un formulario en su página web, quizá nunca me leyeron) proponiéndoles la idea de que hicieran este bot, si quisieran problablemente Telegram les diese un @ más corto como @dle y la marca de bot oficial.\n\nPuedes ver el código del bot en [GitHub](https://github.com/studentenherz/dleraebot), y puedes recibir noticias acerca del bot en @{bot_channel_username}.'

MSG_AYUDA = f'Simplemente, envía un mensaje de texto donde solo esté la palabra que deseas buscar, respetando su correcta escritura incluyendo tildes.\n\n Si quieres acceder rápidamente a una definición desde cualquier otro chat, escribe @{bot_username}  y luego la palabra que deseas buscar, en unos segundos aparecerán las opciones compatibles. Si no te queda claro puedes ver un gif de ejemplo con /ejemplo.\n\nEn las definiciones se pueden encontrar algunas abreviaturas cuyo significado puedes ver <a href="https://t.me/dleraebotchannel/10">aquí</a>.'
MSG_EJEMPLO = 'CgACAgEAAxkBAAMWYSSF83hFhvdaCGrKA8S7RIogjn8AAqcCAAI3gSBFIvdrsiI9VIwgBA'
MSG_NO_RESULT = 'No se han encontrado resultados'
MSG_NO_RESULT_LONG = 'Lo siento, no se han encontrado resultados. Intenta letra por letra y quizá la palabra que buscas esté entre las opciones.'
MSG_PDD = '📖 Palabra del día\n\n {}'
MSG_NO_RESULT_DIRECT_MESSAGE = 'Lo siento, no se han encontrado resultados para «{}». Debes enviar un mensaje de texto que contenga solo el término que deseas buscar y respetando su correcta escritura incluyendo tildes. Si no sabes cómo se escribe intenta el modo <i>inline</i> donde verás sugerencias mientras escribes. También puedes probar buscar directamente en la página de la RAE.'
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

VER_EN_DLE_RAE_ES_PROBABILITY = 0.05

# Global variables
word_of_the_day = ''
wotd_definitions = []

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
		await set_in_bot(id, False, usage_pg_session)

# Bot queries

@bot.inline_handler(lambda query: len(query.query) > 0)
async def inline_query_handler(query):
	try:
		res = [] # inline query results
		words_list = await get_list(query.query, dict_pg_session)
		
		for word, definition, conj in words_list:
			for idx, definition_text in enumerate(smart_split(definition)):
				definition_page = types.InputTextMessageContent(definition_text, parse_mode='HTML')
				res.append(types.InlineQueryResultArticle(f'{word}_{idx}', title=word, input_message_content=definition_page, description=definition_text))
		
		if len(res) == 0:
			await bot.answer_inline_query(query.id, res, switch_pm_text=MSG_NO_RESULT, switch_pm_parameter='no_result')
		else:
			await bot.answer_inline_query(query.id, res)
		
	except Exception:
		logger.exception('Something went wrong:\n')

@bot.message_handler(commands=['start'])
async def start_handler(message):
	await add_message(message.from_user.id, usage_pg_session)
	if message.chat.type == 'private':
		if 'no_result' in message.text:
			await bot_send_message(message.chat.id, MSG_NO_RESULT_LONG, parse_mode='markdown', disable_web_page_preview=True, reply_markup=INLINE_KEYBOARD_BUSCAR_DEFINICION)
		else:
			await bot_send_message(message.chat.id, MSG_START, parse_mode='markdown', disable_web_page_preview=True, reply_markup=REPLY_KEYBOARD)

@bot.message_handler(commands=['ayuda', 'help'])
async def help_handler(message):
	await add_message(message.from_user.id, usage_pg_session)
	await	bot_send_message(message.chat.id, MSG_AYUDA, reply_markup=INLINE_KEYBOARD_BUSCAR_DEFINICION, parse_mode='HTML', disable_web_page_preview=True)

@bot.message_handler(commands=['ejemplo'])
async def ejemplo_handler(message):
	await add_message(message.from_user.id, usage_pg_session)
	await bot.send_animation(message.chat.id, MSG_EJEMPLO)

@bot.message_handler(commands=['aleatorio'])
async def aleatorio_handler(message):
	await add_message(message.from_user.id, usage_pg_session)
	await bot.send_chat_action(message.chat.id, 'typing')
	definition, _ = await get_random(dict_pg_session)
	for page in smart_split(definition):
		await	bot_send_message(message.chat.id, page, parse_mode='HTML')

async def update_word_of_the_day():
	global word_of_the_day, wotd_definitions

	word_of_the_day = await get_word_of_the_day(datetime.date.today(), dict_pg_session)
	wotd_definition, _ = await get_definition(word_of_the_day, dict_pg_session) # ex.: cabalístico, ca
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
	await add_message(message.from_user.id, usage_pg_session)
	await send_word_of_the_day(message.chat.id)

@bot.message_handler(commands=['suscripcion'])
async def suscripcion_handler(message):
	await add_message(message.from_user.id, usage_pg_session)
	if message.chat.type == 'private':
		tgid = message.from_user.id
		first_name = message.from_user.first_name
		is_sus = await is_subscribed(tgid, usage_pg_session)
		text = MSG_PDD_SUSB.format(first_name, 'SÍ' if is_sus else 'NO')
		keyboard = types.InlineKeyboardMarkup()
		keyboard.row(types.InlineKeyboardButton('Desuscribirme' if is_sus else '¡Suscribirme!', callback_data='__desubs' if is_sus else '__subs'))
		await	bot_send_message(message.chat.id, text, reply_markup=keyboard, parse_mode='HTML')

@bot.message_handler(commands=['users'])
async def check_users_handler(message):
	if message.from_user.id == admin_id:
		commands = message.text.split(' ') # /users command
		if len(commands) < 2:
			n = await get_users_count(usage_pg_session)
		elif commands[1] == 's':
			n = await get_users_count(usage_pg_session, subscribed=True)
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
		
		usage_list = await get_usage_last(ndays, usage_pg_session)

		text = '<pre>     ....:: Usage Stats ::....      \n\n   day   | users | messages | inline\n------------------------------------</pre>\n'
		
		
		for u in usage_list:
			users = str(u.users)
			messages = str(u.messages)
			queries = str(u.queries)
			users = (' ' * (len('users') - len(users))) + users
			messages = (' ' * (len('messages') - len(messages))) + messages
			queries = (' ' * (len('inline') - len(queries))) + queries

			text += f'<pre>{u.day.strftime("%d/%m/%y")} | {users} | {messages} | {queries}\n</pre>\n'

		text += f'<pre>Total users: {await get_users_count(usage_pg_session)}</pre>\n'
		text += f'<pre>Subscribed users: {await get_users_count(usage_pg_session, subscribed=True)}</pre>\n'

		await	bot_send_message(admin_id, text, parse_mode='HTML')

@bot.message_handler(commands=['broadcast_all', 'broadcast'])
async def broadcast_handler(message):
	if message.from_user.id == admin_id:
		lst = message.html_text.split(' ', 1)
		text = lst[1]
		usrs = await get_users_ids(usage_pg_session, subscribed=(True if lst[0] == '/broadcast' else None), in_bot=True, blocked=False)

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
		list = await get_users_ids(usage_pg_session, blocked=True)

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
			await set_blocked(id, True, usage_pg_session)
		except Exception as e:
			logger.error(f'Bad user id\n {e}')
			await bot.send_message(admin_id, '<pre>Bad user id</pre>', parse_mode='HTML')

@bot.message_handler(commands=['unblock'])
async def unblock_user_handler(message):
	if message.from_user.id == admin_id:
		try:
			id = int(message.text.split(' ', 1)[1])
			await set_blocked(id, False, usage_pg_session)
		except Exception as e:
			logger.error(f'Bad user id\n {e}')
			await bot.send_message(admin_id, '<pre>Bad user id</pre>', parse_mode='HTML')


@bot.callback_query_handler(lambda query: True)
async def handle_callback_query(query):
	if query.data in ['__desubs', '__subs']:
		tgid = query.from_user.id
		new_text = query.message.text
		query_answer= ''

		if query.data == '__subs':
			await set_subscription(tgid, True, usage_pg_session)
			new_text += '\n\n ¡Listo!, te has suscrito.'
			query_answer = '✅ ¡Te has suscrito!'
		if query.data == '__desubs':
			await set_subscription(tgid, False, usage_pg_session)
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
	if message.chat.type == 'private':
		if message.text in keyboard_command_function:
			await keyboard_command_function[message.text](message)
		elif not message.via_bot or message.via_bot.id != (await bot.get_me()).id:
			await add_message(message.from_user.id, usage_pg_session)
			word = message.text.split()[0].lower()

			definition, _ = await get_definition(word, dict_pg_session)
			if definition:
				await bot.send_chat_action(message.chat.id, 'typing')
				for definition_text in smart_split(definition):
					inline_kb = None
					if random() < VER_EN_DLE_RAE_ES_PROBABILITY:
						inline_kb = types.InlineKeyboardMarkup([[types.InlineKeyboardButton('Ver en dle.rae.es', url=f'https://dle.rae.es/{word}')]])
					await bot_send_message(message.chat.id, definition_text, parse_mode='HTML', reply_markup=inline_kb)
			else:
				inline_kb = types.InlineKeyboardMarkup([[types.InlineKeyboardButton('Probar inline', switch_inline_query_current_chat=f''),
				types.InlineKeyboardButton('Buscar en dle.rae.es', url=f'https://dle.rae.es/{word}') ]])
				await bot_send_message(message.chat.id, MSG_NO_RESULT_DIRECT_MESSAGE.format(word), parse_mode='HTML',reply_markup=inline_kb)
	elif message.chat.type in ['group', 'supergroup', 'channel']:
		await bot.leave_chat(message.chat.id)
		logger.lessinfo(f'Left chat {message.chat}')

@bot.chosen_inline_handler(lambda query: True)
async def handle_chosen_inline(result):
	await add_query(result.from_user.id, usage_pg_session)


async def broadcast_word_of_the_day(req = word_of_the_day):
	# logger.lessinfo('Broadcasting')
	await update_word_of_the_day()
	subs = await get_users_ids(usage_pg_session, subscribed=True)

	tasks = []
	for sub_id in subs:
		tasks.append(send_word_of_the_day(sub_id))

	await asyncio.gather(*tasks)

	log_text = f'Broadcasted Word Of The Day to {len(subs)} users.'
	logger.lessinfo(log_text)
	await bot.send_message(admin_id,'<pre>Log: </pre>' + log_text, parse_mode='HTML')

	return web.Response()

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
app.router.add_get(f'/{bot_token}/broadcastWOTD', broadcast_word_of_the_day)
app.router.add_get(f'/{bot_token}/setWebhook', handle_set_webhook)


if __name__ == '__main__':
	web.run_app(
		app
	)