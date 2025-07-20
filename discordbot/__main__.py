import datetime
import random
import os
from logging import getLogger, StreamHandler, DEBUG
import asyncio

from dotenv import load_dotenv
from discord.ext import commands, tasks
import discord

load_dotenv(verbose=True)
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path)

from discordbot.templates import limit_command  # noqa: E402

logger = getLogger(__name__)
handler = StreamHandler()
handler.setLevel(DEBUG)
logger.setLevel(DEBUG)
logger.addHandler(handler)
logger.propagate = False

intents = discord.Intents.default()
intents.members = True
intents.message_content = True


class RandomStatusTask(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.change_status.start()

    def cog_unload(self):
        self.change_status.cancel()

    @tasks.loop(seconds=5.0)
    async def change_status(self):
        try:
            text = "".join([random.choice(["ク", "ラ", "ウ", "ド"]) for _ in range(4)])
            await self.bot.change_presence(status=discord.Status.online, activity=discord.Game(text + "システム"))
        except Exception as e:
            logger.error(f"ステータス変更中にエラーが発生しました {e}")


class csApplyStartView(discord.ui.View):
    def __init__(self, cs_server, timeout=None):
        super().__init__(timeout=timeout)
        self.cs_server = cs_server

    @discord.ui.button(label="はじめる", custom_id="startapply", style=discord.ButtonStyle.primary)
    async def start(self, interaction: discord.Interaction, button: discord.Button) -> None:
        await interaction.response.send_message("DMに内容を送信したので、ご確認ください！", ephemeral=True)

        if discord.utils.get(interaction.user.roles, name="CSuser") is None:
            embed = discord.Embed(title="管理者応募", description="あなたはまだユーザー認証が完了していないようです。", color=0xf04747)
            await interaction.user.send(embed=embed)
            return

        # user = await self.cs_server.get_userinfo(interaction.user.id)

        authcode = 12345  # await discord_auth.issue_authcode(self.username.value, interaction.user.id)
        embed = discord.Embed(title="管理者応募", description=f"応募ありがとうございます！\n[専用応募フォーム](https://docs.google.com/forms/d/e/1FAIpQLSemE_oSBe5p0ipVvyku4XDjFl5yZafyHdFhdXbrpBMZoAD-EA/viewform?usp=pp_url&entry.545537387={authcode})で必要事項を入力してください。\n認証コード\n```\n{authcode}\n```", color=0x558aff)
        await interaction.user.send(content=str(authcode), embed=embed)


class csPublicBot:
    def __init__(self, cs_server=None):
        self.bot = commands.Bot(
            command_prefix="c!",
            case_insensitive=True,
            help_command=None,
            intents=intents
        )
        self.tree = self.bot.tree

        if cs_server:
            self.cs_server = cs_server

        if "DISCORD_CS_SERVERID" in os.environ:
            self.discord_cs_server_id = int(os.environ.get("DISCORD_CS_SERVERID"))
        else:
            raise ValueError("環境変数が設定されていません")

        # runの後に定義しなければいけないものたち
        self.apply_view = None

        self._register_decorator()

        self.embed_outside = discord.Embed(title="エラー", description="このコマンドは公式サーバーでのみ利用可能です。", color=0xf6a408)

    def _command_is_cs_admin(self, interaction: discord.Interaction):
        return (interaction.guild is not None and
                interaction.guild.id == self.discord_cs_server_id and
                discord.utils.get(interaction.user.roles, name="admin")
                )

    def _register_decorator(self):
        """クラスで定義されたコマンドを登録
        """

        # デコレーターを利用せずにイベントを登録
        self.on_ready = self.bot.event(self.on_ready)
        self.on_message = self.bot.event(self.on_message)
        self.on_raw_reaction_add = self.bot.event(self.on_raw_reaction_add)

        @self.tree.command(name="cs_apply", description="管理者応募のテンプレートを表示します。")
        @limit_command(only_cloudserver=True)
        async def apply_command(interaction: discord.Interaction):
            embed = discord.Embed(title="管理者応募", description="下のボタンを押して、管理者への応募を始めましょう！", color=0x558aff)
            if self._command_is_cs_admin(interaction):
                await interaction.channel.send(embed=embed, view=self.apply_view)
                await interaction.response.send_message("↓送信が完了しました", ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, view=self.apply_view, ephemeral=True)

    async def _delete_info(self, payload: discord.RawReactionActionEvent):
        """作成した情報の埋め込みを削除

        Args:
            payload (discord.RawReactionActionEvent): on_raw_reaction_addのペイロード
        """
        channel = self.bot.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)

        sent_by_me = self.bot.user.id == message.author.id
        if sent_by_me and message.embeds[0].footer.text != "🗑️リアクションで削除":
            logger.debug("削除対象外の埋め込み")
            return

        try:
            ref_message = await channel.fetch_message(message.reference.message_id)
        except discord.errors.NotFound:
            logger.debug("元メッセージが見つからないため誰でも削除可能")
            ref_message = None

        if not ref_message or ref_message.author.id == payload.user_id:
            await message.delete()
            logger.info(f"埋め込みを削除しました {message.id}")

    async def on_ready(self):
        synced_commands = await self.bot.tree.sync()
        logger.debug([f"{command.name}: {command.options}" for command in synced_commands])

        # self.apply_view = csApplyStartView(self.cs_server)
        # self.bot.add_view(self.apply_view)

        channel = self.bot.get_channel(int(os.environ.get("DISCORD_CS_CHANNELID")))
        if channel:
            await channel.send(f"パブリックサーバーが再起動されました 現在時刻:{datetime.datetime.now()}")
        else:
            logger.warning("チャンネルIDが見つかりません")

        RandomStatusTask(self.bot)
        logger.info("Botの準備ができました！")

    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if message.guild is None:
            await message.reply(content="メッセージありがとうございます！こちらでのお問い合わせにはお答えできませんのでご了承ください。\n[お問い合わせチャンネル](https://discord.com/channels/1210843458932178994/1256881718766469131)のご利用をお願いします。")
            return

    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        logger.debug(f"リアクション追加 {payload.emoji.name}")
        if payload.emoji.name == "🗑️":
            await self._delete_info(payload)


async def load_extension(public_bot: csPublicBot):
    for cog in os.listdir("discordbot/cogs"):
        if cog.endswith(".py"):
            await public_bot.bot.load_extension(f"discordbot.cogs.{cog[:-3]}")


if __name__ == "__main__":
    public_bot = csPublicBot()
    asyncio.run(load_extension(public_bot))
    public_bot.bot.run(os.environ.get("DISCORD_TOKEN_CSPUBLIC"))
