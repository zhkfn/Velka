import discord
from discord.ext import commands
from cogs.utils.dataIO import fileIO
from cogs.utils.chat_formatting import box
from cogs.utils import checks
from __main__ import send_cmd_help
import logging
import os
try:
    import tabulate
except:
    tabulate = None


log = logging.getLogger("red.judgement")

class Judge:
    """Keep track of user scores through ![judgement_type] @mention
    For now judgement types are hard coded: Sunlight & Wraith"""

    def __init__(self, bot):
        self.bot = bot
        self.scores = fileIO("data/judgement/scores.json", "load")
        self.settings = fileIO("data/judgement/settings.json", 'load')

    def _process_scores(self, member, score_to_add, judgement_type):
        member_id = member.id
        if member_id in self.scores:
            if judgement_type in self.scores.get(member_id, {}):
                if self.scores[member_id][judgement_type] - score_to_add < 0:
                    self.scores[member_id][judgement_type] = 0
                else:
                    self.scores[member_id][judgement_type] += score_to_add
            else:
                self.scores[member_id][judgement_type] = score_to_add
        else:
            self.scores[member_id] = {}
            self.scores[member_id][judgement_type] = score_to_add

    @commands.command(pass_context=True)
    async def judgement(self, ctx):
        """Checks a user's judgement points

           Example: !judgement """
        member = ctx.message.author
        member_id = member.id
        if self.scores.get(member.id, 0) != 0:
            member_dict = self.scores[member.id]
            msg = "Judgement for " + member.name + ":\n"

            whiteSoap = str(discord.utils.get(self. bot.get_all_emojis(), id="515521115607662593")) 
            redSoap = str(discord.utils.get(self. bot.get_all_emojis(), id="515521115762851840")) 

            if "Sunlight" in self.scores.get(member_id, {}):
                msg += whiteSoap + str(member_dict["Sunlight"]) + " victories.\n"
            if "Wraith" in self.scores.get(member_id, {}):
                msg += redSoap + str(member_dict["Wraith"]) + " sin."
            await self.bot.say(msg)
        else:
            await self.bot.say(member.name + " has not yet been judged.")

    @commands.command(pass_context=True)
    async def bookOfJudgement(self, ctx):
        """sinner leaderboard"""
        server = ctx.message.server
        member_ids = [m.id for m in server.members]
        karma_server_members = [key for key in self.scores.keys()
                                if key in member_ids]
        log.debug("Book of the Guilty:\n\t{}".format(
            karma_server_members))
        names = list(map(lambda mid: discord.utils.get(server.members, id=mid),
                         karma_server_members))
        log.debug("Names:\n\t{}".format(names))
        scores = list(map(lambda mid: self.scores[mid]["Wraith"],
                          karma_server_members))
        log.debug("Sin:\n\t{}".format(scores))
        headers = ["User", "Sin"]
        body = sorted(zip(names, scores), key=lambda tup: tup[1],
                      reverse=True)[:10]
        table = tabulate.tabulate(body, headers, tablefmt="psql")
        await self.bot.say(box(table))
        """co-op leaderboard"""
        server = ctx.message.server
        member_ids = [m.id for m in server.members]
        karma_server_members = [key for key in self.scores.keys()
                                if key in member_ids]
        log.debug("\n\nWarriors of Sunlight:\n\t{}".format(
            karma_server_members))
        names = list(map(lambda mid: discord.utils.get(server.members, id=mid),
                         karma_server_members))
        log.debug("Names:\n\t{}".format(names))
        scores = list(map(lambda mid: self.scores[mid]["Sunlight"],
                          karma_server_members))
        log.debug("Sin:\n\t{}".format(scores))
        headers = ["User", "Sunlight Medals"]
        body = sorted(zip(names, scores), key=lambda tup: tup[1],
                      reverse=True)[:10]
        table = tabulate.tabulate(body, headers, tablefmt="psql")
        await self.bot.say(box(table))


    @commands.group(pass_context=True)
    @checks.mod_or_permissions(manage_messages=True)
    async def karmaset(self, ctx):
        """Manage karma settings"""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)
            return

    @karmaset.command(pass_context=True, name="respond")
    async def _karmaset_respond(self, ctx):
        """Toggles if bot will respond when points get added/removed"""
        if self.settings['RESPOND_ON_POINT']:
            await self.bot.say("Responses disabled.")
        else:
            await self.bot.say('Responses enabled.')
        self.settings['RESPOND_ON_POINT'] = \
            not self.settings['RESPOND_ON_POINT']
        fileIO('data/karma/settings.json', 'save', self.settings)

    async def check_for_score(self, message):
        user = message.author
        content = message.content
        mentions = message.mentions
        if message.author.id == self.bot.user.id:
            return
        if len(mentions) < 1:
            return
        splitted = content.split(" ")
        if len(splitted) >= 1:
            if "!Sunlight" == splitted[0] or "!sunlight" == splitted[0]:
                type = "Sunlight"
            elif "!Wraith" == splitted[0] or "!wraith" == splitted[0]:
                type = "Wraith"
            else:
                return
        else:
            return
        for member in mentions:
            if member == user:
                await self.bot.send_message(message.channel, "Thou canst not judge thyself. ")
            else:
                self._process_scores(member, 1, type)
                if self.settings['RESPOND_ON_POINT']:
                    whiteSoap = str(discord.utils.get(self.bot.get_all_emojis(), id="515521115607662593")) 
                    redSoap = str(discord.utils.get(self.bot.get_all_emojis(), id="515521115762851840")) 
                    if type == "Sunlight":
                        msg = whiteSoap
                    else:
                        msg = redSoap
                    msg += "{} now has {} points.".format(
                        member.name, self.scores[member.id][type])
                    await self.bot.send_message(message.channel, msg)
                fileIO("data/judgement/scores.json", "save", self.scores)
                return


def check_folder():
    if not os.path.exists("data/judgement"):
        print("Creating data/judgement folder...")
        os.makedirs("data/judgement")


def check_file():
    scores = {}
    settings = {"RESPOND_ON_POINT": True}

    f = "data/judgement/scores.json"
    if not fileIO(f, "check"):
        print("Creating default judgement's scores.json...")
        fileIO(f, "save", scores)

    f = "data/judgement/settings.json"
    if not fileIO(f, "check"):
        print("Creating default judgement's scores.json...")
        fileIO(f, "save", settings)


def setup(bot):
    if tabulate is None:
        raise RuntimeError("Run `pip install tabulate` to use judgement.")
    check_folder()
    check_file()
    n = Judge(bot)
    bot.add_listener(n.check_for_score, "on_message")
    bot.add_cog(n)
