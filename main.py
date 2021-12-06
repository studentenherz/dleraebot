import bs4
import requests
from bs4 import BeautifulSoup
import threading
import telebot
from telebot import types
from telebot.util import MAX_MESSAGE_LENGTH 
from credentials import bot_token
import ast

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

KEY_PDD = '📖 Palabra del día'
KEY_ALEATORIO = '🎲 Palabra aleatoria'
KEY_AYUDA = '❔ Ayuda'

REPLY_KEYBOARD = types.ReplyKeyboardMarkup(resize_keyboard=True)
REPLY_KEYBOARD.row(types.KeyboardButton(KEY_ALEATORIO), types.KeyboardButton(KEY_PDD))
REPLY_KEYBOARD.row(types.KeyboardButton(KEY_AYUDA))

INLINE_KEYBOARD_BUSCAR_DEFINICION = types.InlineKeyboardMarkup()
INLINE_KEYBOARD_BUSCAR_DEFINICION.row(types.InlineKeyboardButton('Buscar definición', switch_inline_query=f''))

INLINE_KEYBOARD_BUSCAR_DEFINICION_CURRENT_CHAT = types.InlineKeyboardMarkup()
INLINE_KEYBOARD_BUSCAR_DEFINICION_CURRENT_CHAT.row(types.InlineKeyboardButton('Buscar definición', switch_inline_query_current_chat=f''))

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
	if message.chat.type != 'private':
		return
	if 'no_result' in message.text:
		bot.send_message(message.chat.id, MSG_NO_RESULT_LONG, parse_mode='markdown', disable_web_page_preview=True, reply_markup=INLINE_KEYBOARD_BUSCAR_DEFINICION)
	else:
		bot.send_message(message.chat.id, MSG_START, parse_mode='markdown', disable_web_page_preview=True, reply_markup=REPLY_KEYBOARD)

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

@bot.message_handler(commands=['pdd'])
def pdd_handler(message):
	bot.send_chat_action(message.chat.id, 'typing')
	wotd = get_word_of_the_day()
	new_message = bot.send_message(message.chat.id, MSG_PDD.format(wotd), parse_mode='HTML')
	
	definitions = get_definitions(wotd.split(',')[0]) # ex.: cabalístico, ca

	bot.edit_message_text(chat_id=message.chat.id, message_id=new_message.message_id, text=MSG_PDD.format(definitions[0].lstrip()), parse_mode='HTML')	
	for page in definitions[1:]:
		bot.send_message(message.chat.id, page, parse_mode='HTML')

keyoard_command_function = {
	KEY_PDD : pdd_handler,
	KEY_ALEATORIO: aleatorio_handler,
	KEY_AYUDA: help_handler,
}

@bot.message_handler(content_types=['text'])
def text_messages_handler(message):
	if message.chat.type == 'private':
		if message.text in keyoard_command_function:
			keyoard_command_function[message.text](message)
		elif not message.via_bot or message.via_bot.id != bot.get_me().id:
			word = message.text.split()[0].lower()
			list = get_list(word)
			if word in list:
				bot.send_chat_action(message.chat.id, 'typing')
				definitions_list = get_definitions(word)
				for definition_text in definitions_list:
					bot.send_message(message.chat.id, definition_text, parse_mode='HTML')
			else:
				bot.send_message(message.chat.id, MSG_NO_RESULT_DIRECT_MESSAGE.format(word), parse_mode='HTML',reply_markup=INLINE_KEYBOARD_BUSCAR_DEFINICION_CURRENT_CHAT)


if __name__ == '__main__':
	bot.infinity_polling()