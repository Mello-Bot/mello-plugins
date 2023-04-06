from __future__ import annotations

from typing import TYPE_CHECKING

from mello.utils.plugins import DecoratorPlugin
from mello.utils.plugins.message import MessageType

if TYPE_CHECKING:
    from mello.utils.plugins.context import Context

plugin = DecoratorPlugin("base", "Base", "Base plugin supplied with the bot :D", ["nico9889"])


# This is a placeholder, it's useful to describe internal command
@plugin.command("register", "Register the current user to the platform")
def register(_: Context, __: str):
    pass


@plugin.command("web", "Send a link to login to the web control panel")
def web(ctx: Context, _: str):
    ctx.user.login()


@plugin.command("ping", "Answer with pong!")
def ping(ctx: Context, _: str):
    ctx.message.text("!pong").reply_to_user()


@plugin.command("users", "Send a list of online users")
def users(ctx: Context, _: str):
    m = ctx.message.text("Online users:")
    li = m.list()
    for user in ctx.users.values():
        li.add(user.name())
    m = li.close()
    m.reply_to_channel()


@plugin.on_message
def on_message(ctx: Context, msg: str, _type: MessageType):
    if msg == "test":
        ctx.message.text("Toast!").reply_to_channel()
