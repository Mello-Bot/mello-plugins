from __future__ import annotations

from re import search
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mello.utils.plugins.context import Context
    from mello.utils.plugins.media import ContextTrack, ContextStream
    from mello.utils.plugins.channels import ContextChannel
    from mello.utils.plugins.user import ContextUser
    from mello.utils.plugins.context import DecoratorContext

from mello.utils.plugins import DecoratorPlugin
from mello.utils.plugins.context import ContextType
from mello.utils.plugins.message import Colors

plugin = DecoratorPlugin("media", "Media", "Bot player commands!", ["nico9889"])


@plugin.on_load
def _on_load(ctx: DecoratorContext):
    try:
        ctx.media.volume = ctx.instance_storage["volume"]
    except KeyError:
        ctx.media.volume = 50
        ctx.instance_storage["volume"] = 50


@plugin.on_user_leaved
def _on_user_leaved(ctx: DecoratorContext):
    if not ctx.channels.current().users():
        ctx.media.stop()


@plugin.on_user_moved
def _on_user_moved(ctx: DecoratorContext, _: ContextChannel, __: ContextUser):
    _on_user_leaved(ctx)


@plugin.on_user_banned
def _on_user_banned(ctx: DecoratorContext, _: ContextUser, __: str):
    _on_user_leaved(ctx)


@plugin.on_user_kicked
def _on_user_kicked(ctx: DecoratorContext, _: ContextUser, __: str):
    _on_user_leaved(ctx)


@plugin.on_music_start
def _on_music_start(ctx: DecoratorContext, track: ContextTrack):
    ctx.message.text("Playing: ").bold(track.title).reply_to_channel()
    if ctx.type == ContextType.Discord:
        ctx.me.set_description(track.title)


# FIXME
@plugin.on_stream_change
def _on_stream_change(ctx: DecoratorContext, stream: ContextStream):
    ctx.message.text("Now streaming ").bold(stream.title).text(" from ").bold(stream.author).reply_to_channel()
    if ctx.type == ContextType.Discord:
        ctx.me.set_description(stream.title)


@plugin.on_mute_change
def _on_mute_change(ctx: DecoratorContext, muted: bool, actor: ContextUser | None):
    if ctx.user == ctx.me:
        if muted:
            ctx.message \
                .bold("Please, mute me locally if you need or stop me if the other users agree. (×﹏×)",
                      color=Colors.RED).send_to_user(actor)
            # FIXME: this need to be fixed on PyMumble, if the user is the bot it "unmute" it on client side instead of
            #  server side
            ctx.me.unmute()
            if ctx.type == ContextType.Mumble:
                ctx.message.bold(
                    f"{actor.name()} muted me and for technical reasons I can't unmute myself. Please help me (╥﹏╥)",
                    color=Colors.ORANGE
                ).reply_to_channel()
        else:
            ctx.message.bold("Thank you! ヽ(~_~(・_・ )ゝ", color=Colors.YELLOW).send_to_user(actor)


@plugin.command("tracks", "List all tracks that the bot can play")
def _tracks(ctx: DecoratorContext, message: str):
    if not message:
        page = 1
        tracks = ctx.media.tracks()[0:20]
    elif message.isdigit():
        page = int(message)
        tracks = ctx.media.tracks()[20 * (page - 1):20 * page]
    else:
        page = 1
        tracks = ctx.media.tracks()[0:20]
        ctx.message.text("Invalid page number.", color=Colors.RED).reply_to_channel()
    m = ctx.message.text(f"Available tracks [Page: {page}/{len(ctx.media.tracks()) // 20 + int(102 % 20 > 0)}]:")
    li = m.list()
    for track in tracks:
        li.add(f"{track.id}) {track.title}")
    m = li.close()
    m.reply_to_channel()


@plugin.command("play", "Play the selected track")
def _play(ctx: DecoratorContext, message: str):
    try:
        ctx.media.play(int(message))
    except ValueError:
        track = ctx.media.search(message)
        if track:
            ctx.media.play(track.id)


