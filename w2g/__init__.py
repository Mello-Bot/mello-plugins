from __future__ import annotations

from typing import TYPE_CHECKING

from mello.utils.plugins.message import Colors, Color as MColor

if TYPE_CHECKING:
    from mello.utils.plugins.context import Context
    from mello.utils.plugins.channels import ContextChannel
    from mello.utils.plugins.user import ContextUser
    from typing import Dict

from mello.utils.plugins import Plugin, Command
from mello.utils.plugins.callbacks import Callback
from mello.utils.plugins.web.options.string_option import StringOption
import requests

HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json"
}


class WatchTogether(Plugin):
    def __init__(self):
        super().__init__("w2g", "Watch Together", "Permits you to create a watch together session from the chat", ["nico9889"])
        self.channel_room: dict[str, str] = {}
        self.user_channel: dict[str, str] = {}
        self.api_token_option = None
        self.add_command(Token(self))
        self.add_command(Color(self))
        self.add_command(Create(self))
        self.add_command(Update(self))
        self.add_command(AddPlaylist(self))
        self.set_callback(Callback.OnUserMoved, self.on_user_moved)
        self.set_callback(Callback.OnUserLeaveServer, self.on_user_leaved)

    def on_load(self, ctx: Context):
        self.api_token_option = ApiTokenOption(self)
        self.api_token_option.on_change = lambda value: setattr(self, "api_token_option", value) or True
        self.options.add(self.api_token_option)

    @property
    def api_token(self):
        return self.instance_storage.get("api_token")

    @api_token.setter
    def api_token(self, value: str):
        self.instance_storage["api_token"] = value

    @property
    def colors(self) -> Dict[str, str]:
        return self.instance_storage.get("colors") or {}

    @colors.setter
    def colors(self, colors: Dict[str, str]):
        self.instance_storage["colors"] = colors

    def on_user_leaved(self, ctx: Context):
        if ctx.user.id() in self.user_channel:
            channel = self.user_channel.pop(ctx.user.id())
            del self.channel_room[channel]

    def on_user_moved(self, ctx: Context, channel: ContextChannel, actor: ContextUser):
        if ctx.user.id() in self.user_channel:
            c = self.user_channel.pop(ctx.user.id())
            room = self.channel_room.pop(c)
            self.channel_room[channel.id()] = room
            self.user_channel[ctx.user.id()] = channel.id()
            message = ctx.message.bold("W2G: ").text(f"Room {room} is now tied to ").bold(channel.name())
            message.send_to_channel(ctx.user.current_channel())
            message.send_to_channel(channel)


class ApiTokenOption(StringOption):
    def __init__(self, p: WatchTogether):
        super().__init__("WatchTogether API Token",
                         "Set here you personal W2G API Token. Check W2G docs for more details", p.api_token)
        self.plugin = p

    def on_change(self, value: str) -> bool:
        if not value.isalnum():
            return False
        self.plugin.api_token = value
        return True


class Token(Command):
    def __init__(self, p: WatchTogether):
        super().__init__("token", "Set your W2G API Token")
        self.plugin = p

    def execute(self, ctx: Context, message: str):
        if not message.isalnum():
            return ctx.message.text("W2G Token contains invalid characters").reply_to_user()
        self.plugin.api_token = message
        ctx.message.text("W2G Token saved correctly").reply_to_user()


