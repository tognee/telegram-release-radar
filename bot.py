import os
from sys import exit as sysexit
import logging
from telegram.ext import Updater

from dbhelper import DBHelper

from plugins.release_radar import Plugin as ReleaseRadar

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

TOKEN = os.environ.get('BOT_TOKEN')
if not TOKEN:
    print("Cannot find BOT_TOKEN")
    sysexit()

db = DBHelper()
db.setup()

plugins = [
    ReleaseRadar(db)
]
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

updater = Updater(token=TOKEN)
dispatcher = updater.dispatcher
for plugin in plugins:
    if not plugin: continue
    for handler in plugin.handlers:
        if not handler: continue
        dispatcher.add_handler(handler, plugin.group)

updater.start_polling()
updater.idle()
