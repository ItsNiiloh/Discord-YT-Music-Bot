import re

import discord
from discord.ext import commands
from discord import FFmpegPCMAudio
import yt_dlp
import urllib
import asyncio
import threading
import os
import shutil
import sys
import subprocess as sp
from dotenv import load_dotenv


load_dotenv()
TOKEN = os.getenv('BOT_TOKEN')
PREFIX = os.getenv('BOT_PREFIX', '!')
YTDL_FORMAT = os.getenv('YTDL_FORMAT', 'worstaudio')
PRINT_STACK_TRACE = os.getenv('PRINT_STACK_TRACE', '1').lower() in ('true', 't', '1')
BOT_REPORT_COMMAND_NOT_FOUND = os.getenv('BOT_REPORT_COMMAND_NOT_FOUND', '1').lower() in ('true', 't', '1')
BOT_REPORT_DL_ERROR = os.getenv('BOT_REPORT_DL_ERROR', '0').lower() in ('true', 't', '1')
try:
    COLOR = int(os.getenv('BOT_COLOR', '280000'), 16)
except ValueError:
    print('the BOT_COLOR in .env is not a valid hex color')
    print('using default color ff0000')
    COLOR = 0xff0000


bot = commands.Bot(command_prefix=PREFIX, intents=discord.Intents(voice_states=True, guilds=True, guild_messages=True, message_content=True))
queues = {} 


def main():
    if TOKEN is None:
        return ("No token found. Please create a .env file containing the token.")
    try: bot.run(TOKEN)
    except discord.PrivilegedIntentsRequired as error:
        return error


### Commands for the bot
@bot.command(name='play', aliases=['p'])
async def play(ctx: commands.Context, *args):
    voice_state = ctx.author.voice
    if not await sense_checks(ctx, voice_state=voice_state):
        return

    query = ' '.join(args)
    # if no url was provided, search for the query
    will_need_search = not urllib.parse.urlparse(query).scheme

    server_id = ctx.guild.id

    await ctx.send(f'Looking for `{query}`...')
    with yt_dlp.YoutubeDL({'format': YTDL_FORMAT,
                           'source_address': '0.0.0.0',
                           'default_search': 'ytsearch',
                           'outtmpl': '%(id)s.%(ext)s',
                           'noplaylist': True,
                           'allow_playlist_files': False,
                           'paths': {'home': f'./dl/{server_id}'}}) as ydl:
        try:
            info = ydl.extract_info(query, download=False)
        except yt_dlp.utils.DownloadError as err:
            await notify_about_failure(ctx, err)
            return

        if 'entries' in info:
            info = info['entries'][0]
        # if the query was a search, use the first result
        await ctx.send('Downloading ' + (f'https://youtu.be/{info["id"]}' if will_need_search else f'`{info["title"]}`' + '...'))
        try:
            ydl.download([query])
        except yt_dlp.utils.DownloadError as err:
            await notify_about_failure(ctx, err)
            return
        
        path = f'./dl/{server_id}/{info["id"]}.{info["ext"]}'
        try: queues[server_id].append((path, info))
        except KeyError: # first in queue
            queues[server_id] = [(path, info)]
            try: connection = await voice_state.channel.connect()
            except discord.ClientException: connection = get_voice_client_from_channel_id(voice_state.channel.id)
            connection.play(discord.FFmpegOpusAudio(path), after=lambda error=None, connection=connection, server_id=server_id:
                                                             after_track(error, connection, server_id))


@bot.command(name='queue', aliases=['q'])
async def queue(ctx: commands.Context, *args):
    try: queue = queues[ctx.guild.id]
    except KeyError: queue = None
    if queue == None:
        await ctx.send('The botinho doesn\'t have any songs in the queue...')
    else:
        title_str = lambda val: '‣ %s\n\n' % val[1] if val[0] == 0 else '**%2d:** %s\n' % val
        queue_str = ''.join(map(title_str, enumerate([i[1]["title"] for i in queue])))
        embedVar = discord.Embed(color=COLOR)
        embedVar.add_field(name='Now playing:', value=queue_str)
        await ctx.send(embed=embedVar)
    if not await sense_checks(ctx):
        return


@bot.command(name='skip', aliases=['s'])
async def skip(ctx: commands.Context, *args):
    if not await sense_checks(ctx):
        await ctx.send('You must be in a voice channelinho to use this command.')
        return

    voice_client = get_voice_client_from_channel_id(ctx.author.voice.channel.id)
    voice_client.stop()
    await ctx.send('Skipped the song.')


@bot.command(name='pause', aliases=['ps'])
async def pause(ctx: commands.Context, *args):
    if not await sense_checks(ctx):
        await ctx.send('You must be in a voice channelinho to use this command.')
        return

    voice_client = get_voice_client_from_channel_id(ctx.author.voice.channel.id)
    if voice_client.is_paused():
        await ctx.send('Already paused, maninho...')
    else:
        voice_client.pause()
        await ctx.send('Paused the song.')


