from bs4 import BeautifulSoup
import bs4
import aiohttp
import ast
from telebot.util import MAX_MESSAGE_LENGTH 



MOZILLA_HEADERS = {'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:91.0) Gecko/20100101 Firefox/91.0'}

# Messages parsing

def recursive_unwrap(tag, v,  fullcontent = False):
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
		# electroencefalografista is the longgest word in Spanish as for now, that's why it is here
		if (len(v[-1]) + len(msg_continua_end) + len(tag_text) + 21 + len('electroencefalografista') > (MAX_MESSAGE_LENGTH if not fullcontent else  float('inf'))):
			v[-1] += msg_continua_end
			v.append(msg_continua_start)
		v[-1] += tag_text
	
def parse_response(r):
	sp = BeautifulSoup(r, features='html.parser')
	definitions = ['']
	for article in sp.find('div', {'id': 'resultados'}).find_all('article', recursive=False):
		recursive_unwrap(article, definitions)
	return definitions



# RAE queries

async def get_definitions(entry, session):
	async with session.get(f'https://dle.rae.es/?w={entry}', headers=MOZILLA_HEADERS) as r:
		return parse_response(await r.text())

async def get_list(entry, session):
	async with await session.get(f'https://dle.rae.es/srv/keys?q={entry}', headers=MOZILLA_HEADERS) as r:
		return ast.literal_eval(await r.text())

async def get_random():
	async with aiohttp.ClientSession() as session:
		async with session.get('https://dle.rae.es/?m=random', headers=MOZILLA_HEADERS) as r:
			return parse_response(await r.text())

async def get_word_of_the_day(session):
	async with aiohttp.ClientSession() as session:
		async with session.get('https://dle.rae.es/', headers=MOZILLA_HEADERS) as r:
			sp = BeautifulSoup(await r.text(), features='html.parser')
			return sp.find(id='wotd').text

