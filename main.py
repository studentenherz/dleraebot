import types
import requests
from bs4 import BeautifulSoup
import threading
import telebot
from telebot import types 
from credentials import bot_token
import ast

bot = telebot.TeleBot(bot_token)

# Definition of constants

MOZILLA_HEADERS = {'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:91.0) Gecko/20100101 Firefox/91.0'}

MSG_START = 'No es necesario que inicies un chat con el bot para que funcione, tampoco es necesario que lo agregues a ningún grupo o canal (/ayuda para más información), pero ya que estás aquí te cuento algunas cosas:\n\n - los comandos están en español porque es un bot para obtener definiciones de palabras en español 😅,\n - la imagen del bot es la bandera de España y no el isotipo de la RAE porque esta última imagen está sujeta a derechos de autor, mientras que la bandera de España que usé no.\n\nHace un tiempo le escribí a la RAE (a través de un formulario en su página web, quizá nunca me leyeron) proponiéndoles la idea de que hicieran este bot, si quisieran problablemente Telegram les diese un @ más corto como @dle y la marca de bot oficial. Puedes ver el código del bot en [GitHub](https://github.com/studentenherz/dleraebot).'

MSG_AYUDA = 'Escribe @dleraebot y luego la palabra que deseas buscar, en unos segundos aparecerán las opciones compatibles. Si no te queda claro puedes ver un gif de ejemplo con /ejemplo.'

MSG_EJEMPLO = 'CgACAgEAAxkBAAMWYSSF83hFhvdaCGrKA8S7RIogjn8AAqcCAAI3gSBFIvdrsiI9VIwgBA'


# RAE queries

def get_definition(s, entry):
    r = s.get(f'https://dle.rae.es/{entry}', headers=MOZILLA_HEADERS)
    sp = BeautifulSoup(r.text, features='html.parser')
    definition = ''
    for article in sp.find('div', {'id': 'resultados'}).find_all('article'):
        definition += article.text
    return definition

def get_list(s, entry):
    r = s.get(f'https://dle.rae.es/srv/keys?q={entry}', headers=MOZILLA_HEADERS)
    return ast.literal_eval(r.text)

# Bot queries

@bot.inline_handler(lambda query: len(query.query) > 0)
def inline_query_handler(query):
    try:
        s = requests.Session()
        l = get_list(s, query.query)

        res = []
        def add_res(i, entry):
            deffinition_text = get_definition(s, entry)
            definition = types.InputTextMessageContent(deffinition_text)
            r = types.InlineQueryResultArticle(i, title=entry, input_message_content=definition, description=deffinition_text)
            res.append(r)

        threads = []

        for i in range(len(l)):
            threads.append(threading.Thread(target=add_res, args=(i, l[i])))

        for i in range(len(l)):
            threads[i].start()

        for i in range(len(l)):
            threads[i].join()
            
        if len(res) > 0:
            bot.answer_inline_query(query.id, res)
    except Exception as e:
        print(e)

@bot.message_handler(commands=['start'])
def start_handler(message):
    bot.send_message(message.chat.id, MSG_START, parse_mode='markdown', disable_web_page_preview=True)

@bot.message_handler(commands=['ayuda'])
def help_handler(message):
    m = types.InlineKeyboardMarkup()
    m.row(types.InlineKeyboardButton('Buscar definición', switch_inline_query=f''))
    bot.send_message(message.chat.id, MSG_AYUDA, reply_markup=m)

@bot.message_handler(commands=['ejemplo'])
def ejemplo_handelr(message):
    bot.send_animation(message.chat.id, MSG_EJEMPLO)


if __name__ == '__main__':
    bot.polling()