@bot.command(name='resume', aliases=['r'])
async def resume(ctx: commands.Context, *args):
    if not await sense_checks(ctx):
        await ctx.send('You must be in a voice channelinho to use this command.')
        return

    voice_client = get_voice_client_from_channel_id(ctx.author.voice.channel.id)
    if voice_client.is_playing():
        await ctx.send('Already playing, maninho...')
    else:
        voice_client.resume()
        await ctx.send('Resumed the song.')


@bot.command(name='stop', aliases=['st']) 
async def stop(ctx: commands.Context, *args):
    if not await sense_checks(ctx):
        await ctx.send('You must be in a voice channelinho to use this command.')
        return

    voice_client = get_voice_client_from_channel_id(ctx.author.voice.channel.id)
    voice_client.stop()
    queues.pop(ctx.guild.id)
    await ctx.send('Stopped and cleared the songs.')
    

@bot.command(name='leave', aliases=['l'])
async def leave(ctx: commands.Context, *args):
    if not await sense_checks(ctx):
        await ctx.send('You must be in a voice channelinho to use this command.')
        return

    voice_client = get_voice_client_from_channel_id(ctx.author.voice.channel.id)
    await voice_client.disconnect()
    await ctx.send('Disconnected from the voice channelinho.')


### Helper functions
# Get the voice client from the channel id
def get_voice_client_from_channel_id(channel_id: int):
    for voice_client in bot.voice_clients:
        if voice_client.channel.id == channel_id:
            return voice_client


# Play the next song in the queue
def after_track(error, connection, server_id):
    if error is not None:
        print(f'Error in track: {error}')
        return
    try:
        queues[server_id].pop(0)
        if len(queues[server_id]) > 0:
            connection.play(discord.FFmpegOpusAudio(queues[server_id][0][0]), after=lambda error=None, connection=connection, server_id=server_id:
                                                                                         after_track(error, connection, server_id))
        else:
            asyncio.run_coroutine_threadsafe(safe_disconnect(connection), bot.loop)
    except KeyError:
        pass


# Disconnect from the voice channel if the bot is not playing anything
async def safe_disconnect(connection):
    if not connection.is_playing():
        await connection.disconnect()


# Check if the user is in a voice channel and if the bot is in the same voice channel
async def sense_checks(ctx: commands.Context, voice_state=None) -> bool:
    if voice_state is None: voice_state = ctx.author.voice 
    if voice_state is None:
        await ctx.send('You must be in a voice channelinho to use this command.')
        return False

    if bot.user.id not in [member.id for member in ctx.author.voice.channel.members] and ctx.guild.id in queues.keys():
        await ctx.send('You must be in in the same voice channelinho as the bot to use this command.')
        return False
    return True


# Delete the dl folder when the bot is disconnected from a voice channel
@bot.event
async def on_voice_state_update(member: discord.User, before: discord.VoiceState, after: discord.VoiceState):
    if member != bot.user:
        return
    if before.channel is None and after.channel is not None: # connected to vc
        return
    if before.channel is not None and after.channel is None: # disconnected from vc
        server_id = before.channel.guild.id
        try: queues.pop(server_id)
        except KeyError: pass
        try: shutil.rmtree(f'./dl/{server_id}/')
        except FileNotFoundError: pass


# Handle command errors
@bot.event
async def on_command_error(ctx: discord.ext.commands.Context, err: discord.ext.commands.CommandError):
    # handle command errors
    if isinstance(err, discord.ext.commands.errors.CommandNotFound):
        if BOT_REPORT_COMMAND_NOT_FOUND:
            await ctx.send("Command not recognized. To see available commands type {}help".format(PREFIX))
        return

    # If unhandled command error, restart the bot
    sys.stderr.write(f'Unhandled command error raised, {err=}')
    sys.stderr.flush()
    sp.run(['./restart'])


# Handle bot errors
@bot.event
async def on_ready():
    print(f'Logged in successfully as {bot.user.name}')
async def notify_about_failure(ctx: commands.Context, err: yt_dlp.utils.DownloadError):
    if BOT_REPORT_DL_ERROR:
        # remove ANSI escape sequences from the error message
        sanitized = re.compile(r'\x1b[^m]*m').sub('', err.msg).strip()
        if sanitized[0:5].lower() == "error":
            # remove "ERROR:" from the beginning of the message
            sanitized = sanitized[5:].strip(" :")
        await ctx.send('Failed to download due to error: {}'.format(sanitized))
    else:
        await ctx.send('Sorry, failed to download this video')
    return


if __name__ == '__main__':
    try:
        sys.exit(main())
    except SystemError as error:
        if PRINT_STACK_TRACE:
            raise
        else:
            print(error)