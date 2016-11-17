from datetime import datetime

from discord.ext import commands
import discord

from .utils.utils import plural
from .utils import checks
from .base import BaseCog


UPTIME_BRIEF = ('{d}d', '{h}h', '{m}m', '{s}s')
UPTIME_LONG = ('{d} day{dp}', '{h} hour{hp}',
               '{m} minute{mp}', '{s} second{sp}')


class Meta(BaseCog):
    def __init__(self, bot):
        self.bot = bot

    @commands.group(hidden=True)
    async def manage(self):
        """Manage bot user attributes."""
        pass

    @manage.command()
    @checks.is_owner()
    async def name(self, *, new_name=None):
        """Rename bot."""
        if new_name:
            await self.bot.edit_profile(username=new_name)

    @manage.command(pass_context=True, aliases=['game'])
    @checks.is_owner()
    async def status(self, ctx, *, new_status=None):
        """Change bot's online status or game name."""
        for s in self.bot.servers:
            bot_member = s.get_member(self.bot.user.id)
            break

        if ctx.invoked_with == 'game':
            await self.bot.change_presence(
                game=discord.Game(name=new_status),
                status=bot_member.status)
        else:
            await self.bot.change_presence(
                game=bot_member.game,
                status=getattr(discord.Status, new_status or '', 'online'))

    async def set_avatar_by_url(self, url):
        status, image = await self.request(url, 'read')
        if status != 200:
            return
        await self.bot.edit_profile(avatar=image)

    @manage.command(pass_context=True)
    @checks.is_owner()
    async def avatar(self, ctx, new_avatar=None):
        """Change bot's avatar.

        new_avatar can be a link to an image,
        left blank with an attached image,
        or left blank with no attachment to remove image
        """
        if new_avatar is not None:
            await self.set_avatar_by_url(new_avatar)
        else:
            if len(ctx.message.attachments):
                await self.set_avatar_by_url(ctx.message.attachments[0]['url'])
            else:
                await self.bot.edit_profile(avatar=None)

    @manage.command(pass_context=True, no_pm=True)
    @commands.bot_has_permissions(change_nickname=True)
    @checks.owner_or_permissions(manage_nicknames=True)
    async def nick(self, ctx, *, new_nick=None):
        """Change bot's nickname."""
        bot_member = ctx.message.server.me
        await self.bot.change_nickname(bot_member, new_nick or None)

    def get_oauth_url(self):
        perms = discord.Permissions()
        perms.kick_members = True
        perms.ban_members = True
        perms.read_messages = True
        perms.send_messages = True
        perms.manage_messages = True
        perms.embed_links = True
        perms.change_nickname = True
        perms.add_reactions = True
        return discord.utils.oauth_url(self.bot.client_id, permissions=perms)

    @commands.command()
    async def join(self):
        """Add bot to one of your servers.

        Bots can no longer accept instant invite links.
        You can only invite/add bots to servers you create.
        This command gives you a link to add this bot to your servers.
        """
        desc = '\n'.join([
            'Follow this link, login if necessary, then select a server you own to add me to.',
            'The requested permissions are required for some of my commands to function.'])
        embed = discord.Embed(title='Click here!',
                              url=self.get_oauth_url(),
                              description=desc)
        await self.bot.say(embed=embed)

    def get_uptime(self, brief=False):
        now = datetime.utcnow()
        delta = now - self.bot.start_time
        hours, remainder = divmod(int(delta.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        days, hours = divmod(hours, 24)

        if brief:
            fmt = UPTIME_BRIEF
            joiner = ' '
        else:
            fmt = UPTIME_LONG
            joiner = ', '

        for ind, time in enumerate((days, hours, minutes, seconds, None)):
            if time:
                fmt = fmt[ind:]
                break
            elif time is None:
                fmt = [fmt[3]]

        return joiner.join(fmt).format(
            d=days, dp=plural(days),
            h=hours, hp=plural(hours),
            m=minutes, mp=plural(minutes),
            s=seconds, sp=plural(seconds))

    @commands.command()
    async def about(self):
        """Display bot information."""
        description = 'Uptime: {}\n[Invite Link]({})'.format(self.get_uptime(brief=True),
                                                             self.get_oauth_url())
        embed = discord.Embed(description=description)
        embed.set_author(name=str(self.bot.owner),
                         icon_url=self.bot.owner.avatar_url)
        docs = 'Say {0.command_prefix}help'
        if self.bot.config.get('userdocs'):
            docs += ' or see [here]({0.config[userdocs]})'
        docs += '.'
        embed.add_field(name='Documentation', value=docs.format(self.bot))
        source = self.bot.config.get('source')
        if source:
            embed.add_field(name='Source', value='See [here]({}).'.format(source))
        embed.set_footer(text='Made with discord.py | Online Since', icon_url='http://i.imgur.com/5BFecvA.png')
        embed.timestamp = self.bot.start_time
        await self.bot.say(embed=embed)

    @commands.command()
    async def uptime(self):
        """Display bot uptime."""
        uptime = '\n'.join(self.get_uptime().split(', '))
        embed = discord.Embed(
            description='```ocaml\nUptime:\n{}\n```'.format(uptime),
            timestamp=self.bot.start_time)
        embed.set_footer(text='Online Since')
        await self.bot.say(embed=embed)

    @commands.command(pass_context=True, aliases=['ping'])
    async def poke(self, ctx):
        """Make sure bot is working."""
        if ctx.invoked_with == 'poke':
            reply = 'I need an adult!'
        else:
            reply = 'Pong!'
        await self.bot.say(reply)


def setup(bot):
    """Magic function to set up cog."""
    bot.add_cog(Meta(bot))
