import os
import functools

from discord import Embed
from discord.ext.commands import Bot
import discord


try:
    discord_cs_server_id = int(os.environ["DISCORD_CS_SERVERID"])
except (KeyError, ValueError):
    raise ValueError("環境変数 DISCORD_CS_SERVERID が設定されていません。")


class EmbedTemplates:
    outside_cs = Embed(title="エラー", description="このコマンドは公式サーバーでのみ利用可能です。", color=0xf6a408)
    no_permission = Embed(title="エラー", description="このコマンドを実行する権限がありません。", color=0xf6a408)
    dm = Embed(title="エラー", description="このコマンドはDMでは実行できません。", color=0xf6a408)
    scratch_no_found = Embed(title="エラー", description="テキストからScratchのURLを見つけられませんでした。", color=0xf6a408)


class EmojiTemplates:
    def __init__(self, bot: Bot):
        self.auth_cloud = bot.get_emoji(1331105602956689562)
        self.auth_comment = bot.get_emoji(1331105606215536710)
        self.auth_profile_comment = bot.get_emoji(1331105604646998026)


def _command_is_cs_admin(interaction: discord.Interaction):
    return (interaction.guild is not None and
            interaction.guild.id == discord_cs_server_id and
            discord.utils.get(interaction.user.roles, name="admin")
            )


def limit_command(only_admin=False, only_cloudserver=False, allow_dm=True):
    def decorator(f):
        @functools.wraps(f)
        async def wrapper(*args, **kwargs):
            # 位置引数の中からinteractionを取得
            interaction = [arg for arg in args if isinstance(arg, discord.Interaction)][0]

            # もしなければキーワード引数から取得
            if interaction is None:
                interaction = kwargs.get('interaction')

            if only_admin and not _command_is_cs_admin(interaction):
                await interaction.response.send_message(embed=EmbedTemplates.no_permission, ephemeral=True)
                return

            if not allow_dm and interaction.guild is None:
                await interaction.response.send_message(embed=EmbedTemplates.dm, ephemeral=True)
                return

            if only_cloudserver and interaction.guild is not None and interaction.guild.id != discord_cs_server_id:
                await interaction.response.send_message(embed=EmbedTemplates.outside_cs, ephemeral=True)
                return
            return await f(*args, **kwargs)

        return wrapper
    return decorator


if __name__ == "__main__":
    print(EmbedTemplates.embed_outside)
    print(EmbedTemplates.embed_no_permission)
    print(EmbedTemplates.embed_dm)
