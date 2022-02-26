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
	
def parse_response(r, fullcontent = False):
	sp = BeautifulSoup(r, features='html.parser')
	definitions = ['']
	for article in sp.find('div', {'id': 'resultados'}).find_all('article', recursive=False):
		recursive_unwrap(article, definitions, fullcontent)
	return definitions

def conjugations(r):
	sp = BeautifulSoup(r, features='html.parser')
	conj_section = sp.find(id='conjugacion')
	if not conj_section: return
	rows = conj_section.find('table').find_all('tr')

	modes = {
		'Formas no personales' : {'Infinitivo', 'Gerundio', 'Participio'}, 
		'Indicativo' : {'Presente', 'Pretérito imperfecto / Copretérito', 'Pretérito perfecto simple / Pretérito', 'Futuro simple / Futuro', 'Condicional simple / Pospretérito'}, 'Subjuntivo' : {'Presente', 'Futuro simple / Futuro', 'Pretérito imperfecto / Pretérito'}, 
		'Imperativo' : {}
		}


	pronombres = {
		'Primera persona de singular',
		'Segunda persona de singular',
		'Tercera persona de singular',
		'Primera persona de plural',
		'Segunda persona de plural',
		'Tercera persona de plural',
		'Singular de cortesía',
		'Plural de cortesía',
		'Forma singular de cortesía',
		'Forma plural de cortesía'
	}

	persona = {
		'Primera' : 1,
		'Segunda' : 2,
		'Tercera' : 3,
	}

	numero = { 
		 'Singular': 's',
		 'Plural': 'p'
	}


	conjugation = {
		'Formas no personales': {},
		'Indicativo' : {},
		'Subjuntivo' : {},
		'Imperativo' : {}
	}

	conj = {'numero': None, 'persona': None, 'pronombre': None}
	conjugation['Formas no personales']['Infinitivo'] = [{'palabra' : rows[2].find_all('td')[3].text} | conj]
	conjugation['Formas no personales']['Gerundio'] = [{'palabra' :rows[2].find_all('td')[4].text} | conj]
	conjugation['Formas no personales']['Participio'] = [{'palabra' :rows[4].find_all('td')[3].text} | conj]

	# Check if row corresponds to mode row
	def h1(row):
		for t in row:
			if t.text in modes.keys():
				return t.text
		return ''

	# Check if row corresponds to tense row
	def h2(row):
		ths = row.find_all('th')
		if not ths:
			return False
		for t in ths:
			if t.text in modes:
				return False
		
		return True

	# Get person, mumber and pronoun from data row
	def classify_row(row):
		conj = {'numero' : None, 'persona': None, 'pronombre' : None}
		for t in row:
			if t.get('data-g') in numero:
				conj['numero'] = numero[t.get('data-g')]
			if t.get('data-g') in persona:
				conj['persona'] = persona[t.get('data-g')]
			if t.get('title') in pronombres:
				conj['pronombre'] = t.text

		return conj


	index = 5
	last_numero = None
	last_persona = None
	while index < len(rows):
		h = h1(rows[index])
		if h != '': # if mode row
			index += 1

			while index < len(rows) and h1(rows[index]) == '': # step inside
				if h2(rows[index]):
					tiempos = {}

					if h == 'Imperativo':
						tiempos = {3: ''}
						conjugation[h][''] = []
					else:
						for i, t in enumerate(rows[index]):
							if t.text in modes[h]:
								tiempos[i] = t.text
								conjugation[h][t.text] = []
							
					
					index += 1
					while index < len(rows) and h1(rows[index]) == '' and not h2(rows[index]):
						conj = classify_row(rows[index])
						if conj['numero'] == None:
							conj['numero'] = last_numero
						else:
							last_numero = conj['numero']

						if conj['persona'] == None:
							conj['persona'] = last_persona
						else:
							last_persona = conj['persona']
						
						for i, t in enumerate(rows[index]):
							if i in tiempos:
								conjugation[h][tiempos[i]].append({'palabra': t.text} | conj)

						index+=1
				else:
					index += 1
	
	return conjugation

# RAE queries

async def get_definitions(entry, session, fullcontent = False):
	async with session.get(f'https://dle.rae.es/?w={entry}', headers=MOZILLA_HEADERS) as r:
		res = await r.text()
		return parse_response(res, fullcontent), conjugations(res)

async def get_list(entry, session):
	async with await session.get(f'https://dle.rae.es/srv/keys?q={entry}', headers=MOZILLA_HEADERS) as r:
		return ast.literal_eval(await r.text())

async def get_random():
	async with aiohttp.ClientSession() as session:
		async with session.get('https://dle.rae.es/?m=random', headers=MOZILLA_HEADERS) as r:
			res = await r.text()
			return parse_response(res), conjugations(res)

async def get_word_of_the_day(session):
	async with aiohttp.ClientSession() as session:
		async with session.get('https://dle.rae.es/', headers=MOZILLA_HEADERS) as r:
			sp = BeautifulSoup(await r.text(), features='html.parser')
			return sp.find(id='wotd').text

