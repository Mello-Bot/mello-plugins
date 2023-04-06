from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mello.utils.plugins.context import DecoratorContext
    from mello.utils.plugins.channels import ContextChannel
    from mello.utils.plugins.user import ContextUser

from mello.utils.plugins import DecoratorPlugin

plugin = DecoratorPlugin("home", "Home", "Set a channel where the bot returns if left alone", ["nico9889"])


def home(ctx: DecoratorContext):
    try:
        channel = ctx.instance_storage["channel"]
        ctx.channels[channel].join()
    except KeyError:
        pass


@plugin.state
def create_state():
    return {
        "last_channel": None
    }


@plugin.on_user_leaved
def _on_user_leaved(ctx: DecoratorContext):
    channel = ctx.me.current_channel()
    if channel and ctx.instance_storage.get("enabled") and not channel.users():
        home(ctx)


@plugin.on_user_moved
def _on_user_moved(ctx: DecoratorContext, channel: ContextChannel, actor: ContextUser):
    _on_user_leaved(ctx)
    if ctx.user == ctx.me and actor != ctx.me:
        if actor.current_channel() == channel:
            ctx.state["last_channel"] = channel
            ctx.message.bold("What's up? (•ิ_•ิ)?").reply_to_channel()
        else:
            last_channel = ctx.state["last_channel"]
            if last_channel and len(last_channel.users()) > 0:
                ctx.message.bold("Bye! ヾ(・ω・*)").send_to_channel(last_channel)


@plugin.on_load
def _on_load(ctx: DecoratorContext):
    home(ctx)
    channel = ctx.instance_storage.get("channel")
    if channel:
        ctx.shared_storage["channel"] = channel
    if "enabled" not in ctx.instance_storage:
        ctx.instance_storage["enabled"] = False


@plugin.command("sethome", "Set the channel where the bot returns")
def _set_home(ctx: DecoratorContext, _: str):
    channel = ctx.user.current_channel()
    ctx.instance_storage["channel"] = channel.id()
    ctx.shared_storage["channel"] = channel.id()
    ctx.message.text("Setted ").bold(channel.name()).text(" as home").reply_to_channel()


@plugin.command("home", "Enable/disable auto homing")
def _home(ctx: DecoratorContext, message: str):
    if message == "on":
        enabled = True
    elif message == "off":
        enabled = False
    else:
        enabled = not ctx.instance_storage["enabled"]
    ctx.instance_storage["enabled"] = enabled
    if enabled:
        m = ctx.message.bold("Enabled")
    else:
        m = ctx.message.bold("Disabled")
    m.text(" auto home").reply_to_channel()


@plugin.command("come", "Join to the user channel")
def _come(ctx: DecoratorContext, _: str):
    ctx.user.current_channel().join()
    ctx.message.text("Here I am (´• ω •`)").reply_to_channel()
