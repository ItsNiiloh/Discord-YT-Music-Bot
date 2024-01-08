# Discord Music Bot

## Description

This is a Discord bot that plays music from YouTube in your Discord server's voice channels. It uses the discord.py and yt-dlp libraries to download and play audio from YouTube videos.

## Installation

1. Clone the repository.
2. Install the required Python libraries with pip install -r requirements.txt.
3. Create a .env file in the root directory and add your bot token with the line BOT_TOKEN=<Your Bot Token>. (need to create a discord developer account)
4. Run app.py to start the bot.

## Features

Play audio from a YouTube URL or search term
Queue songs to play in order
Skip, pause, resume, and stop playback
Leave the voice channel
Commands
!play <URL or search term>: Play the audio from the provided YouTube URL or search term.
!queue: Display the current queue of songs.
!skip: Skip the currently playing song.
!pause: Pause the currently playing song.
!resume: Resume playing the currently paused song.
!stop: Stop playing music and clear the queue.
!leave: Leave the voice channel.



