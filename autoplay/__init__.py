from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Dict, List, Callable
    from mello.utils.plugins.context import Context
    from mello.utils.plugins.media import ContextTrack
    from mello.utils.plugins.message import ContextMessage

from random import shuffle, randint
import re
from enum import IntEnum
from mello.utils.plugins import Plugin, Command
from mello.utils.plugins.media import EndReason
from mello.utils.plugins.callbacks import Callback
from mello.utils.plugins.message import Colors


class Status(IntEnum):
    Ignored = 1
    FullIgnored = 2


class Filter:
    def __init__(self, negative: bool, _filter: str, keyword: str):
        self.negative = negative
        self.filter = _filter
        self.keyword = keyword.lower()
        if self.filter == "duration":
            self._apply: Callable[[ContextTrack], bool] = lambda track: track.duration < int(self.keyword)
        elif self.filter == "author":
            self._apply: Callable[[ContextTrack], bool] = lambda track: self.keyword in track.author.lower()
        elif self.filter == "uploader":
            self._apply: Callable[[ContextTrack], bool] = lambda track: self.keyword in track.uploader.name.lower()
        elif self.filter == "title":
            self._apply: Callable[[ContextTrack], bool] = lambda track: self.keyword in track.normalized_title.lower()
        else:
            self._apply: Callable[[ContextTrack], bool] = lambda track: False

    def apply(self, track: ContextTrack):
        if self.negative:
            return not self._apply(track)
        else:
            return self._apply(track)

    def explain(self, message: ContextMessage) -> ContextMessage:
        if self.filter == "duration":
            return message.text(
                f"select tracks that are {'more' if self.negative else 'less'} than {self.keyword} seconds long")
        else:
            doesnt = "doesn't"  # seriously python?
            return message.text(
                f"select tracks if {self.filter} {doesnt if self.negative else ''} contains {self.keyword}")

    def __str__(self):
        return f"{'!' if self.negative else ''}{self.filter}:{self.keyword}"

    def __repr__(self):
        return self.__str__()

    def as_dict(self):
        return {
            "negative": self.negative,
            "filter": self.filter,
            "keyword": self.keyword
        }

    @staticmethod
    def from_dict(data: dict):
        if "negative" not in data or "filter" not in data or "keyword" not in data:
            return None
        return Filter(data["negative"], data["filter"], data["keyword"])


class IFilters:
    def __init__(self, autoplay: AutoPlay):
        self.filters: List[Filter] = []
        self.plugin = autoplay

    def add(self, f: Filter):
        self.filters.append(f)

    def pop(self, index: int):
        return self.filters.pop(index)

    def clear(self):
        self.filters.clear()

    def serializable(self):
        return [f.as_dict() for f in self.filters]

    def apply(self, track: ContextTrack):
        result = True
        for f in self.filters:
            result = result and f.apply(track)
        if self.plugin.blacklist_active:
            result = result and (str(track.id) not in self.plugin.blacklist or self.plugin.blacklist[
                str(track.id)] == Status.Ignored)
        return result


