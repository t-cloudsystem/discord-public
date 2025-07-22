from logging import getLogger, StreamHandler, DEBUG, INFO
import asyncio

from discord import Embed, app_commands
import discord
from discord.ext import commands


logger = getLogger(__name__)
handler = StreamHandler()
handler.setLevel(DEBUG)
logger.setLevel(INFO)
logger.addHandler(handler)
logger.propagate = False


self_deletable_message_users = {
    (302050872383242240, "bump"),  # DISBOARDのbump
    (761562078095867916, "up")   # ディス速のup
}


class DeleteMessageCog(commands.Cog):
    """自動メッセージを削除するCog"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _is_deletable(self, channel: discord.abc.MessageableChannel, message: discord.Message, payload: discord.RawReactionActionEvent) -> bool:
        """メッセージが削除可能か確認する

        Args:
            payload (discord.RawReactionActionEvent): on_raw_reaction_addのペイロード
        """

        if (
            [reaction for reaction in message.reactions if reaction.emoji == "🗑️"][0].me and
            message.interaction and payload.user_id == message.interaction.user.id
        ):
            return True

        sent_by_me = self.bot.user.id == message.author.id
        if sent_by_me and message.embeds[0].footer.text != "🗑️リアクションで削除":
            logger.debug("削除対象外の埋め込み")
            return False

        try:
            ref_message = await channel.fetch_message(message.reference.message_id)
        except discord.errors.NotFound:
            logger.debug("元メッセージが見つからないため誰でも削除可能")
            return True

        if ref_message.author.id == payload.user_id:
            return True

        return False

    @commands.Cog.listener()
    async def on_app_command_completion(self, interaction: discord.Interaction, command: app_commands.Command | app_commands.ContextMenu):
        while interaction.response.is_done():
            await asyncio.sleep(0.1)

        if (interaction.application_id, command.name) in self_deletable_message_users:
            # 削除可能とする
            await interaction.message.add_reaction("🗑️")
            logger.info(f"削除可能通知のリアクション付与完了 {interaction.id}")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        logger.debug(f"リアクション追加 {payload.emoji.name}")
        if payload.emoji.name != "🗑️":
            return

        channel = self.bot.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)

        if await self._is_deletable(channel, message, payload):
            await message.delete()
            logger.info(f"埋め込みを削除しました {message.id}")


async def setup(bot: commands.Bot):
    """Cogのセットアップ関数"""
    await bot.add_cog(DeleteMessageCog(bot))
    logger.info("DeleteMessageCog セットアップ完了")
