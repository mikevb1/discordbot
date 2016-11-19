from xml.etree import ElementTree as XMLTree
import datetime
import asyncio
import random
import re

from discord.ext import commands
import discord
import aiohttp

from .utils.checks import bot_config_attr
from .utils.errors import NotFound
from .utils.utils import between
from .utils.emoji import digits
from .base import BaseCog


FACTS = 'http://catfacts-api.appspot.com/api/facts?number={count}'

HOME = 'http://thecatapi.com/'
HOME_BY_ID = HOME + '?id={image_id}'
GET = HOME + 'api/images/get?api_key={api_key}&format=xml{category}&sub_id={sub_id}'
REPORT = HOME + 'api/images/report?api_key={api_key}&sub_id={sub_id}&image_id={image_id}{reason}'
VOTE = HOME + 'api/images/vote?api_key={api_key}&sub_id={sub_id}&image_id={image_id}&score={score}'
GET_VOTES = HOME + 'api/images/getvotes?api_key={api_key}&sub_id={sub_id}'
FAVE = HOME + 'api/images/favourite?api_key={api_key}&sub_id={sub_id}&image_id={image_id}&action={act}'
GET_FAVES = HOME + 'api/images/getfavourites?api_key={api_key}&sub_id={sub_id}'

CATEGORIES = ('hats', 'space', 'funny', 'sunglasses', 'boxes',
              'caturday', 'ties', 'dream', 'sinks', 'clothes')
REACTIONS = ('\N{PILE OF POO}', *digits[1:], '\N{HEAVY BLACK HEART}')


class MostRecent(Exception):
    pass


