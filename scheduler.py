import datetime, asyncio

MINUTE = 60
HOUR = 60 * MINUTE
DAY = 24 * HOUR

async def run_every(dt: float, func, start = None) -> None:
	"""
		Couroutine that runs periodically
	param: dt: time in seconds
	param: func: async function you want to run, you wont get any returned value
	param: start: None: waits for first sleep, "now" starts from the begining 
							"hh:mm:ss" starts at next time it is the given time
	"""
	async def coro():
		if start:
			if start == 'now':
				await func()
			else:
				try:
					time = datetime.datetime.strptime(start, '%H:%M:%S')
					now = datetime.datetime.now()
					until = datetime.datetime(now.year, now.month, now.day, time.hour, time.minute, time.second)
					if until <  now:
						until += datetime.timedelta(1)
					await asyncio.sleep((until - now).total_seconds())
					await func()
				except Exception:
					await func()
		while True:
			await asyncio.sleep(dt)
			await func()
	
	return await coro()