class Create(Command):
    def __init__(self, p: WatchTogether):
        super().__init__("create", "Create a WatchTogether room with a specified video")
        self.plugin = p

    def execute(self, ctx: Context, message: str):
        token = self.plugin.api_token
        if not self.plugin.api_token:
            return ctx.message.text(
                "Missing W2G API Token. Please use !token <token> to set an API token", color=Colors.RED) \
                .reply_to_channel()
        color = self.plugin.colors[ctx.user.id()] if ctx.user.id() in self.plugin.colors else "#6f6f6f"
        res = requests.post("https://api.w2g.tv/rooms/create.json", headers=HEADERS, json={
            "w2g_api_key": token,
            "share": message,
            "bg_color": color,
            "bg_opacity": "100"
        })
        if not res.ok:
            return ctx.message.text("Failed to create room", color=Colors.RED).reply_to_channel()
        data = res.json()
        if "streamkey" not in data:
            return ctx.message.text("W2G returned an invalid response", color=Colors.RED).reply_to_channel()

        ctx.message.text(ctx.user.name()).text(" created a new ") \
            .hypertext("room", f"https://w2g.tv/rooms/{data['streamkey']}") \
            .text("!").reply_to_channel()
        self.plugin.channel_room[ctx.user.current_channel().id()] = data['streamkey']
        self.plugin.user_channel[ctx.user.id()] = ctx.user.current_channel().id()


class Update(Command):
    def __init__(self, p: WatchTogether):
        super().__init__("update", "Update the video in the room tied to this channel")
        self.plugin = p

    def execute(self, ctx: Context, message: str):
        room = self.plugin.channel_room.get(ctx.user.current_channel().id())
        if not room:
            return ctx.message.text("No room has been created in this channel", color=Colors.RED).reply_to_user()
        res = requests.post(f"https://api.w2g.tv/rooms/{room}/sync_update", headers=HEADERS, json={
            "w2g_api_key": self.plugin.api_token,
            "item_url": message
        })
        if not res.ok:
            return ctx.message.text("Failed to update the room", color=Colors.RED).reply_to_channel()
        ctx.message.text(ctx.user.name()).text(" changed the video to ").text(message).reply_to_channel()


class AddPlaylist(Command):
    def __init__(self, p: WatchTogether):
        super().__init__("addplaylist",
                         "Add one or more video to the current room. Format: !addplaylist <URL> ... <URL>")
        self.plugin = p

    def execute(self, ctx: Context, message: str):
        chunks = message.split(" ")
        videos = []
        for num, chunk in enumerate(chunks):
            video = {
                "url": chunk,
                "title": num
            }
            videos.append(video)
        room = self.plugin.channel_room.get(ctx.user.current_channel().id())
        if not room:
            return ctx.message.text("No room has been created in this channel", color=Colors.RED).reply_to_user()
        res = requests.post(f"https://api.w2g.tv/rooms/{room}/playlists/current/playlist_items/sync_update",
                            headers=HEADERS,
                            json={
                                "w2g_api_key": self.plugin.api_token,
                                "add_items": videos
                            })
        if not res.ok:
            return ctx.message.text("Failed to update the room", color=Colors.RED).reply_to_channel()
        _list = ctx.message.text(ctx.user.name()).text(" added the following videos to the room: ").list()
        for chunk in chunks:
            _list = _list.add(chunk)
        _list.close().reply_to_channel()


class Color(Command):
    def __init__(self, p: WatchTogether):
        super().__init__("color",
                         "Set your favourite color. Will be used as W2G Room background color. Use the Hex Format 0f0f0f")
        self.plugin = p

    def execute(self, ctx: Context, message: str):
        if message.startswith("#"):
            message = message[1:]
        if not message.isascii():
            return ctx.message.text("Invalid color code. It must contains only Hex symbols",
                                    color=Colors.RED).reply_to_user()
        if len(message) != 6:
            return ctx.message.text("Color must be express in 6 hex digit format. Example: 0f0f0f or #0f0f0f",
                                    color=Colors.RED).reply_to_user()
        try:
            r, g, b = int(message[0:2], 16), int(message[2:4], 16), int(message[4:6], 16)
        except ValueError:
            return ctx.message.text("Color must be express in 6 hex digit format. Example: 0f0f0f or #0f0f0f",
                                    color=Colors.RED).reply_to_user()
        colors = self.plugin.colors
        colors[ctx.user.id()] = f"#{message}"
        self.plugin.colors = colors
        ctx.message.bold("New color set!", color=MColor(r, g, b)).reply_to_user()


plugin = WatchTogether
