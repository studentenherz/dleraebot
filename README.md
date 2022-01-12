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

```bash
$ python main.py
```

in order to save the logs and keep seing them on screen run 

```bash
$ python main.py 2>&1 | tee -a bot.log
```