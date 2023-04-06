from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Dict
    from mello.utils.plugins.context import Context
    from mello.utils.plugins.user import ContextUser
    from mello.utils.plugins.channels import ContextChannel

from threading import Timer

from mello.utils.plugins import Command, Plugin

from mello.utils.plugins.callbacks import Callback
from mello.utils.plugins.message import Colors
from mello.utils.plugins.web.options.number_option import NumberOption


class AutoAfkPlugin(Plugin):
    def __init__(self):
        super().__init__("autoafk", "AutoAFK", "Check periodically if an user quit the audio and move it into the AFK channel", ["nico9889"])
        self.previous_channels: Dict[str, ContextChannel] = {}
        self.timers: Dict[str, Timer] = {}
        self.channel: ContextChannel | None = None
        self.add_command(SetAfkTimeCommand(self))
        self.add_command(SetAfkChannelCommand(self))
        self.add_command(AfkCommand(self))
        self.add_command(Enable(self))
        self.add_command(Disable(self))
        self.set_callback(Callback.OnUserDeaf, self.on_deafen_change)
        self.time_option = NumberOption("AFK Time", "Seconds that has to elapse before moving the user", 15, 0, 60, 1)
        self.time_option.on_change = lambda value: setattr(self, "time", value if value > 0 else 0) or value > 0
        self.options.add(self.time_option)

    def on_load(self, ctx: Context):
        channel_id = self.instance_storage.get("channel")
        if channel_id:
            self.channel = ctx.channels.get(channel_id)
        self.time_option.set(self.time)

    @property
    def time(self):
        return self.instance_storage.get("time") or 15

    @time.setter
    def time(self, value):
        self.instance_storage["time"] = value

    @property
    def enabled(self):
        return self.instance_storage.get("enabled") or False

    @enabled.setter
    def enabled(self, value: bool):
        self.instance_storage["enabled"] = value

    def afk(self, user: ContextUser):
        self.previous_channels[user.id()] = user.current_channel()
        user.send_message(f"You were moved because you were muted for more than {self.time} seconds.\n"
                          f"Unmute to get back to the previous channel!")
        user.move(self.channel)
        self.timers.pop(user.id())

    def on_deafen_change(self, ctx: Context, deaf: bool, actor):
        if self.channel and self.enabled:
            if deaf:
                t = Timer(interval=self.time, function=self.afk, args=[ctx.user, ])
                self.timers[ctx.user.id()] = t
                t.start()
            else:
                try:
                    channel = self.previous_channels.pop(ctx.user.id())
                    ctx.user.move(channel)
                except KeyError:
                    pass
                try:
                    t = self.timers.pop(ctx.user.id())
                    t.cancel()
                except KeyError:
                    pass


plugin = AutoAfkPlugin


class SetAfkTimeCommand(Command):
    def __init__(self, plugin: AutoAfkPlugin):
        super().__init__("afktime", "Set the AFK time in seconds between every scan")
        self.plugin = plugin

    def execute(self, ctx: Context, message: str):
        try:
            self.plugin.time = int(message)
            ctx.message.text(
                f"Ok! I'll move every user muted for more than {self.plugin.time} seconds in {self.plugin.channel}.").reply_to_user()
        except ValueError:
            ctx.message.text("Invalid number! The number of seconds must be an integer number!",
                             color=Colors.RED).reply_to_user()


class SetAfkChannelCommand(Command):
    def __init__(self, plugin: AutoAfkPlugin):
        super().__init__("afkchannel", "Set the current channel as AFK channel")
        self.plugin = plugin

    def execute(self, ctx: Context, message: str):
        channel = ctx.user.current_channel()
        if channel:
            self.plugin.channel = channel
            self.plugin.instance_storage["channel"] = channel.id()
            ctx.message.bold(channel.name()).text(f" has been set as the AFK channel").reply_to_user()


class AfkCommand(Command):
    def __init__(self, plugin: AutoAfkPlugin):
        super().__init__("afk", "Move the user into the AFK channel")
        self.plugin = plugin

    def execute(self, ctx: Context, message: str):
        if self.plugin.channel:
            ctx.user.move(self.plugin.channel)
        else:
            ctx.message.text("AFK channel hasn't been setted").reply_to_user()


class Enable(Command):
    def __init__(self, autoafk: AutoAfkPlugin):
        super().__init__("enable", "Enable the plugin")
        self.plugin = autoafk

    def execute(self, ctx: Context, message: str):
        self.plugin.enabled = True
        ctx.message.bold("AutoAFK: ").text("enabled").reply_to_channel()


class Disable(Command):
    def __init__(self, autoafk: AutoAfkPlugin):
        super().__init__("disable", "Disable the plugin")
        self.plugin = autoafk

    def execute(self, ctx: Context, message: str):
        self.plugin.enabled = False
        ctx.message.bold("AutoAFK: ").text("disabled").reply_to_channel()
