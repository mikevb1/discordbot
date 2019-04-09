#!/usr/bin/env python3
import asyncio
import logging
import sys

from lagbot import LagBot

# stolen from R.Danny
try:
    import uvloop
except ImportError:
    pass
else:
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())


debug = any('debug' in arg.lower() for arg in sys.argv)
logging.basicConfig(level=logging.INFO if debug else logging.WARNING)

help_attrs = {'hidden': True}
initial_cogs = [f'cogs.{cog}' for cog in [
    'cog', 'images', 'management', 'meta',
    'misc', 'overwatch', 'owner']]
if not debug:
    initial_cogs.append('cogs.botlist')

if __name__ == '__main__':
    bot = LagBot(help_attrs=help_attrs, debug=debug)

    for cog in initial_cogs:
        try:
            bot.load_extension(cog)
        except Exception as e:
            logging.exception(f"Couldn't load cog {cog}")

    status = bot.run()
    if status:
        logging.critical(f'Exiting with {status}.')
    logging.shutdown()
    sys.exit(status)
