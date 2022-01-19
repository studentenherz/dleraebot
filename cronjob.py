import requests
import click
from credentials import HOST_URL, bot_token
import logging

logging.basicConfig(format='%(asctime)s (%(filename)s:%(lineno)d %(threadName)s) %(levelname)s - %(name)s: "%(message)s"', filename='cron.log')

@click.command()
@click.option('--broadcast', help='Also broadcast WOTD', is_flag=True)
def cli(broadcast):
	if broadcast:
		response = requests.get(f'{HOST_URL}/{bot_token}/broadcastWOTD')
		if response.status_code != 200:
			logging.error(f'Broadcast responded with code {response.status_code}')
	else:
		response = requests.get(f'{HOST_URL}/{bot_token}/updateDB')
		if response.status_code != 200:
				logging.error(f'Update responded with code {response.status_code}')


if __name__ == '__main__':
	cli()
