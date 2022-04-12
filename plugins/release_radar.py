import os
from datetime import datetime
from time import sleep
from telegram.ext import PrefixHandler, MessageHandler, Filters
from telegram.utils.helpers import escape_markdown
from telegram.error import RetryAfter

from spotipy import Spotify
from spotipy.oauth2 import SpotifyClientCredentials
from spotipy.exceptions import SpotifyException

def chunks(l, n):
    for i in range(0, len(l), n):
        yield l[i:i+n]

def get_effective_chat_title(chat):
    if chat.type == 'private':
        return chat.first_name
    return chat.title

class Plugin:
    def __init__(self, db):
        self.name = "Release Radar"

        client_id = os.environ.get('SPOTIFY_CLIENT_ID')
        client_secret = os.environ.get('SPOTIFY_CLIENT_SECRET')
        can_spotify_setup = client_id and client_secret

        self.handlers = [
            PrefixHandler(['/', '.', '!'], ["subs", "subscriptions", "iscrizioni"], self.show_subscriptions),
            PrefixHandler(['/', '.', '!'], ["latest"], self.show_latest),
            MessageHandler(Filters.text & Filters.regex(r'^https?:\/\/open.spotify.com/artist/'), self.handle_spotify_link),
            MessageHandler(Filters.text & Filters.regex(r'^spotify:artist:'), self.handle_spotify_link),
        ] if db.is_enabled and can_spotify_setup else []

        self.group = 0
        self.db = db
        if db.is_enabled: self.setup()

        self.sp = None
        if can_spotify_setup:
            client_credentials_manager = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
            self.sp = Spotify(
                client_credentials_manager=client_credentials_manager,
                status_retries=5,
                retries=5
            )

        self.enabled = can_spotify_setup and db.is_enabled
        self.hidden = False

    def setup(self):
        self.db.cur.execute("CREATE TABLE IF NOT EXISTS ReleaseRadar_Chats (chatID integer, artistID text)")
        self.db.cur.execute("CREATE TABLE IF NOT EXISTS ReleaseRadar_Artists (artistID text PRIMARY KEY, lastSingleID text, lastSingleDate text, lastSingleName text, lastAlbumID text, lastAlbumDate text, lastAlbumName text)")
        self.db.conn.commit()

    def add_artist_to_chat(self, chatID, artistID):
        self.db.execute("INSERT INTO ReleaseRadar_Chats (chatID, artistID) VALUES (%s, %s)", (chatID, artistID))
        self.db.conn.commit()

    def remove_artist_from_chat(self, chatID, artistID):
        self.db.execute("DELETE FROM ReleaseRadar_Chats WHERE chatID = (%s) AND artistID = (%s);", (chatID, artistID))
        self.db.conn.commit()

    def get_artists_for_chat(self, chatID):
        self.db.execute("SELECT artistID FROM ReleaseRadar_Chats WHERE chatID = (%s)", (chatID, ))
        rows = self.db.cur.fetchall()
        if not rows: return []
        return rows

    def get_chats_for_artist(self, artistID):
        self.db.execute("SELECT chatID FROM ReleaseRadar_Chats WHERE artistID = (%s)", (artistID, ))
        rows = self.db.cur.fetchall()
        if not rows: return []
        return rows

    def update_last_artist_single(self, artistID, lastID, lastDate, lastName):
        self.db.execute("UPDATE ReleaseRadar_Artists SET lastSingleID = (%s), lastSingleDate = (%s), lastSingleName = (%s) WHERE artistID = (%s);", (lastID, lastDate, lastName, artistID))
        self.db.conn.commit()

    def update_last_artist_album(self, artistID, lastID, lastDate, lastName):
        self.db.execute("UPDATE ReleaseRadar_Artists SET lastAlbumID = (%s), lastAlbumDate = (%s), lastAlbumName = (%s) WHERE artistID = (%s);", (lastID, lastDate, lastName, artistID))
        self.db.conn.commit()

    def add_artist(self, artistID, lastSingleID, lastSingleDate, lastSingleName, lastAlbumID, lastAlbumDate, lastAlbumName):
        self.db.execute("INSERT INTO ReleaseRadar_Artists (artistID, lastSingleID, lastSingleDate, lastSingleName, lastAlbumID, lastAlbumDate, lastAlbumName) VALUES (%s, %s, %s, %s, %s, %s, %s)", (artistID, lastSingleID, lastSingleDate, lastSingleName, lastAlbumID, lastAlbumDate, lastAlbumName))
        self.db.conn.commit()

    def get_artist(self, artistID):
        self.db.execute("SELECT * FROM ReleaseRadar_Artists WHERE artistID = (%s)", (artistID, ))
        rows = self.db.cur.fetchone()
        if not rows: return []
        return rows

    def get_all_artists(self):
        self.db.cur.execute("SELECT artistID FROM ReleaseRadar_Artists")
        rows = self.db.cur.fetchall()
        if not rows: return []
        return rows

    def remove_artist(self, artistID):
        self.db.execute("DELETE FROM ReleaseRadar_Artists WHERE artistID = (%s)", (artistID, ))
        self.db.conn.commit()

    def get_newest_release(self, artist_id, album_type, local = False):
        latest_release = None
        while latest_release is None:
            try:
                if local: latest_release = self.sp.artist_albums(artist_id, album_type=album_type, country='IT', limit=1)['items']
                else: latest_release = self.sp.artist_albums(artist_id, album_type=album_type, limit=1)['items']
            except SpotifyException:
                sleep(1)
        if len(latest_release)>0:
            latest_release = latest_release[0]
        else:
            latest_release = {'release_date': '1910-01-01', 'id': '', 'name': ''}
        if 'release_date_precision' in latest_release:
            if latest_release['release_date_precision'] == "year":
                latest_release['release_date'] = latest_release['release_date']+"-01-01"
            if latest_release['release_date_precision'] == "month":
                latest_release['release_date'] = latest_release['release_date']+"-01"
        latest_release['release_date'] = latest_release['release_date'][:10]
        return latest_release

    def update_new_releases(self, artist_id):
        latest_album = self.get_newest_release(artist_id, 'album')
        latest_album['name'] = latest_album['name'].replace('“', '"').replace('”', '"').strip()
        latest_single = self.get_newest_release(artist_id, 'single')
        latest_single['name'] = latest_single['name'].replace('“', '"').replace('”', '"').strip()
        current_artist = self.get_artist(artist_id)
        result = { 'single': None, 'album': None }
        if not current_artist:
            self.add_artist(artist_id, latest_single['id'], latest_single['release_date'], latest_single['name'], latest_album['id'], latest_album['release_date'], latest_album['name'])
            result['single'] = latest_single
            result['album'] = latest_album
            return result
        if latest_single['id'] != current_artist[1] and latest_single['name'] != current_artist[3]:
            db_date = datetime.strptime(current_artist[2] or "1910-01-01", '%Y-%m-%d')
            new_date = datetime.strptime(latest_single['release_date'], '%Y-%m-%d')
            if db_date < new_date:
                self.update_last_artist_single(artist_id, latest_single['id'], latest_single['release_date'], latest_single['name'])
                print(f"New single found for {artist_id}: {latest_single['artists'][0]['name']} - {latest_single['name']}")
                result['single'] = latest_single
        if latest_album['id'] != current_artist[4] and latest_album['name'] != current_artist[6]:
            db_date = datetime.strptime(current_artist[5] or "1910-01-01", '%Y-%m-%d')
            new_date = datetime.strptime(latest_album['release_date'], '%Y-%m-%d')
            if db_date < new_date:
                self.update_last_artist_album(artist_id, latest_album['id'], latest_album['release_date'], latest_album['name'])
                print(f"New album found for {artist_id}: {latest_album['artists'][0]['name']} - {latest_album['name']}")
                result['album'] = latest_album
        return result

    def send_release(self, bot, chat, response):
        image_id = response['cover']
        try:
            image_id = bot.send_photo(chat, response['cover'], response['text'], parse_mode="MarkdownV2", reply_markup=response['keyboard'])
            image_id = image_id.photo[0].file_id
        except RetryAfter as e:
            timer = int(str(e)[33:-8])
            sleep(timer)
            return self.send_release(bot, chat, response)
        sleep(1)
        return image_id

    def send_release_to_chats(self, bot, artist_id, release):
        chats = self.get_chats_for_artist(artist_id)
        response = self.generate_response(release)
        for chat in chats:
            response['cover'] = self.send_release(bot, chat[0], response)

    @staticmethod
    def get_artist_id(link):
        if link.lower().startswith("https://open.spotify.com/artist/"):
            link = link[32:]
            if '?' in link: link = link[:link.find('?')]
            if '&' in link: link = link[:link.find('&')]
            if link.endswith('/'): link = link[:-1] #  Remove last slash if present
        elif link.lower().startswith("spotify:artist:"):
            link = link[15:]
        return link.strip()

    @staticmethod
    def generate_response(release):
        message = fr"[‍](https://open.spotify.com/album/{release['id']})*{escape_markdown(release['name'], version=2)}*"+"\n"
        for artist in release['artists']:
            message += fr"_{escape_markdown(artist['name'], version=2)}_"+"\n"
        message += "\n"
        message += fr"🗓 {escape_markdown(release['release_date'], version=2)}"+"\n"
        message += fr"💽 \#{escape_markdown(release['album_type'][:1].upper()+release['album_type'][1:], version=2)}"
        return {
            'text': message,
            'keyboard': {'inline_keyboard': [[{'text':"Spotify Link", 'url': "https://open.spotify.com/album/"+release['id']}]]},
            'cover': release['images'][0]['url']
        }

    def show_subscriptions(self, update, context):
        followed_artists = self.get_artists_for_chat(update.effective_chat.id)
        artists_list = list(map(lambda row: row[0], followed_artists))
        result = ""
        chunked_artists_list = list(chunks(artists_list, 20))
        for chunk_artists_list in chunked_artists_list:
            if len(chunk_artists_list) == 0: continue
            spotify_artists = self.sp.artists(chunk_artists_list)
            for artist in spotify_artists['artists']:
                result += r"\-"+f" [{escape_markdown(artist['name'], version=2)}](https://open.spotify.com/artist/{artist['id']})\n"
        if result == "":
            result = "_No One_"
        context.bot.send_message(update.effective_chat.id, f"*Currently subscribed to:*\n{result}", parse_mode="MarkdownV2", disable_web_page_preview=True)


    def show_latest(self, update, context):
        link = context.args[0]
        artist_id = self.get_artist_id(link)
        current_artist = self.get_artist(artist_id)
        if not current_artist:
            context.bot.send_message(update.effective_chat.id, f"{artist_id} is not tracked, you should add it before checking the latest releases!")
            return
        if current_artist[1] != "":
            last_single = self.sp.album(current_artist[1])
            response = self.generate_response(last_single)
            context.bot.send_photo(update.effective_chat.id, response['cover'], response['text'], parse_mode="MarkdownV2", reply_markup=response['keyboard'])
        else:
            context.box.send_message(update.effective_chat.id, "No last single recorded")
        sleep(3)
        if current_artist[4] != "":
            last_album = self.sp.album(current_artist[4])
            response = self.generate_response(last_album)
            context.bot.send_photo(update.effective_chat.id, response['cover'], response['text'], parse_mode="MarkdownV2", reply_markup=response['keyboard'])
        else:
            context.bot.send_message(update.effective_chat.id, "No last album recorded")

    def handle_spotify_link(self, update, context):
        link = update.message.text.split(" ")[0]
        artist_id = self.get_artist_id(link)
        chat_id = update.effective_chat.id
        chat_name = get_effective_chat_title(update.effective_chat)
        spotify_artist = self.sp.artist(artist_id)
        followed_artists = self.get_artists_for_chat(chat_id)
        if (artist_id, ) in followed_artists:
            self.remove_artist_from_chat(chat_id, artist_id)
            print(f"Removed artist {spotify_artist['name']} ({artist_id}) for {chat_name} ({chat_id})")
            context.bot.send_message(chat_id, f"You've unsubscribed to {spotify_artist['name']}")
            chats = self.get_chats_for_artist(artist_id)
            if len(chats) == 0:
                self.remove_artist(artist_id)
                print(f"Now artist {spotify_artist['name']} ({artist_id}) is no longer tracked")
        else:
            self.add_artist_to_chat(chat_id, artist_id)
            print(f"Added artist {spotify_artist['name']} ({artist_id}) for {chat_name} ({chat_id})")
            context.bot.send_message(chat_id, f"You've subscribed to {spotify_artist['name']}")
            if not self.get_artist(artist_id):
                latest_album = self.get_newest_release(artist_id, 'album', True)
                latest_single = self.get_newest_release(artist_id, 'single', True)
                self.add_artist(artist_id, latest_single['id'], latest_single['release_date'], latest_single['name'], latest_album['id'], latest_album['release_date'], latest_album['name'])
                print(f"Now artist {spotify_artist['name']} ({artist_id}) is being tracked")
