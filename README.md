# telegram-release-radar
Telegram bot that notifies you if a new track has been released on Spotify

## Usage
Create a `.env` file containing the Telegram bot Token and the Client ID and Secret from your Spotify App.  
The format should be:

```
BOT_TOKEN = <>
SPOTIFY_CLIENT_ID = <>
SPOTIFY_CLIENT_SECRET = <>
```

Replace the `<>` with the correct string.  
`bot.py` will make the bot accept the commands to subscribe and unsubscribe from a specific artist.  
`releaseRadar.py` should be run whenever you want to check for new Albums and Singles.

If you're on Windows you can use the Task Scheduler built into the OS
If you're on Linux you can use crontab

## Commands
| command                               | function                                      |
| ------------------------------------- | --------------------------------------------- |
| `/start`                              | Gives a small introduction to the bot         |
| spotify artist url or uri             | Subscribes or Unsubscribes to the artist link |
| `.subs`                               | Lists all subscribed artists                  |
| `.latest [spotify artist url or uri]` | Shows latest releases for that artist         |