class AutoPlay(Plugin):
    def __init__(self):
        super().__init__("autoplay", "AutoPlay", "After a song autoqueue another song", ["m3rk", "nico9889"])

        self.autoplay_active = False
        self.blacklist_active = False
        self.filters: IFilters = IFilters(self)
        self.tracks: list[ContextTrack] = []

        self.add_command(RandomCommand(self))
        self.add_command(SwitchAutoplay(self))
        self.add_command(SwitchBlacklist(self))
        self.add_command(Filters(self))
        self.add_command(AddFilter(self))
        self.add_command(DeleteFilter(self))
        self.add_command(ResetFilters(self))
        self.add_command(SaveFilters(self))
        self.add_command(LoadFilters(self))
        self.add_command(FiltersPresets(self))

        self.set_callback(Callback.OnMusicEnd, self.on_music_end)
        self.set_callback(Callback.OnPlayerNext, self.on_player_next)
        self.set_callback(Callback.OnMusicStart, self.on_music_start)
        self.set_callback(Callback.OnTrackAdd, self.on_track_add)
        self.set_callback(Callback.OnTrackDelete, self.on_track_delete)

    def on_load(self, ctx: Context):
        if "blacklist" not in self.instance_storage:
            self.instance_storage["blacklist"] = {}
        if "presets" not in self.instance_storage:
            self.instance_storage["presets"] = {}

    def on_track_add(self, ctx: Context, track: ContextTrack):
        if self.filters.apply(track):
            self.tracks.append(track)

    def on_track_delete(self, ctx: Context, track: ContextTrack):
        i = self.tracks.index(track)
        if i is not None:
            del self.tracks[i]

    @property
    def presets(self) -> Dict[str, List[dict[str, str | bool]]]:
        return self.instance_storage["presets"] if "presets" in self.instance_storage else {}

    @presets.setter
    def presets(self, presets: Dict[str, List[dict[str, str | bool]]]):
        self.instance_storage["presets"] = presets

    @property
    def blacklist(self) -> Dict[str, Status]:
        return self.instance_storage["blacklist"] if "blacklist" in self.instance_storage else {}

    @blacklist.setter
    def blacklist(self, blacklist: Dict[str, Status]):
        self.instance_storage["blacklist"] = blacklist

    def save_filters(self, name: str):
        serializable = self.filters.serializable()
        presets = self.presets
        presets[name] = serializable
        self.presets = presets

    def load_filters(self, name):
        if name not in self.presets:
            return False
        filters = []
        preset = self.presets[name]
        for f in preset:
            f = Filter.from_dict(f)
            if f:
                filters.append(f)
        self.filters.clear()
        for f in filters:
            self.filters.add(f)
        return True

    def on_music_start(self, ctx: Context, track: ContextTrack):
        if str(track.id) in self.blacklist:
            # Il bot non può aver avviato le tracce FullIgnored, essendo stato un utente è stato volontario,
            # si riporta a canzone accettata
            if self.blacklist[str(track.id)] == Status.FullIgnored:
                del self.blacklist[str(track.id)]
                self.blacklist = self.blacklist

    # Quando la musica finisce
    def on_music_end(self, ctx: Context, track: ContextTrack, reason: EndReason):
        if reason == EndReason.Terminated and str(track.id) in self.blacklist:
            del self.blacklist[str(track.id)]
            self.blacklist = self.blacklist
        if self.autoplay_active and reason != EndReason.Stop:  # Se autoplay abilitato
            if self.tracks:
                track = self.tracks.pop(0)
                self.tracks.append(track)
                if len(ctx.media.queue()) == 0:
                    ctx.media.play(track.id)
                else:
                    ctx.media.enqueue(track.id)

    def on_player_next(self, ctx: Context, track: ContextTrack):
        if self.blacklist_active:
            blacklist = self.blacklist
            try:
                blacklist[str(track.id)] = Status.FullIgnored
            except KeyError:
                blacklist[str(track.id)] = Status.Ignored
            self.blacklist = blacklist
            
    def apply_filters(self, ctx: Context):
        self.tracks = list(filter(self.filters.apply, ctx.media.tracks()))
        shuffle(self.tracks)


class SwitchAutoplay(Command):
    def __init__(self, m_plugin: AutoPlay):
        super().__init__("apswitch", "Switch autoplay on/off")
        self.plugin: AutoPlay = m_plugin

    def execute(self, ctx: Context, message: str):
        self.plugin.autoplay_active = not self.plugin.autoplay_active
        message = ctx.message.text("Autoplay ")
        if self.plugin.autoplay_active:
            message = message.bold('on')
            self.plugin.apply_filters(ctx)
        else:
            message = message.bold('off')
            self.plugin.tracks = []
        message.reply_to_channel()


class SwitchBlacklist(Command):
    def __init__(self, m_plugin: AutoPlay):
        super().__init__("blacklist", "Switch blacklist on/off")
        self.plugin: AutoPlay = m_plugin

    def execute(self, ctx: Context, message: str):
        self.plugin.blacklist_active = not self.plugin.blacklist_active
        ctx.message.text("Blacklist ").bold('on' if self.plugin.blacklist_active else 'off').reply_to_channel()


class AddFilter(Command):
    def __init__(self, autoplay: AutoPlay):
        super().__init__("addfilter", "Add a filter. Syntax: (!)(author|uploader|title|duration):(keywords)")
        self.plugin = autoplay

    def execute(self, ctx: Context, message: str):
        result = re.search("(!?)(title|author|uploader|duration):(.+)", message)
        if not result:
            return ctx.message \
                .text("Invalid filter. Accepted syntax: (!)(filter):(keywords). Example: !uploader:admin") \
                .newline().text("Accepted filters:") \
                .list() \
                .add("author", bold=True) \
                .add("title", bold=True) \
                .add("uploader", bold=True) \
                .add("duration", bold=True) \
                .close().reply_to_channel()
        if result.group(2) == "duration" and not result.group(3).isdigit():
            return ctx.message.text("Duration filter accepts only numbers. You must specify the value in seconds.")
        filter_ = Filter(result.group(1) == '!', result.group(2), result.group(3))
        self.plugin.filters.add(filter_)
        self.plugin.apply_filters(ctx)
        success = ctx.message.bold("Filter added successfully!", color=Colors.GREEN).newline().bold("Effect:")
        success = filter_.explain(success)
        success.reply_to_channel()


