import bs4
import requests
from bs4 import BeautifulSoup
import threading
import telebot
from telebot import types
from telebot.util import MAX_MESSAGE_LENGTH 
from credentials import bot_token, admin_id
import ast
from db.handler import subscribe_user, unsubscribe_user, add_user, is_subscribed, get_susbcribed_ids, get_users_count, update_usage, get_usage_last, get_usage
import time
import schedule
import datetime

bot = telebot.TeleBot(bot_token)

# Definition of constants


MOZILLA_HEADERS = {'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:91.0) Gecko/20100101 Firefox/91.0'}
MSG_START = 'No es necesario que inicies un chat con el bot para que funcione, tampoco es necesario que lo agregues a ningún grupo o canal (/ayuda para más información), pero ya que estás aquí te cuento algunas cosas:\n\n - los comandos están en español porque es un bot para obtener definiciones de palabras en español 😅.\n\n -Hace un tiempo le escribí a la RAE (a través de un formulario en su página web, quizá nunca me leyeron) proponiéndoles la idea de que hicieran este bot, si quisieran problablemente Telegram les diese un @ más corto como @dle y la marca de bot oficial.\n\nPuedes ver el código del bot en [GitHub](https://github.com/studentenherz/dleraebot), y puedes recibir noticias acerca del bot en @dleraebotchannel.'

MSG_AYUDA = 'Simplemente, envía un mensaje de texto donde solo esté la palabra que deseas buscar, respetando su correcta escritura incluyendo tildes.\n\n Si quieres acceder rápidamente a una definición desde cualquier otro chat, escribe @dleraebot y luego la palabra que deseas buscar, en unos segundos aparecerán las opciones compatibles. Si no te queda claro puedes ver un gif de ejemplo con /ejemplo.\n\nEn las definiciones se pueden encontrar algunas abreviaturas cuyo significado puedes ver <a href="https://t.me/dleraebotchannel/10">aquí</a>.'
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

# Messages parsing

def recursive_unwrap(tag, v):
	telegram_supported_tags = ['b', 'strong', 'i', 'em', 'u', 'ins', 's', 'strike', 'del', 'code', 'pre']

	def get_super(x):
		normal = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+-=()"
		super_s = "ᴬᴮᶜᴰᴱᶠᴳᴴᴵᴶᴷᴸᴹᴺᴼᴾQᴿˢᵀᵁⱽᵂˣʸᶻᵃᵇᶜᵈᵉᶠᵍʰᶦʲᵏˡᵐⁿᵒᵖ۹ʳˢᵗᵘᵛʷˣʸᶻ⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾"
		res = x.maketrans(''.join(normal), ''.join(super_s))
		return x.translate(res)

	def recursion(tag):
		if (type(tag) == bs4.element.Tag):
			fstr = ''
			for x in tag.contents:
				if x.name in telegram_supported_tags:
					fstr += f'<{x.name}>{recursion(x)}</{x.name}>'
				elif x.name == 'sup':
					fstr += get_super(x.string)
				else:
					fstr += recursion(x)
			return fstr
		else:
			return tag.string

	msg_continua_end = '\n\n <pre>ver continuación...</pre>'
	msg_continua_start = '<pre>... continuación</pre>\n\n'
	
	for x in tag.contents:
		tag_text = recursion(x)
		if (len(v[-1]) + len(msg_continua_end) + len(tag_text) + len(MSG_PDD) + len('electroencefalografista') > MAX_MESSAGE_LENGTH):
			v[-1] += msg_continua_end
			v.append(msg_continua_start)
		v[-1] += tag_text
	
def parse_response(r):
	sp = BeautifulSoup(r.text, features='html.parser')
	definitions = ['']
	for article in sp.find('div', {'id': 'resultados'}).find_all('article', recursive=False):
		recursive_unwrap(article, definitions)
	return definitions



# RAE queries

def get_definitions(entry):
	r = requests.get(f'https://dle.rae.es/?w={entry}', headers=MOZILLA_HEADERS)
	return parse_response(r)

def get_list(entry):
	r = requests.get(f'https://dle.rae.es/srv/keys?q={entry}', headers=MOZILLA_HEADERS)
	return ast.literal_eval(r.text)

