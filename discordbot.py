"""Discord bot for Discord."""

import discord
import asyncio
import logging
import json
from collections import OrderedDict

from creds import dis_name, dis_pass
from command import Command

# Discord Client/Bot
client = discord.Client()

# Logging Setup
log = logging.getLogger('discord')
log.setLevel(logging.INFO)
fhandler = logging.FileHandler(
    filename='discordbot.log',
    encoding='utf-8',
    mode='w')
fhandler.setFormatter(logging.Formatter(
    '%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
log.addHandler(fhandler)


# General helper functions.


def func_desc(func):
    """Get first sentence/description of function from docstring.

    Arguments:
    func -- function to get description from

    Returns:
    str -- "No description." or first sentence of docstring
    """
    doc = func.__doc__
    if doc is None:
        return 'No description.'
    desc = ''
    for c in doc:
        if c == '\n':
            desc += ' '
        desc += c
        if c == '.':
            break
    return desc


def list_align(words):
    """Find word of greatest length and return list of differences in length.

    Arguments:
    words -- list of words

    Returns:
    lens -- list of ints
    """
    longest = 0
    lens = []
    for word in words:
        if len(word) > longest:
            longest = len(word)
    for word in words:
        lens.append(longest - len(word))
    return lens


async def com_perm_check(msg, com):
    """Check if command can be used by user and on server."""
    if (com.servers is None or msg.server.id in com.servers) and \
            (com.users is None or msg.author in com.users):
        return True
    await client.send_message(msg.channel, 'You cannot perform that command!')
    return False


# Command functions.


async def commands(msg, commands):
    """Print all commands available on server.

    Arguments:
    msg -- discord.msg, to get server and channel
    commands -- command dict
    """
    await client.send_message(msg.channel, 'Available commands:')
    serv_coms = []
    for com in commands.values():
        if await com_perm_check(msg, com):
            serv_coms.append(com)
    # serv_coms = [com for com in commands.values()
    # if await com_perm_check(msg, com)]
    space = list_align([com.name for com in serv_coms])
    for ind, com in enumerate(serv_coms):
        await client.send_message(msg.channel, '`{}{}: {}`'.format(
            com,
            ' ' * (space[ind] + 1),
            func_desc(com.func)))


def stream_name_link(nl):
    """Get stream link from name or vice-versa."""
    if nl.startswith('http://') or nl.startswith('https://') or \
            nl.startswith('twitch.tv') or nl.startswith('hitbox.tv'):
        link = nl
        name = link.split('/')[-1]
    else:
        name = nl
        link = 'http://twitch.tv/{}'.format(name.lower())
    return name, link


async def stream(msg, *args):
    """Announce that you or someone else is streaming.

    Examples:
    !stream sgtlaggy -- sgtlaggy is streaming at http://twitch.tv/sgthoppy
    !stream -- YourName is streaming at http://twitch.tv/YourName
    """
    with open('stream.json', 'r') as s:
        streamers = json.load(s)
    author = str(msg.author)
    if len(args) == 0:
        try:
            link = streamers[author]
            await client.send_message(
                msg.channel,
                '{} is going live over at {}'.format(author, link))
        except KeyError:
            pass
    else:
        if len(msg.mentions) >= len(args):
            for m in msg.mentions:
                try:
                    name, link = m.name, streamers[m.name]
                except KeyError:
                    name, link = stream_name_link(m.name)
                await client.send_message(
                    msg.channel,
                    '{} is going live over at {}'.format(name, link))
            return
        name, link = stream_name_link(args[0])
        if name in streamers:
            link = streamers[name]
        await client.send_message(
            msg.channel,
            '{} is streaming over at {}'.format(name, link))


async def add_stream(msg, *args):
    """Add or update a streamer's link."""
    try:
        with open('stream.json', 'r') as s:
            streamers = json.load(s)
    except FileNotFoundError:
        streamers = {}
    if len(msg.mentions) == 1:
        name, link = str(msg.mentions[0]), args[1]
    elif len(args) == 1:
        name, link = str(msg.author), args[0]
    else:
        name, link = args
    streamers[name] = link
    with open('stream.json', 'w') as s:
        json.dump(streamers, s)
        await client.send_message(
            msg.channel,
            'Adding {} ({}) to steamer list.'.format(name, link))


async def remove_stream(msg, *args):
    """Remove streamer from list."""
    with open('stream.json', 'r') as s:
        streamers = json.load(s)
    try:
        name = str(msg.mentions[0])
    except:
        name = args[0]
    try:
        del streamers[name]
    except:
        await client.send_message(
            msg.channel,
            'Streamer {} does not exist in list.'.format(args[0]))
        return
    await client.send_message(
        msg.channel,
        '{} has been removed.'.format(args[0]))
    with open('stream.json', 'w') as s:
        json.dump(streamers, s)


async def join(msg, *args):
    """Tell bot to join server using ID or discordgg link."""
    try:
        await client.accept_invite(args[0])
    except IndexError:
        pass
    except discord.HTTPException:
        await client.send_message(msg.channel, 'Could not join server.')
    except discord.NotFound:
        await client.send_message(
            msg.channel,
            'Invite is invalid or expired.')


async def leave(msg, *args):
    """Tell bot to leave server."""
    try:
        await client.leave_server(msg.server)
    except discord.HTTPException:
        await client.send_message(msg.channel, 'Could not leave server.')


# Command Setup
serv = {
    'test': '124369415344095234',
    'tccn': '126440582619856896'}
coms_list = [
    Command('!commands', commands, None, None),
    Command('!join', join, None, None),
    Command('!leave', leave, None, None),
    Command('!stream', stream, None, None),
    Command('!addstream', add_stream, None, None),
    Command('!remstream', remove_stream, None, None)]
coms = OrderedDict()
for com in coms_list:
    coms[com.name] = com


# Discord functions.


@client.event
async def on_ready():
    """Called when bot is ready."""
    log.info('Bot ready!')


@client.event
async def on_message(msg):
    """Define what happens when message is recieved."""
    if msg.author == client.user:
        return
    com, *args = msg.content.split()
    if not await com_perm_check(msg, coms[com]):
        return
    if com in coms:
        if com == '!commands':
            await coms[com].func(msg, coms)
        else:
            await coms[com].func(msg, *args)

if __name__ == '__main__':
    client.run(dis_name, dis_pass)
