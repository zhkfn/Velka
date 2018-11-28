import discord
from discord.ext import commands
from cogs.utils.dataIO import fileIO
from cogs.utils.chat_formatting import box
from cogs.utils import checks
from __main__ import send_cmd_help
import logging
import os
import asyncio
import time
try:
    import tabulate
except:
    tabulate = None

log = logging.getLogger("red.judgement")

class Velka:
    """Keep track of user scores through ![judgement_type] @mention
    For now judgement types are hard coded: Sunlight & Wraith"""

    # Initiate: Load existing scores and settings
    def __init__(self, bot):
        self.bot = bot
        self.scores = fileIO("data/judgement/scores.json", "load")
        self.settingsLoc = ("data/judgement/settings.json")
        self.settings = fileIO(self.settingsLoc, 'load')
        
    # Method for storing and adding points
    def _process_scores(self, member, score_to_add, judgement_type):
        member_id = member.id
        if member_id in self.scores:
            if judgement_type in self.scores.get(member_id, {}):
                if self.scores[member_id][judgement_type] - score_to_add <= 0:
                    self.scores[member_id][judgement_type] = 0
                    total = 0
                    for score in self.scores[member_id]:
                        total += score
                    if total <= 0 and score_to_add < 0:
                        self.scores.pop(member_id)
                else:
                    self.scores[member_id][judgement_type] += score_to_add
            else:
                self.scores[member_id][judgement_type] = score_to_add
        else:
            self.scores[member_id] = {}
            for st in self.settings["SCORE_TYPE"]:
                self.scores[member_id][st] = 0
            self.scores[member_id][judgement_type] = score_to_add
        self.saveScores()

    # Give out points to users
    # todo: Obey daily limit
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
            command = splitted[0].lower()
            scoreType = ""
            for st in self.settings['SCORE_TYPE']:
                if "!"+st.lower() == splitted[0].lower():
                    scoreType = st
                    break
            if scoreType == "":
                return
        else:
            return
        for member in mentions:
            if member == user and self.settings['DEBUG'] == False:
                await self.bot.send_message(message.channel, "Thou canst not judge thyself. ")
            else:
                # Add cooldown and daily limit
                self._process_scores(member, 1, scoreType)
                if self.settings['RESPOND_ON_POINT']:
                    msg = "{}{} now has {} {}.".format(
                        self.emote(scoreType), member.name,
                        self.scores[member.id][scoreType],
                        self.settings['SCORE_TYPE'][scoreType]["noun"])
                    await self.bot.say(msg)

    # Check user score
    @commands.command(pass_context=True)
    async def judgement(self, ctx):
        """Checks a user's judgement points"""
        member = ctx.message.author
        member_id = member.id
        if self.scores.get(member.id, 0) != 0:
            member_dict = self.scores[member.id]
            msg = "Judgement for " + member.name + ":"
            for st in self.settings["SCORE_TYPE"]:
                msg += "\n" + self.emote(st) + str(member_dict[st]) + " " + st["noun"] + "."
            await self.bot.say(msg)
        else:
            await self.bot.say(member.name + " has not yet been judged.")

    # Leaderboard
    # todo: Look at score type list
    # todo: separate out score types
    @commands.command(pass_context=True)
    async def bookOfJudgement(self, ctx):
        """leaderboard"""
        server = ctx.message.server
        member_ids = [m.id for m in server.members]
        karma_server_members = [key for key in self.scores.keys()
                                if key in member_ids]
        names = list(map(lambda mid: discord.utils.get(server.members, id=mid),
                         karma_server_members))
        scores = list(map(lambda mid: self.scores[mid]["Wraith"],
                          karma_server_members))
        headers = ["Sin", "user"]
        body = sorted(zip(scores, names), key=lambda tup: tup[1],
                      reverse=True)[:10]
        table = tabulate.tabulate(body, headers, tablefmt="psql")
        await self.bot.say(box(table))
        
    # Decay scores weekly. Delete any users with no score.
    # Take away roles when score too low
    # Assign role based on points

    # Settings
    @commands.group(pass_context=True)
    @checks.mod_or_permissions(manage_messages=True)
    async def velkaset(self, ctx):
        """Manage Velka's settings"""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)
            return
    
    # Should velka respond to points added?
    @velkaset.command(pass_context=True, name="respond")
    async def _velkaset_respond(self, ctx):
        """- Toggles if Velka will respond when points are awarded"""
        if self.settings.get('RESPOND_ON_POINT', 0) == 0:
            self.settings['RESPOND_ON_POINT'] = True
            self.saveSettings()
        if self.settings['RESPOND_ON_POINT']:
            await self.bot.say("Responses disabled.")
        else:
            await self.bot.say('Responses enabled.')
        self.settings['RESPOND_ON_POINT'] = \
            not self.settings['RESPOND_ON_POINT']
        self.saveSettings()
        
    
    # Debug mode?
    @velkaset.command(pass_context=True, name="debug")
    async def _velkaset_debug(self, ctx):
        """- Toggles debug mode - award yourself points with no limits"""
        if 'DEBUG' in self.settings:
        else:
            self.settings['DEBUG'] = True
            self.saveSettings()
        if self.settings['DEBUG']:
            await self.bot.say("Debug mode disabled.")
        else:
            await self.bot.say('Debug mode enabled.')
        self.settings['DEBUG'] = \
            not self.settings['DEBUG']
        self.saveSettings()
    
    # Edit score types
    @velkaset.command(pass_context=True, name="scoreEditType")
    async def _velkaset_scoreEditType(self, ctx, scoreType : str):
        """- Edit the categories of scores"""
        await self.ScoreEditType(ctx, scoreType)
            
    # Edit score types
    async def ScoreEditType(self, ctx, scoreType : str):
        if scoreType:
            for st in self.settings["SCORE_TYPE"]:
                if st == scoreType:
                    msg = "Currently Editing " + st + ".\n"
                    msg += "Which property do you want to edit?"
                    msg += "\n    1. Counter Noun: " + str(self.settings["SCORE_TYPE"][st]["noun"])
                    msg += "\n    2. Emote ID: " + str(self.settings["SCORE_TYPE"][st]["emoteID"])
                    msg += "\n    3. Weekly Decay Rate: " + str(self.settings["SCORE_TYPE"][st]["decayRate"])
                    msg += "\n    4. Daily Limit: " + str(self.settings["SCORE_TYPE"][st]["dailyLimit"])
                    msg += "\n    5. Award Role: " + str(self.settings["SCORE_TYPE"][st]["role"])
                    msg += "\n    6. Role Cost: " + str(self.settings["SCORE_TYPE"][st]["roleCost"])
                    msg += "\n    0. Exit"
                    await self.bot.say(msg)
                    msg = await self.bot.wait_for_message(author=ctx.message.author, timeout=60)
                    if msg is None:
                        await self.bot.say("Nothing selected. Quitting edit mode.")
                        return
                    msg = msg.content
                    if str.isdigit(msg) and int(msg) > 0 and int(msg) < 7:
                        sel = int(msg)
                        await self.bot.say("What value should it be set to?")
                        val = await self.bot.wait_for_message(author=ctx.message.author, timeout=60)
                        if val is None:
                            await self.bot.say("No value given. Quitting edit mode.")
                            return
                        val = val.content
                        if sel == 1:
                            self.settings["SCORE_TYPE"][st]["noun"] = val
                        elif sel == 2:
                            self.settings["SCORE_TYPE"][st]["emoteID"] = val
                        elif sel == 5:
                            self.settings["SCORE_TYPE"][st]["role"] = val
                        elif str.isdigit(val):
                            if sel == 3:
                                self.settings["SCORE_TYPE"][st]["decayRate"] = int(val)
                            elif sel == 4:
                                self.settings["SCORE_TYPE"][st]["dailyLimit"] = int(val)
                            elif sel == 6:
                                self.settings["SCORE_TYPE"][st]["roleCost"] = int(val)
                        else:
                            await self.bot.say("Invalid value.")
                            await self.ScoreEditType(ctx, scoreType)
                            return
                        self.saveSettings()
                        await self.bot.say("Value saved.")
                        await self.ScoreEditType(ctx, scoreType)
                        return
                    if msg == "0":
                        await self.bot.say("Quitting edit mode.")
                        return
                    await self.bot.say("Invalid selection. Quitting edit mode.")
                    return
            await self.bot.say("That score type does not exist.")
    
    # Cooldown between awarded points
    @velkaset.command(pass_context=True, name="cooldown")
    async def _velkaset_cooldown(self, ctx):
        """- Set the cooldown timer between points awarded to one person."""
        if 'COOLDOWN' not in self.settings:
            self.settings['COOLDOWN'] = 300
        cd = self.settings['COOLDOWN'];
        await self.bot.say("Cooldown is currently set to " + str(cd) + "s (" + str(cd/60) + "m). How many seconds should it be set to?")
        msg = await self.bot.wait_for_message(author=ctx.message.author, timeout=60)
        if msg is None:
            await self.bot.say("No cooldown value given.")
        elif str.isdigit(msg.content):
            cd = int(msg.content)
            self.settings['COOLDOWN'] = cd
            await self.bot.say("Cooldown set to " + str(cd) + "s.")
            self.saveSettings()
        else:
            await self.bot.say("Invalid cooldown.")
    
    # Create a new score type
    @velkaset.command(pass_context=True, name="scoreAddType")
    async def _velkaset_scoreAddType(self, ctx, command : str):
        """- Create a new score type to track"""
        if self.settings.get('SCORE_TYPE', 0) == 0:
            self.settings['SCORE_TYPE'] = {}
            self.saveSettings()
        if command:
            if command in self.settings['SCORE_TYPE']:
                await self.bot.say(command + " already exists. Would you like to edit it?")
                msg = await self.bot.wait_for_message(author=ctx.message.author, timeout=60)
                if msg is None:
                    await self.bot.say('No score type was added.')
                    return
                msg = msg.content
                if msg.lower() == "yes" or msg.lower() == "y":
                    await self.ScoreEditType(ctx, command)
                else:
                    await self.bot.say('No score type was added.')
            else:
                self.settings['SCORE_TYPE'][command] = {"noun":"points", "emoteID":"0", "decayRate":2, "dailyLimit":2, "role":"", "roleCost":0}
                for m in self.scores:
                    self.scores[m][command] = 0
                self.saveSettings()
                self.saveScores()
                await self.bot.say(command + " created.")
                await self.self.ScoreEditType(ctx, command)
        else:
            await self.bot.say('Please type a unique score type command name after "scoreAddType".')
    
    # delete an existing score type
    @velkaset.command(pass_context=True, name="scoreDeleteType")
    async def _velkaset_scoreDeleteType(self, ctx, command : str):
        """- Delete an existing score"""
        if command:
            if command in self.settings['SCORE_TYPE']:
                await self.bot.say("Are you sure you want to permanently delete " + command + "?")
                msg = await self.bot.wait_for_message(author=ctx.message.author, timeout=60)
                if msg is None:
                    await self.bot.say('No score types were deleted.')
                    return
                msg = msg.content
                if msg.lower() == "yes" or msg.lower() == "y":
                    self.settings['SCORE_TYPE'].pop(command)
                    for m in self.scores:
                        self.scores[m].pop(command)
                    self.saveSettings()
                    self.saveScores()
                    await self.bot.say(command + " has been deleted.")
                else:
                    await self.bot.say('No score types were deleted.')
            else:
                await self.bot.say('That score type does not exist.')
        else:
            await self.bot.say('Please type an existing score type command after "scoreDeleteType".')
    
    # Edit a user score
    @velkaset.command(pass_context=True, name="editUserScore")
    async def _velkaset_editUserScore(self, ctx):
        """- Manage a user's scores"""
        if len(ctx.message.mentions) != 1:
            await self.bot.say('Please mention a user after "editUserScore"')
            return
        member = ctx.message.mentions[0]
        if self.scores.get(member.id, 0) != 0:
            member_dict = self.scores[member.id]
            msg = "Judgement for " + member.name + ":"
            for s in member_dict:
                msg += "\n   " + s + " : " + member_dict[s]
            msg += "Which score would you like to edit?"
            await self.bot.say(msg)
            msg = await self.bot.wait_for_message(author=ctx.message.author, timeout=60)
            if msg is None:
                await self.bot.say("None selected. Quitting.")
                return
            msg = msg.content
            if msg in self.settings["SCORE_TYPE"]:
                scoreType = msg
                await self.bot.say("What should it be set to?")
                msg = await self.bot.wait_for_message(author=ctx.message.author, timeout=60)
                if msg is None:
                    await self.bot.say("No value given. Quitting.")
                    return
                msg = msg.content
                if str.isdigit(msg):
                    _process_scores(self, member, int(msg) - member_dict[scoreType], scoreType)
                    await self.bot.say(scoreType + " is now " + msg)
                else:
                    await self.bot.say("Invalid value.")
            else:
                await self.bot.say("Invalid score type.")
                
        else:
            await self.bot.say(member.name + " has not yet been judged. Would you like to create a new judgement?")
            msg = await self.bot.wait_for_message(author=ctx.message.author, timeout=60)
            if msg is None:
                return
            msg = msg.content
            if msg.lower() == "yes" or msg.lower() == "y":
                _process_scores(self, member, 0, list(self.settings["SCORE_TYPE"].keys())[0])
                _velkaset_editUserScore(self, ctx)
    # Helper functions
    
    def saveSettings(self):
        fileIO(self.settingsLoc, 'save', self.settings)
        
    def saveScores(self):
        fileIO("data/judgement/scores.json", "save", self.scores)
        
    def emote(self, scoreType):
        if self.settings["SCORE_TYPE"][scoreType]["emoteID"] == "0":
            return ""
        return str(discord.utils.get(self.bot.get_all_emojis(), idself.settings["SCORE_TYPE"][scoreType]["emoteID"]))
    
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
    n = Velka(bot)
    bot.add_listener(n.check_for_score, "on_message")
    bot.add_cog(n)