def get_random():
	r = requests.get('https://dle.rae.es/?m=random', headers=MOZILLA_HEADERS)
	return parse_response(r)

def get_word_of_the_day():
	r = requests.get('https://dle.rae.es/', headers=MOZILLA_HEADERS)
	sp = BeautifulSoup(r.text, features='html.parser')
	return sp.find(id='wotd').text


# Bot queries

@bot.inline_handler(lambda query: len(query.query) > 0)
def inline_query_handler(query):
	try:
		l = get_list(query.query)

		res = []
		def add_res(i, entry):
			definitions_list = get_definitions(entry)
			for idx, definition_text in enumerate(definitions_list):
				definition = types.InputTextMessageContent(definition_text, parse_mode='HTML')
				r = types.InlineQueryResultArticle(f'{i}_{idx}', title=entry, input_message_content=definition, description=definition_text)
				res.append((f'{i}_{idx}',r))

		threads = []

		for i in range(len(l)):
			threads.append(threading.Thread(target=add_res, args=(i, l[i])))

		for i in range(len(l)):
			threads[i].start()

		for i in range(len(l)):
			threads[i].join()
			
		res.sort()
		res = [x[1] for x in res]

		if len(res) == 0:
			bot.answer_inline_query(query.id, res, switch_pm_text=MSG_NO_RESULT, switch_pm_parameter='no_result')
		else:
			bot.answer_inline_query(query.id, res)
		
	except Exception as e:
		print(e)

@bot.message_handler(commands=['start'])
def start_handler(message):
	if message.chat.type == 'private':
		if 'no_result' in message.text:
			bot.send_message(message.chat.id, MSG_NO_RESULT_LONG, parse_mode='markdown', disable_web_page_preview=True, reply_markup=INLINE_KEYBOARD_BUSCAR_DEFINICION)
		else:
			bot.send_message(message.chat.id, MSG_START, parse_mode='markdown', disable_web_page_preview=True, reply_markup=REPLY_KEYBOARD)
			add_user(message.from_user.id)

@bot.message_handler(commands=['ayuda', 'help'])
def help_handler(message):
	bot.send_message(message.chat.id, MSG_AYUDA, reply_markup=INLINE_KEYBOARD_BUSCAR_DEFINICION, parse_mode='HTML', disable_web_page_preview=True)

@bot.message_handler(commands=['ejemplo'])
def ejemplo_handler(message):
	bot.send_animation(message.chat.id, MSG_EJEMPLO)

@bot.message_handler(commands=['aleatorio'])
def aleatorio_handler(message):
	bot.send_chat_action(message.chat.id, 'typing')
	definitions = get_random()
	for page in definitions:
		bot.send_message(message.chat.id, page, parse_mode='HTML')

def update_word_of_the_day():
	global word_of_the_day, wotd_definitions

	word_of_the_day = get_word_of_the_day()
	wotd_definitions = get_definitions(word_of_the_day.split(',')[0]) # ex.: cabalístico, ca

def send_word_of_the_day(chat_id):
	if word_of_the_day == '':
		bot.send_chat_action(chat_id, 'typing')
		update_word_of_the_day()
	bot.send_message(chat_id, MSG_PDD.format(wotd_definitions[0].lstrip()), parse_mode='HTML')	
	for page in wotd_definitions[1:]:
		bot.send_message(chat_id, page, parse_mode='HTML')


@bot.message_handler(commands=['pdd'])
def pdd_handler(message):
	send_word_of_the_day(message.chat.id)

@bot.message_handler(commands=['suscripcion'])
def suscripcion_handler(message):
	if message.chat.type == 'private':
		tgid = message.from_user.id
		first_name = message.from_user.first_name
		is_sus = is_subscribed(tgid)
		text = MSG_PDD_SUSB.format(first_name, 'SÍ' if is_sus else 'NO')
		keyboard = types.InlineKeyboardMarkup()
		keyboard.row(types.InlineKeyboardButton('Desuscribirme' if is_sus else '¡Suscribirme!', callback_data='desubs' if is_sus else 'subs'))
		bot.send_message(message.chat.id, text, reply_markup=keyboard, parse_mode='HTML')

