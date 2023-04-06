from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mello.utils.plugins.context import Context
    from mello.utils.plugins.channels import ContextChannel
    from mello.utils.plugins.user import ContextUser

from mello.utils.plugins import Plugin, Command
from mello.utils.plugins.callbacks import Callback
from mello.utils.plugins.message import Colors


def check_empty(ctx: Context, parent: ContextChannel, name: str):
    empty = False
    children = parent.children()
    for channel in children:
        empty = empty or (len(channel.users()) == 0)
    if empty:
        return
    ctx.channels.new(f"{name} #{len(children) + 1}", parent)


def clear_empty(channel: ContextChannel):
    children = channel.children()
    if len(children) <= 1:
        return
    for child in channel.children()[1:]:
        if len(child.users()) == 0:
            child.delete()


class AutoChannel(Plugin):
    def __init__(self):
        super().__init__("autochannel", "AutoChannel", "Create channels automagically", ["nico9889"])
        self.add_command(ApplyMagic(self))
        self.add_command(RemoveMagic(self))
        self.set_callback(Callback.OnUserMoved, self.on_user_moved)

    @property
    def channels(self) -> dict[str, str]:
        return self.instance_storage.get("channels") or {}

    @channels.setter
    def channels(self, channels: dict[str, str]):
        self.instance_storage["channels"] = channels

    def on_user_moved(self, ctx: Context, channel: ContextChannel, actor: ContextUser):
        try:
            parent = channel.parent()
            if not parent:
                return
            name = self.channels[parent.id()]
            clear_empty(parent)
            check_empty(ctx, parent, name)
        except KeyError:
            try:
                name = self.channels[channel.id()]
                clear_empty(channel)
                check_empty(ctx, channel, name)
            except KeyError:
                pass


class ApplyMagic(Command):
    def __init__(self, auto_channel: AutoChannel):
        super().__init__("applymagic", "Make this channel magic! Syntax: !applymagic <name>")
        self.plugin = auto_channel

    def execute(self, ctx: Context, message: str):
        if not message:
            return ctx.message.text("Please specify a name for the automagic channels",
                                    color=Colors.RED).reply_to_channel()
        channel = ctx.user.current_channel()
        name = message
        ctx.message.text("Applying", Colors.RED) \
            .text("magic ", color=Colors.ORANGE) \
            .text("on ", color=Colors.YELLOW) \
            .text("channel: ", color=Colors.YELLOW) \
            .bold(channel.name(), color=Colors.GREEN) \
            .text(" using ", color=Colors.LIME) \
            .text(" name ", color=Colors.BLUE) \
            .bold(name, color=Colors.VIOLET).reply_to_channel()
        channels = self.plugin.channels
        channels[channel.id()] = name
        self.plugin.channels = channels
        check_empty(ctx, channel, name)


class RemoveMagic(Command):
    def __init__(self, auto_channel: AutoChannel):
        super().__init__("removemagic", "Make this channel back to normal")
        self.plugin = auto_channel

    def execute(self, ctx: Context, message: str):
        try:
            channel = ctx.user.current_channel()
            channels = self.plugin.channels
            del channels[channel.id()]
            self.plugin.channels = channels
            clear_empty(channel)
            ctx.message.text("This channel is now normal again").reply_to_channel()
        except KeyError:
            ctx.message.text("This channel is already boring").reply_to_channel()


plugin = AutoChannel
