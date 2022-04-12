#!/usr/bin/env python3
import os
from sys import exit as sysexit
from telegram import Bot

from dbhelper import DBHelper

from plugins.release_radar import Plugin as ReleaseRadar

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

def main():
    TOKEN = os.environ.get('BOT_TOKEN')
    if not TOKEN:
        print("Cannot find BOT_TOKEN")
        sysexit()
    bot = Bot(token=TOKEN)

    db = DBHelper()
    db.setup()
    rr = ReleaseRadar(db)
    all_artists = rr.get_all_artists()
    for artist in all_artists:
        artist_id = artist[0]
        print(f"Now checking artist {artist_id}")
        new_releases = rr.update_new_releases(artist_id)
        if new_releases['single']:
            rr.send_release_to_chats(bot, artist_id, new_releases['single'])
        if new_releases['album']:
            rr.send_release_to_chats(bot, artist_id, new_releases['album'])

if __name__ == "__main__": main()
