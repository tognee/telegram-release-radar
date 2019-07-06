#!/usr/bin/env python3
import os
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, CallbackQueryHandler, Filters, CallbackContext
import logging

import releaseRadar as rr

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

def start(update: Update, context: CallbackContext):
	context.bot.sendMessage(update.message.chat_id,"""
Hey!
Send me the spotify link that you want to follow and then I'll notify you if something new comes out.
		""")

def subscriptions(update: Update, context: CallbackContext):
	rr.getSubscriptions(update.message.from_user.id)

def textHandler(update: Update, context: CallbackContext):
	query = update.message.text
	if query.lower().startswith("https://open.spotify.com/artist/"):
		query = query[32:]
		if '?' in query:
			query = query[:query.find('?')]
	elif query.lower().startswith("spotify:artist:"):
		query = query[15:]
	elif query.lower().startswith(".subs"):
		rr.getSubscriptions(update.message.from_user.id)
		return True
	elif query.lower().startswith(".latest "):
		query = query[8:]
		if query.lower().startswith("https://open.spotify.com/artist/"):
			query = query[32:]
			if '?' in query:
				query = query[:query.find('?')]
		elif query.lower().startswith("spotify:artist:"):
			query = query[15:]
		rr.botGetLastArtistReleases(update.message.from_user.id, query.strip())
		return True
	else:
		return True
	rr.addRemoveArtist(update.message.from_user.id, query.strip())


updater = Updater(rr.TOKEN, use_context=True)
# add handlers
dispatcher = updater.dispatcher

dispatcher.add_handler(CommandHandler('start', start, pass_args=True))
dispatcher.add_handler(CommandHandler('subs', subscriptions))
dispatcher.add_handler(MessageHandler(Filters.all, textHandler))

updater.start_polling()