class Images(BaseCog):
    def __init__(self, bot):
        self.bot = bot

    def make_xkcd_url(self, num=''):
        url = 'http://xkcd.com/'
        if num:
            url += str(num) + '/'
        url += 'info.0.json'
        return url

    async def fetch_xkcd(self, num=''):
        url = self.make_xkcd_url(num)
        status, data = await self.request(url)
        if status != 200:
            raise NotFound('Could not get comic.')
        else:
            return data

    def xkcd_date(self, data):
        if 'date' in data:
            date = data['date']
        else:
            date = datetime.date(*map(int, (data['year'],
                                            data['month'],
                                            data['day'])))
        return date

    async def xkcd_insert(self, data):
        async with self.bot.db.transaction():
            return await self.bot.db.execute('''
                INSERT INTO xkcd VALUES ($1, $2, $3, $4, $5)
                ''', data['num'], data['safe_title'],
                data['alt'], data['img'], self.xkcd_date(data))

    @commands.command()
    async def xkcd(self, comic=''):
        """Get xkcd comics.

        [comic] can be the number of a comic or "r"/"rand"/"random"
        """
        data = None
        await self.bot.type()
        try:
            if comic in ('r', 'rand', 'random') or not comic:
                data = await self.fetch_xkcd()
                await self.bot.db.fetchrow('''
                    SELECT * FROM xkcd WHERE num = $1
                    ''', data['num']) or await self.xkcd_insert(data)
                if not comic:
                    raise MostRecent
                while True:
                    comic = random.randint(1, data['num'])
                    if comic != 404:
                        break
            else:
                if not comic.isdigit():
                    return
                comic = int(comic)
            data = await self.bot.db.fetchrow('''
                SELECT * FROM xkcd WHERE num = $1
                ''', comic) or await self.fetch_xkcd(comic)
            if isinstance(data, dict):
                await self.xkcd_insert(data)
        except NotFound as e:
            await self.bot.say(e)
            return
        except MostRecent:
            pass

        message = '**Date**: {1:%m/%d/%Y}' \
                  '\n**Title**: {0[num]}. {0[safe_title]}' \
                  '\n**Alt Text**: {0[alt]}' \
                  '\n**Image**: {0[img]}'.format(data, self.xkcd_date(data))
        await self.bot.say(message)

    async def fetch_facts(self, count):
        status, j = await self.request(FACTS.format(count=count))
        if status != 200 or (j is not None and j['success'] != 'true'):
            raise NotFound('No cat fact available.')
        return j['facts']

    async def fetch_cat(self, url, **format_args):
        url = url.format(api_key=self.bot.config['cat_api'],
                         reason=format_args.pop('reason', ''),
                         **format_args)
        status, data = await self.request(url, 'text')
        if status != 200:
            raise NotFound('Could not get cat.')
        return data

    async def try_cat_image(self, url, attempt=1):
        if url is None:
            return False
        try:
            resp = await self.request(url, 'read')
        except aiohttp.ClientOSError:  # DNS name not resolved
            return False
        else:
            return resp.status == 200

    @commands.group(pass_context=True, invoke_without_command=True)
    @bot_config_attr('cat_api')
    async def cat(self, ctx, category=''):
        """Get a random cat image.

        [category] can be one of:
            hats, space, funny, sunglasses,
            boxes, caturday, ties, dream,
            sinks, clothes

        Within 30 seconds of the image being posted anyone can react with:
            * 1-10 to rate the image.
            * heart to favorite the image.
            * poop to report the image.
        """
        if category in CATEGORIES:
            category = '&category=' + category
        elif category:
            await self.bot.say('Invalid category. Try one of: ' + ', '.join(CATEGORIES))
        sub_id = ctx.message.author.id
        await self.bot.type()
        try:
            while True:
                x = await self.fetch_cat(GET, category=category, sub_id=sub_id)
                image_root = XMLTree.fromstring(x).find('data').find('images').find('image')
                image_url = image_root.find('url').text
                image_id = image_root.find('id').text
                if await self.try_cat_image(image_url):
                    break
                else:
                    await self.fetch_cat(REPORT, sub_id=sub_id,
                                         image_id=image_id,
                                         reason='DNS name not resolved')
        except NotFound as e:
            await self.bot.say(str(e))
            return

        try:
            fact = (await self.fetch_facts(1))[0]
        except NotFound as e:
            fact = ''

        embed = discord.Embed(title=image_id, url=HOME_BY_ID.format(image_id=image_id),
                              description=fact or None)
        embed.set_image(url=image_url)
        embed.add_field(name='Rate', value='{0[1]}-{0[10]}'.format(REACTIONS))
        embed.add_field(name='Favorite: ' + REACTIONS[11],
                        value='Report: ' + REACTIONS[0])

        if not ctx.message.channel.permissions_for(ctx.message.server.me).add_reactions:
            await self.bot.say(embed=embed)
            return

        embed.colour = discord.Colour.green()
        msg = await self.bot.say(embed=embed)

        for reaction in REACTIONS[1:]:
            await self.bot.add_reaction(msg, reaction)

        actions = []
        votes = {}
        faved = set()
        reported = False

        def vote_check(reaction, user):
            sub_id = user.id
            score = REACTIONS.index(reaction.emoji)
            if 1 <= score <= 10:
                votes[sub_id] = score
            elif score == 11:
                faved.add(sub_id)
                actions.append(self.fetch_cat(FAVE, sub_id=sub_id,
                                              image_id=image_id,
                                              act='add'))
            else:
                nonlocal reported
                reported = True
                actions.append(self.fetch_cat(REPORT, sub_id=sub_id, image_id=image_id))
                return True
            if len(actions) + len(votes) == 20:
                return True

        await self.bot.wait_for_reaction(REACTIONS, timeout=30,
                                         message=msg, check=vote_check)

        if reported:
            await self.bot.delete_message(msg)
            await actions[-1]
            return

        embed.colour = discord.Colour.red()
        embed._fields = None
        await self.bot.edit_message(msg, embed=embed)
        for reaction in REACTIONS[1:]:
            await self.bot.remove_reaction(msg, reaction, self.bot.user)

        for sub_id, score in votes.items():
            actions.append(self.fetch_cat(VOTE, sub_id=sub_id,
                                          image_id=image_id,
                                          score=score))
        await asyncio.gather(*actions)

    @cat.command(name='facts', aliases=['fact'])
    async def cat_facts(self, count: float = 1):
        """Get cat facts.

        0 < [count] <= 20
        """
        if count < 0:
            count = 1
        else:
            count = between(count, 0, 20)
        partial = count - int(count)
        count = int(count)
        if partial:
            count += 1
        elif count == 0:
            return

        try:
            facts = await self.fetch_facts(count)
        except NotFound as e:
            facts = [str(e)]
        else:
            if partial:
                end_ind = int(len(facts[-1]) * partial)
                facts[-1] = facts[-1][:end_ind] or facts[-1][0]

        if len(facts) > 1:
            msg = commands.Paginator(prefix='', suffix='')
            for ind, fact in enumerate(facts):
                msg.add_line('{}. {}'.format(ind + 1, fact))
            for page in msg.pages:
                await self.bot.say(page)
        else:
            await self.bot.say(facts[0])

    @cat_facts.error
    async def cat_facts_error(self, exc, ctx):
        if isinstance(exc, commands.BadArgument):
            pass
        else:
            ctx.command = ctx.command.name
            await self.bot.on_command_error(exc, ctx)

    @cat.command(pass_context=True)
    async def ratings(self, ctx):
        """Get a list of images you've rated.

        To change your rating of an image, see the "rerate" command.
        """
        sub_id = ctx.message.author.id
        await self.bot.type()
        root = XMLTree.fromstring(await self.fetch_cat(GET_VOTES, sub_id=sub_id))
        ids = [i.text for i in root.iter('id')]
        scores = [s.text for s in root.iter('score')]
        urls = [u.text for u in root.iter('url')]
        if not ids:
            await self.bot.say("You haven't rated any images.")
            return
        msg = commands.Paginator(prefix='', suffix='')
        for s, i, u in zip(scores, ids, urls):
            msg.add_line('{score}/10 {id}: {url}.'.format(score=s, id=i, url=u))
        for page in msg.pages:
            await self.bot.say(page)

    @cat.command(pass_context=True)
    async def rerate(self, ctx, image_id, new_score):
        """Re-rate an image you've rated before.

        <new_score> can be either just a number or "X/10"
        """
        sub_id = ctx.message.author.id
        await self.bot.type()
        root = XMLTree.fromstring(await self.fetch_cat(GET_VOTES, sub_id=sub_id))
        ids = [i.text for i in root.iter('id')]
        if image_id not in ids:
            await self.bot.say('Invalid image_id.')
            return
        if new_score.isdigit():
            score = between(int(new_score), 1, 10)
        elif new_score in REACTIONS[1:11]:
            score = REACTIONS.index(new_score)
        else:
            score_match = re.match(r'(-?[0-9]*)/10', new_score)
            if score_match is None:
                await self.bot.say('Invalid score format.')
                return
            score = between(int(score_match.group(1)), 1, 10)
        await self.fetch_cat(VOTE, sub_id=sub_id, image_id=image_id, score=score)
        await self.bot.say('\N{THUMBS UP SIGN} Changed your rating.')

    @cat.command(pass_context=True, aliases=['faves', 'favourites'])
    async def favorites(self, ctx, to_remove=None):
        """Get a list of your favorited images.

        Images are posted in format "ID: url".
        [to_remove] is an ID of the image you want to unfavorite.
        """
        sub_id = ctx.message.author.id
        await self.bot.type()
        root = XMLTree.fromstring(await self.fetch_cat(GET_FAVES, sub_id=sub_id))
        ids = [i.text for i in root.iter('id')]
        urls = [u.text for u in root.iter('url')]
        if not ids:
            await self.bot.say("You don't have any favorite images.")
            return

        if to_remove is not None:
            if to_remove not in ids:
                await self.bot.say("That's not in your favorites.")
                return
            await self.fetch_cat(FAVE, sub_id=sub_id,
                                 image_id=to_remove,
                                 act='remove')
            await self.bot.say('\N{THUMBS UP SIGN} Removed favorite.')
            return
        msg = commands.Paginator(prefix='', suffix='')
        for i, u in zip(ids, urls):
            msg.add_line('`{id}`: {url}.'.format(id=i, url=u))
        for page in msg.pages:
            await self.bot.say(page)


def setup(bot):
    """Magic function to set up cog."""
    bot.add_cog(Images(bot))