@plugin.command("stream", "Reproduce audio from a streaming URL")
def _stream(ctx: DecoratorContext, message: str):
    if not message:
        ctx.message.text("Please provide a stream index or partial stream name. Use !streams to list all streams by index", color=Colors.RED).reply_to_channel()
    streams = ctx.media.streams()
    try:
        stream = streams[int(message)]
    except ValueError:
        streams = list(filter(lambda _stream: message in _stream.title.lower(), streams))
        if streams:
            stream = streams[0]
        else:
            stream = None
    except IndexError:
        stream = None
    if stream:
        ctx.media.stream(stream)
    else:
        ctx.message.text("Stream not found", color=Colors.RED).reply_to_channel()


@plugin.command("streams", "List all available streams")
def _streams(ctx: DecoratorContext, _: str):
    li = ctx.message.bold("Available streams:").list()
    for idx, stream in enumerate(ctx.media.streams()):
        li = li.add(f"{idx}) {stream.title}")
    li.close().reply_to_channel()


@plugin.command("stop", "Stop the playback")
def _stop(ctx: DecoratorContext, _: str):
    ctx.media.stop()


@plugin.command("seek", "Seek the current track. Please give a value in seconds.")
def _seek(ctx: DecoratorContext, message: str):
    try:
        value = float(message)
        if value >= 0:
            ctx.media.seek(value)
            return
    except ValueError:
        pass
    ctx.message.text("Invalid seek value. Please give a value in seconds >= 0", bold=True,
                     color=Colors.RED).reply_to_user()


@plugin.command("volume", "Change the volume (0-100)")
def _volume(ctx: DecoratorContext, message: str):
    if not message:
        ctx.message.bold("Current volume: ").text(str(ctx.media.volume)).reply_to_user()
    elif message.isdigit() and 0 <= int(message) <= 100:
        value = int(message)
        ctx.media.volume = value
        ctx.instance_storage["volume"] = value
    else:
        ctx.message.text("Invalid volume. Must be a number between 0 and 100.", color=Colors.RED)


