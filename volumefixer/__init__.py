from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mello.utils.plugins.context import Context
    from typing import Dict

from mello.utils.plugins import Plugin, Command
from mello.utils.plugins.callbacks import Callback
from mello.utils.plugins.media import ContextTrack
from mello.utils.plugins.message import Colors


class VolumeFixer(Plugin):
    def __init__(self):
        super().__init__("vf", "Volume Fixer", "Adjust bot volume per track", ["nico9889"])
        self.add_command(VFSwitch(self))
        self.add_command(VolumeFix(self))
        self.add_command(VFix(self))
        self.add_command(Volume(self))
        self.base_volume = 50

        self.callbacks.set_callback(Callback.OnMusicStart, self.on_music_start)

    def on_load(self, ctx: Context):
        if "on" not in self.instance_storage:
            self.instance_storage["on"] = False
        if "volumes" not in self.instance_storage:
            self.instance_storage["volumes"] = {}
        self.base_volume = ctx.media.volume

    @property
    def on(self) -> bool:
        return self.instance_storage["on"]

    @on.setter
    def on(self, on: bool):
        self.instance_storage["on"] = on

    @property
    def volumes(self) -> Dict[str, int]:
        return self.instance_storage["volumes"]

    @volumes.setter
    def volumes(self, volumes: Dict[str, int]):
        self.instance_storage["volumes"] = volumes

    def on_music_start(self, ctx: Context, track: ContextTrack):
        if self.on:
            try:
                percentage = self.volumes[str(track.id)]
                ctx.media.volume = self.base_volume / 100 * percentage
                ctx.message \
                    .bold(f"VolumeFixer:", color=Colors.GREEN) \
                    .text(f"Volume adjusted to {ctx.media.volume}% ({percentage}% of base volume)") \
                    .reply_to_channel()
            except KeyError:
                ctx.media.volume = self.base_volume

    def fix(self, ctx: Context):
        if self.on:
            track = ctx.media.current()
            if track:
                try:
                    percentage = self.volumes[str(track.id)]
                    ctx.media.volume = self.base_volume / 100 * percentage
                    ctx.message \
                        .text(f"Volume adjusted to {ctx.media.volume}% ({percentage}% of base volume)") \
                        .reply_to_channel()
                except KeyError:
                    pass


class VFSwitch(Command):
    def __init__(self, volumefixer: VolumeFixer):
        super().__init__("vfswitch", "Activate/deactivate volume fix")
        self.plugin = volumefixer

    def execute(self, ctx: Context, message: str):
        self.plugin.on = not self.plugin.on
        message = ctx.message.bold("VolumeFix ")
        if self.plugin.on:
            self.plugin.fix(ctx)
            self.plugin.base_volume = ctx.media.volume
            message = message.text("enabled")
        else:
            ctx.media.volume = self.plugin.base_volume
            message = message.text("disabled")
        message.reply_to_channel()


class VolumeFix(Command):
    def __init__(self, volumefixer: VolumeFixer):
        super().__init__("volumefix",
                         "Adjust the volume for the current playing track. Specify a value between 0 and 100.")
        self.plugin = volumefixer

    def execute(self, ctx: Context, message: str):
        if not message.isdigit():
            return ctx.message.text("Invalid argument. Please specify a number between 0 and 100.",
                                    color=Colors.RED).reply_to_channel()
        percentage = int(message)
        if not 0 <= percentage <= 100:
            return ctx.message.text("Invalid value. Please specify a number between 0 and 100.",
                                    color=Colors.RED).reply_to_channel()
        track = ctx.media.current()
        if not track:
            return ctx.message.text("No track is playing right now.", color=Colors.RED).reply_to_channel()
        volumes = self.plugin.volumes
        volumes[str(track.id)] = percentage
        self.plugin.volumes = volumes
        self.plugin.fix(ctx)


class VFix(VolumeFix):
    def __init__(self, volumefixer: VolumeFixer):
        super().__init__(volumefixer)
        self.tag = "vfix"
        self.description = "Shortcut for volumefix"


class Volume(Command):
    def __init__(self, volumefixer: VolumeFixer):
        super().__init__("volume", "Intercepts the volume command and use that as base volume")
        self.plugin = volumefixer

    def execute(self, ctx: Context, message: str):
        if not message.isdigit():
            return  # Error already reported by media plugin
        volume = int(message)
        if not 0 <= volume <= 100:
            return  # Error already reported by media plugin
        self.plugin.base_volume = volume
        self.plugin.fix(ctx)


plugin = VolumeFixer
