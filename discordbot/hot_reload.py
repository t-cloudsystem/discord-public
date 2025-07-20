from logging import getLogger, StreamHandler, DEBUG, Logger
import pathlib

from discord.ext import commands
from watchfiles import awatch, Change


class HotReload:
    def __init__(self, bot: commands.Bot, *, logger=None):
        self.bot = bot
        if logger:
            self.logger: Logger = logger
        else:
            self.logger: Logger = getLogger(__name__)
            handler = StreamHandler()
            handler.setLevel(DEBUG)
            self.logger.setLevel(DEBUG)
            self.logger.addHandler(handler)
            self.logger.propagate = False

        self.logger.info("HotReload initialized")

    async def watch_files(self):
        async for changes in awatch("discordbot/cogs"):
            for change in changes:
                if change[0] == Change.modified or change[0] == Change.added:
                    cog_name = pathlib.Path(change[1]).parts[-1][:-3]  # Windows/Linux 両対応
                    self.logger.info(f"Detected change in {cog_name}, reloading...")
                    try:
                        await self.bot.reload_extension(f"discordbot.cogs.{cog_name}")
                        self.logger.info(f"Reloaded {cog_name}")
                    except Exception as e:
                        self.logger.error(f"Failed to reload {cog_name}: {e}")
