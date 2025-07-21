import os
import datetime
from logging import getLogger, StreamHandler, DEBUG
import random
import time

from discord.ext import commands, tasks
from discord import app_commands, Interaction
import requests
import scapi

from discordbot.cogs.scratch_info import ScratchInfo
from ..templates import limit_command


logger = getLogger(__name__)
handler = StreamHandler()
handler.setLevel(DEBUG)
logger.setLevel(DEBUG)
logger.addHandler(handler)
logger.propagate = False


JST = datetime.timezone(datetime.timedelta(hours=9))

# 宣伝をする時刻
start_times = [
    datetime.time(hour=7, minute=0, tzinfo=JST),
]


class DailyProjects(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot: commands.Bot = bot
        self.studio_id = os.environ.get("SCRATCH_DAILY_PROJECTS_STUDIO_ID")
        self.api_url = os.environ.get("SCRATCH_DAILY_HISTORY_API_URL")
        self.api_pass = os.environ.get("SCRATCH_DAILY_HISTORY_API_PASS")
        self.channel_id = os.environ.get("SCRATCH_DAILY_CHANNELID")

        if not all([self.studio_id, self.api_url, self.api_pass, self.channel_id]):
            raise ValueError("環境変数を正しく設定してください。")

        self.max_applies = 20

        # self.bot.tree.add_command(self.decide_command)
        self.run.start()

    def cog_unload(self):
        self.run.cancel()

    @tasks.loop(time=start_times)
    async def run(self):
        await self.decide_daily_project()

    async def decide_daily_project(self, mention: bool = True):
        studio: scapi.Studio = await scapi.get_studio(self.studio_id)
        await studio.update()

        past_res = requests.get(self.api_url)
        if not past_res.headers["Content-Type"].startswith("application/json") or past_res.json()["code"] != 200:
            logger.error("API側でエラーが発生しました")
            logger.debug(past_res.text)
            return

        past_projects = set(int(data["id"]) for data in past_res.json()["data"])
        applies = {}

        projects_candidate: list[scapi.Project] = []
        projects_weight = []

        # projectsは新しい順に返される
        async for project in studio.projects(limit=studio.project_count):
            try:
                if project.get_remixtree().moderation_status == "notsafe":
                    continue
            except scapi.exception.ObjectNotFound:
                # 一応そのまま流す
                logger.warning(f"ステータス取得失敗 {project.id}")

            if project.author not in applies:
                applies[project.author] = 0

            # すでに掲載済みのものと合わせてカウント
            if applies[project.author] > self.max_applies:
                continue

            applies[project.author] += 1

            if project.id in past_projects:
                continue

            projects_candidate.append(project)
            projects_weight.append(1)

        if not projects_candidate:
            logger.info("対象作品なし")
            last_sent = max(int(data["timestamp"]) for data in past_res.json()["data"])
            if time.time() - last_sent > 24 * 60 * 60 + 300:
                logger.info("繰り返しのメッセージはなし")
                return

            channel = self.bot.get_channel(int(self.channel_id))
            text = f"選択できる作品がありませんでした。\n[エントリースタジオ](https://scratch.mit.edu/studios/{self.studio_id}/)で作品を追加しましょう！"
            message = await channel.send(text)
            logger.info(f"メッセージ送信完了: {message.id}")
            return

        logger.debug(f"選択肢: {[str(x) for x in projects_candidate]}")
        logger.debug(f"重み: {projects_weight}")

        choiced_project = random.choices(projects_candidate, k=1, weights=projects_weight)[0]
        logger.info(f"選ばれた作品: {choiced_project.title}")

        text = f"## 今日の作品\nhttps://scratch.mit.edu/projects/{choiced_project.id}/"
        if mention:
            text += "\n|| <@&1324929451175313438> ||"
        scratch_info = ScratchInfo(type="projects", id=choiced_project.id)
        await scratch_info._get_info()

        channel = self.bot.get_channel(int(self.channel_id))
        message = await channel.send(content=text, embed=scratch_info.get_embed(can_delete=False))
        await message.add_reaction(self.bot.get_emoji(1324552402250236005))  # :scratch_love:
        await message.add_reaction(self.bot.get_emoji(1324552400022798416))  # :scratch_favorite:
        logger.debug(f"メッセージを送信しました: {message.id}")

        TODAY = datetime.datetime.now(JST).strftime("%Y/%m/%d")
        await message.create_thread(name=TODAY+" 作品", reason=f"今日の作品(自動作成) {TODAY}")
        logger.debug("スレッドを作成しました")

        requests.post(self.api_url, json={
            "id": choiced_project.id,
            "title": choiced_project.title,
            "pass": self.api_pass
        })

    @app_commands.command(name="admin_decide_daily_project", description="手動で今日の作品を選出します。")
    @limit_command(only_admin=True, only_cloudserver=True)
    async def decide_command(self, interaction: Interaction):
        await interaction.response.defer()
        await self.decide_daily_project(mention=False)
        await interaction.followup.send("選出が完了しました", ephemeral=True)

    @commands.Cog.listener()
    async def on_ready(self):
        pass
        # await self.bot.tree.sync()


async def setup(bot: commands.Bot):
    """Cogをセットアップする関数"""
    await bot.add_cog(DailyProjects(bot))
    logger.info("DailyProjects セットアップ完了")