@bot.message_handler(commands=['users'])
def check_users_handler(message):
	if message.from_user.id == admin_id:
		commands = message.text.split(' ') # /users command
		if len(commands) < 2:
			n = get_users_count()
		elif commands[1] == 's':
			n = get_users_count(subscribed=True)
		bot.send_message(admin_id, f'{n} users')

@bot.message_handler(commands=['usage'])
def check_usage_handler(message):
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
		text += f'<pre>Total users: {get_users_count(subscribed=True)}</pre>\n'

		bot.send_message(admin_id, text, parse_mode='HTML')


@bot.callback_query_handler(lambda query: True)
def handle_callback_query(query):
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

		bot.answer_callback_query(query.id, query_answer)
		bot.edit_message_text(new_text, query.message.chat.id, query.message.id)

keyboard_command_function = {
	KEY_PDD : pdd_handler,
	KEY_ALEATORIO: aleatorio_handler,
	KEY_AYUDA: help_handler,
	KEY_SUSCRIPCION: suscripcion_handler
}

@bot.message_handler(content_types=['text'])
def text_messages_handler(message):
	global new_searches, new_users

	if message.chat.type == 'private':
		new_users.add(message.from_user.id) # add user
		if message.text in keyboard_command_function:
			keyboard_command_function[message.text](message)
		elif not message.via_bot or message.via_bot.id != bot.get_me().id:
			new_searches += 1 # incdrement searches
			word = message.text.split()[0].lower()
			list = get_list(word)
			if word in list:
				bot.send_chat_action(message.chat.id, 'typing')
				definitions_list = get_definitions(word)
				for definition_text in definitions_list:
					bot.send_message(message.chat.id, definition_text, parse_mode='HTML', reply_markup=REPLY_KEYBOARD)
			else:
				bot.send_message(message.chat.id, MSG_NO_RESULT_DIRECT_MESSAGE.format(word), parse_mode='HTML',reply_markup=INLINE_KEYBOARD_BUSCAR_DEFINICION_CURRENT_CHAT)

@bot.chosen_inline_handler(lambda query: True)
def handle_chosen_inline(result):
	global new_users, new_inline_searches
	new_users.add(result.from_user.id) # add user
	new_inline_searches += 1 # increment inline searches

# Scheduling

def run_continuously(interval=60):
    """Continuously run, while executing pending jobs at each
    elapsed time interval.
    @return cease_continuous_run: threading. Event which can
    be set to cease continuous run. Please note that it is
    *intended behavior that run_continuously() does not run
    missed jobs*. For example, if you've registered a job that
    should run every minute and you set a continuous run
    interval of one hour then your job won't be run 60 times
    at each interval but only once.
    """
    cease_continuous_run = threading.Event()

    class ScheduleThread(threading.Thread):
        @classmethod
        def run(cls):
            while not cease_continuous_run.is_set():
                schedule.run_pending()
                time.sleep(interval)

    continuous_thread = ScheduleThread()
    continuous_thread.start()
    return cease_continuous_run


def broadcast_word_of_the_day():
	update_word_of_the_day()
	subs = get_susbcribed_ids()

	for sub_id in subs:
		send_word_of_the_day(sub_id)

def update_database():
	global actually_new_count, new_searches, new_inline_searches

	# update users
	for utgid in new_users:
		actually_new_count += add_user(utgid)
	new_users.clear()

	#update usage
	is_new_day = update_usage(new_searches, new_inline_searches, actually_new_count)

	if is_new_day == 1:
		print('New day data')
		new_searches = 0
		new_inline_searches = 0
		actually_new_count = 0

	print('Database updated')

def init():
	global actually_new_count, new_searches, new_inline_searches
	today_usage = get_usage(datetime.date.today())
	if today_usage:
		actually_new_count = today_usage.users
		new_inline_searches = today_usage.queries
		new_searches = today_usage.messages

if __name__ == '__main__':
	init()

	# schedule
	schedule.every().day.at('12:00').do(broadcast_word_of_the_day)
	schedule.every().minute.do(update_database)

	stop_run_continuously = run_continuously()
	bot.infinity_polling()
	stop_run_continuously.set()