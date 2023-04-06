from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Callable
    from mello.utils.plugins.context import Context
    from mello.utils.plugins.media import ContextTrack

from typing import List
from mello.utils.plugins import Plugin, Command
from mello.utils.plugins.callbacks import Callback
from mello.utils.plugins.message import Colors, ContextMessage


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
    def from_dict(data: dict) -> Filter | None:
        try:
            return Filter(data["negative"], data["filter"], data["keyword"])
        except KeyError:
            return None

    @staticmethod
    def from_str(data: str) -> Filter | None:
        result = re.search("(!?)(title|author|uploader|duration):(.+)", data)
        if not result:
            raise Exception("Invalid filter syntax")
        if result.group(2) == "duration" and not result.group(3).isdigit():
            raise Exception("Invalid duration value")
        return Filter(result.group(1) == '!', result.group(2), result.group(3))


class Filters(List[Filter]):
    def __init__(self):
        super().__init__()

    def serializable(self):
        return [f.as_dict() for f in self]


class AutoPlayList(Plugin):
    def __init__(self):
        super().__init__("autoplaylist", "AutoPlayList", "Automatically add tracks to playlist by keywords", ["nico9889"])
        self.add_command(Keywords(self))
        self.add_command(Playlists())
        self.add_command(AddKeyWord(self))
        self.add_command(DeleteKeyWord(self))
        self.add_command(ScanExistent(self))
        self.callbacks.set_callback(Callback.OnTrackAdd, self.on_track_add)

    def on_load(self, ctx: Context):
        if "keywords" not in self.instance_storage:
            self.instance_storage["keywords"] = {}

    @property
    def keywords(self) -> dict[str, list[int]]:
        return self.instance_storage["keywords"]

    @keywords.setter
    def keywords(self, keywords: dict[str, list[int]]):
        self.instance_storage["keywords"] = keywords

    def on_track_add(self, ctx: Context, track: ContextTrack):
        try:
            for keyword, playlists in self.keywords.items():
                filter_ = Filter.from_str(keyword)
                if filter_.apply(track):
                    for _id in playlists:
                        try:
                            playlist = ctx.media.playlists[_id]
                            if track not in playlist.get_tracks():
                                playlist.add_track(track.id)
                                ctx.message.text("AutoPlayList: Added track ").text(track.title).text(
                                    " to playlist ").text(playlist.name).reply_to_channel()
                        except KeyError:
                            ctx.message.text(f"AutoPlayList: playlist ID {_id} not found for filter {keyword}",
                                             color=Colors.RED).reply_to_channel()
        except Exception as e:
            ctx.message.text(str(e), color=Colors.RED).reply_to_channel()


class Keywords(Command):
    def __init__(self, autoplaylist: AutoPlayList):
        super().__init__("keywords", "List all the keywords")
        self.plugin = autoplaylist

    def execute(self, ctx: Context, message: str):
        message = ctx.message.bold("Keywords [keyword -> playlist]:").list()
        for key, playlists in self.plugin.keywords.items():
            names = []
            for _id in playlists:
                try:
                    playlist = ctx.media.playlists[_id]
                    names.append(playlist.name)
                except KeyError:
                    names.append("Invalid Playlist")
            message = message.add(f"{key} » {', '.join(names)}")
        message.close().reply_to_channel()


class AddKeyWord(Command):
    def __init__(self, autoplaylist: AutoPlayList):
        super().__init__("addkeyword", "Bind a new keyword to a playlist [Syntax: !addkeyword {playlist_id} {keyword}]")
        self.plugin = autoplaylist

    def execute(self, ctx: Context, message: str):
        chunks = message.split(" ", 1)
        if len(chunks) < 2:
            return ctx.message.text("Invalid syntax. Please use !addkeyword {playlist_id} {filter}]",
                                    color=Colors.RED).reply_to_channel()
        if not chunks[0].isdigit():
            return ctx.message.text("Invalid playlist ID: Playlist ID must be a number >= 1.",
                                    color=Colors.RED).reply_to_channel()
        playlist_id = int(chunks[0])
        try:
            playlist = ctx.media.playlists[playlist_id]
        except KeyError:
            return ctx.message.text("Invalid playlist ID: Playlist not found",
                                    color=Colors.RED).reply_to_channel()
        try:
            filter_ = Filter.from_str(chunks[1])
            keywords = self.plugin.keywords
            try:
                keywords[str(filter_)].append(playlist_id)
            except KeyError:
                keywords[str(filter_)] = [playlist_id]
            self.plugin.keywords = keywords
            return ctx.message.text("Added keyword ").bold(chunks[1]).text(" for playlist ").bold(
                playlist.name).reply_to_channel()
        except Exception as e:
            return ctx.message.text(str(e), color=Colors.RED).reply_to_channel()


class DeleteKeyWord(Command):
    def __init__(self, autoplaylist: AutoPlayList):
        super().__init__("delkeyword", "Delete a keyword [!delkeyword {keyword}]")
        self.plugin = autoplaylist

    def execute(self, ctx: Context, message: str):
        try:
            keywords = self.plugin.keywords
            del keywords[message]
            self.plugin.keywords = keywords
            ctx.message.text("AutoPlayList: keyword deleted").reply_to_channel()
        except KeyError:
            ctx.message.text("AutoPlayList: Keyword not found").reply_to_channel()


class Playlists(Command):
    def __init__(self):
        super().__init__("playlists", "List all playlists")

    def execute(self, ctx: Context, message: str):
        message = ctx.message.bold("Available playlists [{id}) {name}]:").list()
        for playlist in ctx.media.playlists.values():
            message = message.add(f"{playlist.id}) {playlist.name}")
        message.close().reply_to_channel()


class ScanExistent(Command):
    def __init__(self, autoplaylist: AutoPlayList):
        super().__init__("scanexistent", "Scan existent tracks")
        self.plugin = autoplaylist

    def execute(self, ctx: Context, message: str):
        tracks = ctx.media.tracks()
        for track in tracks:
            self.plugin.on_track_add(ctx, track)
        ctx.message.bold("AutoPlaylist: ").text("scan terminated").reply_to_channel()


plugin = AutoPlayList
