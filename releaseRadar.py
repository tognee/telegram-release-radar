#!/usr/bin/env python3
import telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import datetime
import sqlite3
import time
import os
import json

with open(os.path.join(os.path.dirname(os.path.realpath(__file__)),'config.json'), 'r') as f:
    config = json.load(f)

client_credentials_manager = SpotifyClientCredentials(client_id=config['spotifyClientID'],client_secret=config['spotifyClientSecret'])
sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)

TOKEN = config['botToken']
bot = telegram.Bot(token=TOKEN)

def escapeMarkdown(string):
    string = str(string).replace("*","\*").replace("_","\_").replace("*","\*").replace("`","\`")
    return string

def chunks(l, n):
    for i in range(0, len(l), n):
        yield l[i:i+n]

def dbSetup(conn, cur):
    stmt1 = "CREATE TABLE IF NOT EXISTS user (userID integer, artistID text)"
    stmt2 = "CREATE TABLE IF NOT EXISTS artist (artistID text PRIMARY KEY, lastSingleID text, lastSingleDate text, lastSingleName text, lastAlbumID text, lastAlbumDate text, lastAlbumName text)"
    cur.execute(stmt1)
    cur.execute(stmt2)
    conn.commit()

def addArtistToUser(conn, cur, userID, artistID):
    cur.execute("INSERT INTO user (userID, artistID) VALUES (?, ?)", (userID, artistID))
    conn.commit()

def removeArtistFromUser(conn, cur, userID, artistID):
    cur.execute("DELETE FROM user WHERE userID = (?) AND artistID = (?);", (userID, artistID))
    conn.commit()

def getArtistsForUser(conn, cur, userID):
    cur.execute("SELECT artistID FROM user WHERE userID = (?)", (userID, ))
    res = cur.fetchall()
    if res:
        return res
    else:
        return []

def getUsersForArtist(conn, cur, artistID):
    cur.execute("SELECT userID FROM user WHERE artistID = (?)", (artistID, ))
    res = cur.fetchall()
    if res:
        return res
    else:
        return []

def updateLastArtistSingle(conn, cur, artistID, lastID, lastDate, lastName):
    cur.execute("UPDATE artist SET lastSingleID = (?), lastSingleDate = (?), lastSingleName = (?) WHERE artistID = (?);", (lastID, lastDate, lastName, artistID))
    conn.commit()

def updateLastArtistAlbum(conn, cur, artistID, lastID, lastDate, lastName):
    cur.execute("UPDATE artist SET lastAlbumID = (?), lastAlbumDate = (?), lastAlbumName = (?) WHERE artistID = (?);", (lastID, lastDate, lastName, artistID))
    conn.commit()

def addArtist(conn, cur, artistID, lastSingleID, lastSingleDate, lastSingleName, lastAlbumID, lastAlbumDate, lastAlbumName):
    cur.execute("INSERT INTO artist (artistID, lastSingleID, lastSingleDate, lastSingleName, lastAlbumID, lastAlbumDate, lastAlbumName) VALUES (?, ?, ?, ?, ?, ?, ?)", (artistID, lastSingleID, lastSingleDate, lastSingleName, lastAlbumID, lastAlbumDate, lastAlbumName))
    conn.commit()

def getArtist(conn, cur, artistID):
    cur.execute("SELECT * FROM artist WHERE artistID = (?)", (artistID, ))
    res = cur.fetchone()
    if res:
        return res
    else:
        return []

def getArtists(conn, cur):
    cur.execute("SELECT artistID FROM artist")
    res = cur.fetchall()
    if res:
        return res
    else:
        return []

def removeArtist(conn, cur, artistID):
    cur.execute("DELETE FROM artist WHERE artistID = (?);", (artistID, ))
    conn.commit()

def botAddArtist(con, cur, artistId):
    artist = getArtist(con, cur, artistId)
    if not artist:
        latestAlbum = getNewestRelease(artistId, 'album', True)
        latestSingle = getNewestRelease(artistId, 'single', True)
        addArtist(con, cur, artistId, latestSingle['id'], latestSingle['release_date'], latestSingle['name'], latestAlbum['id'], latestAlbum['release_date'], latestAlbum['name'])
        print("Now artist "+artistId+" is being tracked")
        return

def botRemoveArtist(con, cur, artistId):
    users = getUsersForArtist(con, cur, artistId)
    if len(users)==0:
        removeArtist(con, cur, artistId)
        print("Now artist "+artistId+" is no longer tracked")
        return

def generateMessage(release):
    message = "*"+escapeMarkdown(release['name'])+"*\n_"+escapeMarkdown(release['artists'][0]['name'])+"_\n\n🎵 "+release['release_date']+"\n▶️ #"+release['album_type'][:1].upper()+release['album_type'][1:]
    return message