def _duration(duration: float) -> str:
    if not duration:
        return "00:00"
    else:
        seconds: str = str(round(duration % 60))
        minutes: str = str(round(duration // 60 % 60))
        hours: str = str(round(duration // 3600))
        out = f"{minutes.rjust(2, '0')}:{seconds.rjust(2, '0')}"
        if int(hours):
            out = f"{hours.rjust(2, '0')}:{out}"
        return out


@plugin.command("current", "Send the current track info in chat")
def _current(ctx: DecoratorContext, _: str):
    track = ctx.media.current()
    if track:
        ctx.message.bold("Playing: ").text(track.title).newline() \
            .bold("by:").text(track.author).newline() \
            .bold("uploaded by:").text(track.uploader.name).newline() \
            .text(f"{_duration(ctx.media.status().elapsed)} / {_duration(track.duration)}").reply_to_channel()
    else:
        ctx.message.bold("I'm not playing anything").reply_to_channel()


@plugin.command("status", "Report the player status")
def _status(ctx: DecoratorContext, _: str):
    current = ctx.media.current()
    status = ctx.media.status()
    message = ctx.message.newline().bold("Current track: ").text(current.title if current else "").newline() \
        .bold("Time: ").text(f"{_duration(status.elapsed)} / {_duration(current.duration) if current else 0}").newline()
    if status.shuffle:
        message = message.bold("Shuffle: ").text("enabled", color=Colors.GREEN).newline()
    if status.repeat:
        message = message.bold("Repeat: ").text("enabled", color=Colors.GREEN).newline()
    message.reply_to_channel()


@plugin.command("queue", "Send a message with the current queue")
def _queue(ctx: DecoratorContext, _: str):
    li = ctx.message.text("Current queue:").list()
    for track in ctx.media.queue():
        li.add(track.title)
    li.close().reply_to_channel()


@plugin.command("enqueue", "Add a track to the queue")
def _enqueue(ctx: DecoratorContext, message: str):
    try:
        track = ctx.media.enqueue(int(message))
    except ValueError:
        track = ctx.media.search(message)
        track = ctx.media.enqueue(track.id)

    if track:
        ctx.message.text("Enqueued ").bold(track.title).reply_to_channel()
    else:
        ctx.message.text(f"I can't find any track that contains: ", color=Colors.RED).bold(message, color=Colors.RED) \
            .reply_to_channel()


@plugin.command("prev", "Play a previous played track")
def _prev(ctx: DecoratorContext, _: str):
    ctx.media.prev()


@plugin.command("next", "Play the next track in queue")
def _next(ctx: DecoratorContext, _: str):
    ctx.media.next()


@plugin.command("shuffle", "Switch on/off track shuffle")
def _shuffle(ctx: DecoratorContext, _: str):
    ctx.media.shuffle = not ctx.media.shuffle
    message = ctx.message.bold("Shuffle: ")
    if ctx.media.shuffle:
        message.text("enabled", color=Colors.GREEN).reply_to_channel()
    else:
        message.text("disabled", color=Colors.RED).reply_to_channel()


@plugin.command("repeat", "Switch on/off track repeat")
def _repeat(ctx: DecoratorContext, _: str):
    ctx.media.repeat = not ctx.media.repeat
    message = ctx.message.bold("Repeat: ")
    if ctx.media.shuffle:
        message.text("enabled", color=Colors.GREEN).reply_to_channel()
    else:
        message.text("disabled", color=Colors.RED).reply_to_channel()


@plugin.command("search", "Search a track by title")
def _search(ctx: DecoratorContext, message: str):
    message = message.lower()
    m = ctx.message.text("Results:")
    li = m.list()
    i = 0
    found = 0

    tracks = ctx.media.tracks()
    while i < len(tracks) and found < 10:
        if message in tracks[i].normalized_title:
            li.add(f"{tracks[i].id}) {tracks[i].title}")
            found += 1
        i += 1
    m = li.close()
    if found:
        m.reply_to_channel()
    else:
        ctx.message.bold("No results for this search term.").reply_to_channel()


def _download(after, ctx: Context, message: str):
    if ctx.type == ContextType.Mumble:
        url = search("href=\"(.*)\"", message).group(1)
    else:
        # TODO: TeamSpeak
        url = message
    ctx.media.youtube.download(url, after)
    ctx.message.text("Downloading: ").hypertext(url, url).reply_to_channel()


@plugin.command("ytdl", "Download a track from a supported service")
def _ytdl(ctx: DecoratorContext, message: str):
    def _after(track: ContextTrack | None):
        if track is not None:
            ctx.message.text("Download completed: ").bold(track.title).reply_to_channel()
        else:
            ctx.message.text(f"Download of {message} failed!", color=Colors.RED).reply_to_channel()

    _download(_after, ctx, message)


@plugin.command("ytdlp", "Downloads a track from a supported service and plays it")
def _ytdlp(ctx: DecoratorContext, message: str):
    def _after(track: ContextTrack | None):
        if track is not None:
            ctx.media.play(track.id)
            ctx.message.bold("Playing: ").text(track.title).reply_to_channel()
        else:
            ctx.message.text(f"Download of {message} failed!", color=Colors.RED).reply_to_channel()

    _download(_after, ctx, message)


@plugin.command("ytdlq", "Downloads a track from a supported service and put it into queue")
def _ytdlq(ctx: DecoratorContext, message: str):
    def _after(track: ContextTrack | None):
        if track is not None:
            ctx.media.enqueue(track.id)
            ctx.message.bold("Queued: ").text(track.title).reply_to_channel()
        else:
            ctx.message.text(f"Download of {message} failed!", color=Colors.RED).reply_to_channel()

    _download(_after, ctx, message)
