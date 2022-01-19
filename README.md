# Bot to query spanish definitions using RAE

## Using the bot as a client

You can inspect a live version of the code in the telegram bot @dleraebot.

## Setting up a local instance

### Clone the repository

```bash
$ git clone https://github.com/studentenherz/dleraebot.git
```

### Install required dependencies

```bash
$ pip install -r requirements.txt
```

### Create your configuration file

Make a copy of the file:

```bash
credentials.py.sample
```

And name it:

```bash
credentials.py
```

Edit your bot token in the file. If you don't have one, you can get it using @BotFather in Telegram.


### Running the bot

Here the bot is set to use webhooks, with an `aiohttp` server through `gunicorn` 

```bash
$ gunicorn app:app -k aiohttp.worker.GunicornWebWorker -b <host>:<port>
```

See [this](https://www.digitalocean.com/community/tutorials/how-to-serve-flask-applications-with-gunicorn-and-nginx-on-ubuntu-20-04) to learn how to set up the webserver with `nginx` + `gunicorn`. 