def sendReleaseToUsers(con, cur, artistId, release):
    users = getUsersForArtist(con, cur, artistId)
    message = generateMessage(release)
    imageID = None
    for user in users:
        if not imageID:
            imageID = bot.sendPhoto(user[0], release['images'][0]['url'], message, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Spotify Link", url="https://open.spotify.com/album/"+release['id'])]])).photo[0].file_id
        else:
            bot.sendPhoto(user[0], imageID, message, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Spotify Link", url="https://open.spotify.com/album/"+release['id'])]]))
        time.sleep(1)

def updateNewReleases(con, cur, artistId):
    latestAlbum = getNewestRelease(artistId, 'album')
    latestSingle = getNewestRelease(artistId, 'single')
    artist = getArtist(con, cur, artistId)
    if not artist:
        addArtist(con, cur, artistId, latestSingle['id'], latestSingle['release_date'], latestSingle['name'], latestAlbum['id'], latestAlbum['release_date'], latestAlbum['name'])
        return
    if latestSingle['id'] != artist[1]:
        if latestSingle['name'] != artist[3]:
            dbDate = datetime.datetime.strptime(artist[2], '%Y-%m-%d')
            newDate = datetime.datetime.strptime(latestSingle['release_date'], '%Y-%m-%d')
            if dbDate <= newDate:
                updateLastArtistSingle(con, cur, artistId, latestSingle['id'], latestSingle['release_date'], latestSingle['name'])
                print("New single found for "+artistId+": "+latestSingle['artists'][0]['name']+" - "+latestSingle['name'])
                sendReleaseToUsers(con, cur, artistId, latestSingle)
    if latestAlbum['id'] != artist[4]:
        if latestAlbum['name'] != artist[6]:
            dbDate = datetime.datetime.strptime(artist[5], '%Y-%m-%d')
            newDate = datetime.datetime.strptime(latestAlbum['release_date'], '%Y-%m-%d')
            if dbDate <= newDate:
                updateLastArtistAlbum(con, cur, artistId, latestAlbum['id'], latestAlbum['release_date'], latestAlbum['name'])
                print("New album found for "+artistId+": "+latestAlbum['artists'][0]['name']+" - "+latestAlbum['name'])
                sendReleaseToUsers(con, cur, artistId, latestAlbum)


def getNewestRelease(artistId, album_type, local = False):
    if local:
        lastRelease = sp.artist_albums(artistId,album_type=album_type,country='IT',limit=1)['items']
    else:
        lastRelease = sp.artist_albums(artistId,album_type=album_type,limit=1)['items']
    if len(lastRelease)>0:
        lastRelease = lastRelease[0]
    else:
        lastRelease = {'release_date': '1910-01-01', 'id': '', 'name': ''}
    if 'release_date_precision' in lastRelease:
        if lastRelease['release_date_precision'] == "year":
            lastRelease['release_date'] = lastRelease['release_date']+"-01-01"
        if lastRelease['release_date_precision'] == "month":
            lastRelease['release_date'] = lastRelease['release_date']+"-01"
    lastRelease['release_date'] = lastRelease['release_date'][:10]
    return lastRelease


def botGetLastArtistReleases(userID, artistId):
    con = sqlite3.connect(os.path.join(os.path.dirname(os.path.realpath(__file__)),'database.db'))
    cur = con.cursor()
    dbSetup(con, cur)
    artist = getArtist(con, cur, artistId)
    if artist:
        if artist[1] != "":
            lastSingle = sp.album(artist[1])
            bot.sendPhoto(userID, lastSingle['images'][0]['url'], generateMessage(lastSingle), parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Spotify Link", url="https://open.spotify.com/album/"+lastSingle['id'])]]))
        else:
            bot.sendMessage(userID, "No last single recorded")
        time.sleep(1)
        if artist[4] != "":
            lastAlbum = sp.album(artist[4])
            bot.sendPhoto(userID, lastAlbum['images'][0]['url'], generateMessage(lastAlbum), parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Spotify Link", url="https://open.spotify.com/album/"+lastAlbum['id'])]]))
        else:
            bot.sendMessage(userID, "No last album recorded")
    else:
        bot.sendMessage(userID, artistId+" is not tracked, you should add it before viewing the latest releases!")


def getSubscriptions(userID):
    con = sqlite3.connect(os.path.join(os.path.dirname(os.path.realpath(__file__)),'database.db'))
    cur = con.cursor()
    dbSetup(con, cur)
    artists = getArtistsForUser(con, cur, userID)
    con.close()
    lista = []
    for artist in artists:
        artist = artist[0]
        lista.append(artist)
    if len(lista)>0:
        listLista = list(chunks(lista, 20))
        result = ""
        for listObj in listLista:
            spotiArtists = sp.artists(listObj)
            for artist in spotiArtists['artists']:
                result += "- ["+escapeMarkdown(artist['name'])+"](https://open.spotify.com/artist/"+artist['id']+")\n"
        if result == "":
            result = "_No One_"
    else:
        result = "_No One_"
    bot.sendMessage(userID, "*Currently subscribed to:*\n"+result, parse_mode="Markdown", disable_web_page_preview=True)


def addRemoveArtist(userID, artistID):
    con = sqlite3.connect(os.path.join(os.path.dirname(os.path.realpath(__file__)),'database.db'))
    cur = con.cursor()
    dbSetup(con, cur)
    spotiArtist = sp.artist(artistID)
    artists = getArtistsForUser(con, cur, userID)
    if (artistID, ) in artists:
        removeArtistFromUser(con, cur, userID, artistID)
        print("Removed artist "+artistID+" ("+spotiArtist['name']+") for "+str(userID))
        bot.sendMessage(userID, "You've unsubscribed to "+spotiArtist['name']+".")
        botRemoveArtist(con, cur, artistID)
    else:
        addArtistToUser(con, cur, userID, artistID)
        print("Added artist "+artistID+" ("+spotiArtist['name']+") for "+str(userID))
        bot.sendMessage(userID, "You've subscribed to "+spotiArtist['name']+".")
        botAddArtist(con, cur, artistID)
    con.close()

if __name__ == "__main__":
    con = sqlite3.connect(os.path.join(os.path.dirname(os.path.realpath(__file__)),'database.db'))
    cur = con.cursor()
    dbSetup(con, cur)
    artists = getArtists(con, cur)
    for artist in artists:
        updateNewReleases(con, cur, artist[0])
    con.close()

# users(id, artist)
# artists(id, lastSingleID, lastSingleDate, lastSingleName, lastAlbumID, lastAlbumDate, lastAlbumName)
