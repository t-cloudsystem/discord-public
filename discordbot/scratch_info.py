import re
from logging import getLogger, StreamHandler, DEBUG, INFO
from typing import Literal
import asyncio

from discord import Embed
import scapi


logger = getLogger(__name__)
handler = StreamHandler()
handler.setLevel(DEBUG)
logger.setLevel(INFO)
logger.addHandler(handler)
logger.propagate = False


class ScratchInfo:
    def __init__(self, url: str = None, type: Literal["projects", "users", "studios"] = None, id: str = None,
                 bot_icon_url: str = "https://api.takechi.cloud/src/icon/takechi_v2.1.png") -> None:
        """ScratchのURLから情報を取得します

        Args:
            url (str, optional): Scratchのプロジェクト、ユーザー、スタジオのいずれかのURL。url、またはtypeとidのどちらかが必須。
            type (Literal[&quot;projects&quot;, &quot;users&quot;, &quot;studios&quot;], optional): IDのタイプ。idの指定が必要。
            id (str, optional): プロジェクト、スタジオのIDまたはユーザー名。typeの指定が必要。
            bot_icon_url (str, optional): 埋め込みのフッターに表示するアイコンのURL。デフォルトはtakechiのアイコン。

        Raises:
            ValueError: 引数不足の場合
            ValueError: ScratchのURLではない場合
        """
        if not (url or (type and id)):
            raise ValueError("URL、またはtypeとidのどちらかを指定してください")

        if url:
            self.url = url

            scratch_pattern = r"(https?://scratch\.mit\.edu/)(projects|users|studios)/([a-zA-Z0-9\-_]+)/*"
            match = re.search(scratch_pattern, self.url)
            logger.debug(f"URL検出結果: {str(match)}")
            if not match:
                logger.debug(f"URL検出失敗 {self.url}")
                raise ValueError(f"{self.url}はScratchのURLではありません")

            self.type = match.group(2)
            self.id = match.group(3)
            logger.debug(f"検出成功 タイプ: {self.type} ID: {self.id}")
        else:
            self.type = type
            self.id = id

            if self.type not in ["projects", "users", "studios"]:
                raise ValueError(f"タイプ {self.type} は無効です")

            if self.type == "projects":
                self.url = f"https://scratch.mit.edu/projects/{self.id}/"
            elif self.type == "users":
                self.url = f"https://scratch.mit.edu/users/{self.id}/"
            elif self.type == "studios":
                self.url = f"https://scratch.mit.edu/studios/{self.id}/"

        self.bot_icon_url = bot_icon_url
        # await self._get_info()

    async def _get_info(self) -> None:
        if self.type == "projects":
            self.data = await scapi.get_project(self.id)
            if not isinstance(self.data, scapi.Project):
                raise ValueError(f"プロジェクト {self.id} が見つかりません")
            self.author: scapi.User = self.data.author
        elif self.type == "users":
            self.data = await scapi.get_user(self.id)
            self.author: scapi.User = self.data
        elif self.type == "studios":
            self.data = await scapi.get_studio(self.id)
            self.author: scapi.User = self.data.author

    def get_embed(self, can_delete: bool = True) -> Embed:
        """情報からEmbedを生成します

        Returns:
            Embed: Discordで送信できるEmbedオブジェクト
        """
        embed = Embed(color=0xf8a936, url=self.url)
        if self.type == "projects":
            embed.title = self.data.title
            description = self.data.instructions
            embed.set_image(url=f"https://uploads.scratch.mit.edu/get_image/project/{self.id}_360x270.png")
        elif self.type == "users":
            embed.title = self.data.username
            description = self.data.about_me
            embed.set_image(url=self.data.icon_url)
        elif self.type == "studios":
            embed.title = self.data.title
            description = self.data.description
            embed.set_image(url=f"https://uploads.scratch.mit.edu/get_image/gallery/{self.id}_510x300.png")

        if len(description) > 80:
            embed.description = description[:80] + "..."
        else:
            embed.description = description

        embed.set_author(name=self.author.username, url=f"https://scratch.mit.edu/users/{self.author.username}/", icon_url=self.author.icon_url)

        if can_delete:
            embed.set_footer(text="🗑️リアクションで削除", icon_url=self.bot_icon_url)

        return embed


async def get_scratch_info(text: str, bot_icon_url: str = None) -> list[ScratchInfo]:
    scratch_pattern = r"https?://scratch\.mit\.edu/(projects|users|studios)/[a-zA-Z0-9\-_]+/*"
    m = re.finditer(scratch_pattern, text)
    data = []
    for match in m:
        try:
            info = ScratchInfo(text[match.start():match.end()], bot_icon_url=bot_icon_url)
            await info._get_info()
            data.append(info)
        except ValueError:
            logger.debug("情報取得失敗")
    return data


if __name__ == "__main__":
    message = "たーけクラウドシステムがサービス再開するらしいよ https://scratch.mit.edu/projects/870204802/"
    data = asyncio.run(get_scratch_info(message))

    for scratch_info in data:
        try:
            print(scratch_info.url)
            print(scratch_info.get_embed())
        except ValueError:
            print("情報取得失敗")
