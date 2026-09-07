import logging

_username_cache = {}


async def get_bot_username(bot) -> str:
    """Return the bot's @username, fetched once via get_me() and cached."""
    cached = _username_cache.get(id(bot))
    if cached:
        return cached

    me = await bot.get_me()
    username = me.username or ""
    _username_cache[id(bot)] = username

    if username:
        logging.info("Bot username cached: t.me/%s", username)
    else:
        logging.warning("Bot get_me() returned empty username!")
    return username