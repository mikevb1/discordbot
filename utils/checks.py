from discord.ext import commands


def need_db(command):
    """Decorator, not check, to mark the command as needing a DB connection."""
    command._db = True
    return command


def bot_config_attr(attr):
    return commands.check(lambda ctx: attr in ctx.bot.config)


async def check_permissions(ctx, perms):
    if ctx.bot.app.owner.id == ctx.author.id:
        return True
    resolved = ctx.channel.permissions_for(ctx.author)
    return all(getattr(resolved, name, None) == value for name, value in perms.items())


def owner_or_permissions(**perms):
    return commands.check(lambda ctx: check_permissions(ctx, perms))
