from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Dict
    from mello.utils.plugins.context import Context
    from mello.utils.plugins.channels import ContextChannel
    from mello.utils.plugins.user import ContextUser

from datetime import datetime, timedelta
from mello.utils.plugins import Plugin, Command
from mello.utils.plugins.callbacks import Callback
from mello.utils.plugins.message import Colors
from mello.utils.plugins.web.options.number_option import NumberOption


class KickCommand(Command):
    def __init__(self):
        super().__init__("kick", "Kick an user by username. You can specify a reason")

    def execute(self, ctx: Context, message: str):
        message += " "
        username, reason = message.split(" ", 1)
        lower = str.lower
        for user in ctx.users.values():
            if lower(user.name()) == lower(username):
                user.kick(reason)


class BanCommand(Command):
    def __init__(self):
        super().__init__("ban", "Ban an user by username. You can specify a reason")

    def execute(self, ctx: Context, message: str):
        message += " "
        username, reason = message.split(" ", 1)
        lower = str.lower
        for user in ctx.users.values():
            if lower(user.name()) == lower(username):
                user.ban(reason)


class RageCommand(Command):
    def __init__(self):
        super().__init__("rage", "Someone got angry")

    def execute(self, ctx: Context, message: str):
        author = ctx.user.name()
        for user in ctx.users.values():
            user.kick(f"{author} is very angry!")


class MoveMap:
    def __init__(self, plugin: CopPlugin, user: ContextUser):
        self.user = user
        self.kick_counter: int = 0
        self.static_counter: int = 0
        self.dynamic_counter: int = 0
        self.last_channel: ContextChannel = user.current_channel()
        self.last_move = datetime.now()
        self.plugin = plugin

    def check(self, destination: ContextChannel):
        if datetime.now() < self.last_move + timedelta(seconds=self.plugin.move_time_limit):
            if destination.id() == self.last_channel.id():
                self.static_counter += 1
                self.dynamic_counter += 1
            else:
                self.dynamic_counter += 1
            if self.dynamic_counter % 2 == 0:
                self.last_channel = destination
        else:
            self.static_counter = self.static_counter - 1 if self.static_counter > 0 else 0
            self.dynamic_counter = self.dynamic_counter - 1 if self.dynamic_counter > 0 else 0
        self.last_move = datetime.now()


class CopPlugin(Plugin):
    def __init__(self):
        super().__init__("cop", "Cop", "This is the police!", ["nico9889"])
        self.add_command(KickCommand())
        self.add_command(BanCommand())
        self.add_command(RageCommand())
        self.move_map: Dict[str, MoveMap] = {}
        self.set_callback(Callback.OnUserMoved, self.on_user_moved)
        self.set_callback(Callback.OnUserJoinServer, self.on_user_joined)

    def on_load(self, ctx: Context):
        dynamic_counter_option = NumberOption("Dynamic Counter",
                                              "Number of moves that the user is allowed to do between different channels",
                                              self.dynamic_move_limit, 2, 60, 1)
        static_counter_option = NumberOption("Static Counter",
                                             "Number of moves that the user is allowed to do between two channels",
                                             self.static_move_limit, 2, 60, 1)
        move_time_limit_option = NumberOption("Move time limit",
                                              "Time that has to elapsed between movement in seconds."
                                              "If the user moves in less time, it's considered spam and increase a"
                                              " counter, otherwise it decreases the counter if necessary.",
                                              self.move_time_limit, 1, 60, 1)
        kick_limit_option = NumberOption("Kick time limit", "If the user get kicked more than n times, "
                                                            "he/she will be permanently ban on the next "
                                                            "infraction. If 0 this is disabled.",
                                         self.kick_limit, 0, 60, 1)

        dynamic_counter_option.on_change = lambda value: setattr(self, "dynamic_move_limit", int(value)) or True
        static_counter_option.on_change = lambda value: setattr(self, "static_move_limit", int(value)) or True
        move_time_limit_option.on_change = lambda value: setattr(self, "move_time_limit", int(value) if value > 0 else None) or True
        kick_limit_option.on_change = lambda value: setattr(self, "kick_limit", int(value)) or True

        self.options.add(move_time_limit_option)
        self.options.add(dynamic_counter_option)
        self.options.add(static_counter_option)
        self.options.add(kick_limit_option)

    @property
    def move_time_limit(self) -> int:
        return self.instance_storage.get("move_time_limit") or 5

    @move_time_limit.setter
    def move_time_limit(self, time_limit: int):
        self.instance_storage["move_time_limit"] = time_limit

    @property
    def dynamic_move_limit(self) -> int:
        return self.instance_storage.get("dynamic_move_limit") or 5

    @dynamic_move_limit.setter
    def dynamic_move_limit(self, limit: int):
        self.instance_storage["dynamic_move_limit"] = limit

    @property
    def static_move_limit(self) -> int:
        return self.instance_storage.get("static_move_limit") or 3

    @static_move_limit.setter
    def static_move_limit(self, limit: int):
        self.instance_storage["static_move_limit"] = limit

    @property
    def kick_limit(self) -> int:
        return self.instance_storage.get("kick_limit") or 0

    @kick_limit.setter
    def kick_limit(self, kick_limit: int):
        self.instance_storage["kick_limit"] = kick_limit

    def on_user_joined(self, ctx: Context):
        if ctx.user.id() not in self.move_map:
            self.move_map[ctx.user.id()] = MoveMap(self, ctx.user)

    def on_user_moved(self, ctx: Context, channel: ContextChannel, actor: ContextUser):
        if ctx.user == actor and ctx.user != ctx.me:
            try:
                last_move = self.move_map[actor.id()]
            except KeyError:
                last_move = MoveMap(self, ctx.user)
                self.move_map[actor.id()] = last_move
            last_move.check(channel)
            if self.kick_limit and last_move.kick_counter > self.kick_limit:
                if last_move.static_counter > self.static_move_limit and last_move.dynamic_counter > self.dynamic_move_limit:
                    ctx.user.ban("I'm tired of kicking you, let's make this permanent. Goodbye")
            else:
                if last_move.static_counter > self.static_move_limit:
                    ctx.user.kick("Where are you going back and forth so fast?")
                    last_move.dynamic_counter -= 1
                    last_move.kick_counter += 1
                elif last_move.dynamic_counter > self.dynamic_move_limit:
                    ctx.user.kick("Please calm down! You are moving everywhere so fast!")
                    last_move.dynamic_counter -= 1
                    last_move.kick_counter += 1
                elif last_move.static_counter == self.static_move_limit or last_move.dynamic_counter == self.dynamic_move_limit:
                    ctx.message.text("Warning: you are moving too fast. On the next move you will be kicked!",
                                     color=Colors.ORANGE).send_to_user(ctx.user)


plugin = CopPlugin
