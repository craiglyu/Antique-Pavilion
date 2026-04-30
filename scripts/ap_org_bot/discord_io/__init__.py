"""discord_io/ — Discord-specific output helpers (embeds, views, message split).

Anything in here imports `discord` and is therefore NOT importable by daemons.
Pure helpers (string split, OPUS marker parse) without discord dep stay here too
because they're conceptually about Discord message formatting.
"""
