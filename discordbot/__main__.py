import datetime
import random
import os
from logging import getLogger, StreamHandler, DEBUG

from dotenv import load_dotenv
from discord.ext import commands, tasks
import discord

from discordbot.scratch_info import get_scratch_info
from discordbot.daily_projects import DailyProjects
from discordbot.templates import EmbedTemplates, EmojiTemplates
from discordbot.scratch_auth import ChooseMethodView, ScratchAuth


load_dotenv(verbose=True)
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path)

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


class csAuthStartView(discord.ui.View):
    def __init__(self, scratch_auth: ScratchAuth, bot: commands.Bot, timeout=None):
        self.scratch_auth = scratch_auth
        self.bot = bot
        super().__init__(timeout=timeout)

    @discord.ui.button(label="はじめる", custom_id="startauth", style=discord.ButtonStyle.primary)
    async def start(self, interaction: discord.Interaction, button: discord.Button) -> None:
        if discord.utils.get(interaction.user.roles, name="CSuser") is not None:
            embed = discord.Embed(title="ユーザー認証", description="あなたはすでに認証が完了しているようです。", color=0x43b581)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(embed=discord.Embed(title="ユーザー認証", description="認証方法を選択してください！", color=0x4459fe),
                                                    view=ChooseMethodView(self.scratch_auth, EmojiTemplates(self.bot)), ephemeral=True)


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

        self.scratch_auth = ScratchAuth()

        # runの後に定義しなければいけないものたち
        self.auth_view = None
        self.apply_view = None
        self.daily_projects = None

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

        @self.tree.command(name="cs_auth", description="ユーザー認証のテンプレートを表示します。")
        @self._command_limit(only_cloudserver=True)
        async def auth_command(interaction: discord.Interaction):
            embed = discord.Embed(title="ユーザー認証", description="下のボタンを押して、☁システムとの連携を始めましょう！", color=0x4459fe)
            if self._command_is_cs_admin(interaction):
                await interaction.channel.send(embed=embed, view=self.auth_view)
                await interaction.response.send_message("↓送信が完了しました", ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, view=self.auth_view, ephemeral=True)

        @self.tree.command(name="cs_apply", description="管理者応募のテンプレートを表示します。")
        @self._command_limit(only_cloudserver=True)
        async def apply_command(interaction: discord.Interaction):
            embed = discord.Embed(title="管理者応募", description="下のボタンを押して、管理者への応募を始めましょう！", color=0x558aff)
            if self._command_is_cs_admin(interaction):
                await interaction.channel.send(embed=embed, view=self.apply_view)
                await interaction.response.send_message("↓送信が完了しました", ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, view=self.apply_view, ephemeral=True)

        @self.tree.command(name="admin_make_threads", description="スレッドを作成します。")
        @self._command_limit(only_admin=True, only_cloudserver=True)
        async def make_threads(interaction: discord.Interaction):
            """テスト用"""

            channel = self.bot.get_channel(1258771478959226980)
            thread = await channel.create_thread(name="応募内容2", reason="テスト")
            link = thread.mention
            await thread.send(f"スレッドが開始されました\n ||{interaction.user.mention} {self.cs_guild.get_role(int(os.environ.get('DISCORD_CS_ADMINROLE'))).mention}||")
            await interaction.response.send_message(f"{link} こちらで会話してください", ephemeral=True)

        @self.tree.command(name="admin_decide_daily_project", description="手動で今日の作品を選出します。")
        @self._command_limit(only_admin=True, only_cloudserver=True)
        async def decide_daily_project(interaction: discord.Interaction):
            await interaction.response.defer()
            await self.daily_projects.decide_daily_project(mention=False)
            await interaction.followup.send("選出が完了しました", ephemeral=True)

        @self.tree.command(name="scratch_fetch", description="Scratchのプロジェクト・ユーザー・スタジオの情報を取得して表示します。")
        @discord.app_commands.describe(
            text="ScratchのURLを含むテキスト",
            ephemeral="非公開で作成するか (Trueで非公開)"
        )
        async def scratch_embed(interaction: discord.Interaction, text: str, ephemeral: bool = False):
            await interaction.response.defer(ephemeral=ephemeral)

            app_info = await self.bot.application_info()
            data = await get_scratch_info(text, app_info.icon.url)
            if data:
                await interaction.followup.send(embeds=[scratch_info.get_embed() for scratch_info in data])
            else:
                await interaction.followup.send(embed=EmbedTemplates.scratch_no_found)

    def _command_limit(self, only_admin=False, only_cloudserver=False, allow_dm=True):
        def decorator(f):
            async def wrapper(interaction: discord.Interaction):
                if only_admin and not self._command_is_cs_admin(interaction):
                    await interaction.response.send_message(embed=EmbedTemplates.no_permission, ephemeral=True)
                    return

                if not allow_dm and interaction.guild is None:
                    await interaction.response.send_message(embed=EmbedTemplates.dm, ephemeral=True)
                    return

                if only_cloudserver and interaction.guild is not None and interaction.guild.id != self.discord_cs_server_id:
                    await interaction.response.send_message(embed=EmbedTemplates.outside_cs, ephemeral=True)
                    return
                return await f(interaction)
            return wrapper
        return decorator

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
        await self.tree.sync()

        self.auth_view = csAuthStartView(self.scratch_auth, self.bot)
        self.bot.add_view(self.auth_view)
        # self.apply_view = csApplyStartView(self.cs_server)
        # self.bot.add_view(self.apply_view)
        self.daily_projects = DailyProjects(self.bot)

        self.scratch_auth.init_with_bot(self.bot)

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

        if "<embed_skip>" not in message.content:
            app_info = await self.bot.application_info()
            data = await get_scratch_info(message.content, app_info.icon.url)
            if data:
                await message.reply(embeds=[scratch_info.get_embed() for scratch_info in data], mention_author=False)

    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        logger.debug(f"リアクション追加 {payload.emoji.name}")
        if payload.emoji.name == "🗑️":
            await self._delete_info(payload)


if __name__ == "__main__":
    public_bot = csPublicBot()
    public_bot.bot.run(os.environ.get("DISCORD_TOKEN_CSPUBLIC"))