class Filters(Command):
    def __init__(self, autoplay: AutoPlay):
        super().__init__("filters", "List all active filters and explains the effects.")
        self.plugin = autoplay

    def execute(self, ctx: Context, message: str):
        message = ctx.message.text("Active filters:").list()
        i = 0
        for f in self.plugin.filters.filters:
            message = message.add(f"{i}) {str(f)}")
            i += 1
        message = message.close().newline()
        for i in range(len(self.plugin.filters.filters)):
            message = self.plugin.filters.filters[i].explain(message)
            if i + 1 < len(self.plugin.filters.filters):
                message = message.bold(" and ")
            message = message.newline()
        message = message.newline() \
            .bold("Blacklist: ").text(f"{'active' if self.plugin.blacklist_active else 'inactive'}") \
            .newline()
        message.reply_to_channel()


class DeleteFilter(Command):
    def __init__(self, autoplay: AutoPlay):
        super().__init__("delfilter", "Delete a filter by list index")
        self.plugin = autoplay

    def execute(self, ctx: Context, message: str):
        if not message.isdigit():
            return ctx.message.text("Invalid index. Index must be a number", color=Colors.RED).reply_to_channel()
        index = int(message)
        if index > len(self.plugin.filters.filters):
            return ctx.message.text("Invalid index. Please check the filters' list and try again.",
                                    color=Colors.RED).reply_to_channel()
        if index < 0:
            return ctx.message.text("Invalid index. Index must be greater or equal to zero.",
                                    color=Colors.RED).reply_to_channel()
        f = self.plugin.filters.pop(index)
        self.plugin.apply_filters(ctx)
        ctx.message.text(f"Successfully removed: {str(f)}").reply_to_channel()


class ResetFilters(Command):
    def __init__(self, autoplay: AutoPlay):
        super().__init__("resetfilters", "Delete all the filters")
        self.plugin = autoplay

    def execute(self, ctx: Context, message: str):
        self.plugin.filters.clear()
        self.plugin.tracks = ctx.media.tracks()
        ctx.message.bold("All filters deleted.", color=Colors.ORANGE).reply_to_channel()


class SaveFilters(Command):
    def __init__(self, autoplay: AutoPlay):
        super().__init__("savefilters", "Save current filters as preset")
        self.plugin = autoplay

    def execute(self, ctx: Context, message: str):
        if not message:
            return ctx.message.text("Please specifiy an alphanumeric name for the preset",
                                    color=Colors.RED).reply_to_channel()
        if not message.isalnum():
            return ctx.message.text("Specified name must be alphanumeric", color=Colors.RED).reply_to_channel()
        self.plugin.save_filters(message)
        ctx.message.text("Filters saved").reply_to_channel()


class LoadFilters(Command):
    def __init__(self, autoplay: AutoPlay):
        super().__init__("loadfilters", "Load saved filters")
        self.plugin = autoplay

    def execute(self, ctx: Context, message: str):
        if not message:
            return ctx.message.text("Please specify an alphanumeric name for the preset",
                                    color=Colors.RED).reply_to_channel()
        if not message.isalnum():
            return ctx.message.text("Specified name must be alphanumeric", color=Colors.RED).reply_to_channel()
        if self.plugin.load_filters(message):
            self.plugin.apply_filters(ctx)
            ctx.message.text("Filters loaded").reply_to_channel()
        else:
            ctx.message.text("Invalid filters presets", color=Colors.RED).reply_to_channel()


class FiltersPresets(Command):
    def __init__(self, autoplay: AutoPlay):
        super().__init__("filterspresets", "List all the filters presets name")
        self.plugin = autoplay

    def execute(self, ctx: Context, message: str):
        presets = self.plugin.presets
        message = ctx.message.bold("Available presets:").list()
        for name in presets.keys():
            message.add(name)
        message.close().reply_to_channel()


class RandomCommand(Command):
    def __init__(self, autoplay: AutoPlay):
        super().__init__("random", "Play a random track!")
        self.plugin = autoplay

    def execute(self, ctx: Context, message: str):
        if self.plugin.autoplay_active:
            track = self.plugin.tracks.pop(0)
            self.plugin.tracks.append(track)
        else:
            tracks = ctx.media.tracks()
            track = tracks[randint(0, len(tracks) - 1)]
        ctx.media.play(track.id)


plugin = AutoPlay
