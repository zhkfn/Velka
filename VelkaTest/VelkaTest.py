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

log = logging.getLogger("red.VelkaTest")

class VelkaTest:
    """Keep track of user scores through ![judgement_type] @mention
    For now judgement types are hard coded: Sunlight & Wraith"""

    # Initiate: Load existing scores and settings
    def __init__(self, bot):
        self.bot = bot
        self.scores = fileIO("data/judgement/scores.json", "load")
        self.settingsLoc = ("data/judgement/settings.json")
        self.settings = fileIO(self.settingsLoc, 'load')

    def saveSettings(self):
        fileIO(self.settingsLoc, 'save', self.settings)

    def saveScores(self):
        fileIO("data/judgement/scores.json", "save", self.scores)

    def emote(self, scoreType):
        if self.settings["SCORE_TYPE"][scoreType]["emoteID"] == "0":
            return ""
        return str(discord.utils.get(self.bot.get_all_emojis(), idself.settings["SCORE_TYPE"][scoreType]["emoteID"]))

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
        saveScores(self)

    # Settings
    @commands.group(pass_context=True)
    @checks.mod_or_permissions(manage_messages=True)
    async def velkaset(self, ctx):
        """Manage Velka's settings"""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)
            return

    # Edit score types
    @velkaset.command(pass_context=True, name="scoreEditType")
    async def _velkaset_scoreEditType(self, ctx, scoreType : str):
        """- Edit the categories of scores"""
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
                    if str.isdigit(msg) and int(msg) > 0 and int(msg) < 7:
                        sel = int(msg)
                        await self.bot.say("What value should it be set to?")
                        val = await self.bot.wait_for_message(author=ctx.message.author, timeout=60)
                        if val is None:
                            await self.bot.say("No value given. Quitting edit mode.")
                            return
                        elif sel == 1:
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
                            _velkaset_scoreEditType(self, ctx, scoreType)
                            return
                        saveSettings(self)
                        await self.bot.say("Value saved.")
                        _velkaset_scoreEditType(self, ctx, scoreType)
                        return
                    if msg == "0":
                        await self.bot.say("Quitting edit mode.")
                        return
                    await self.bot.say("Invalid selection. Quitting edit mode.")
                    return
            await self.bot.say("That score type does not exist.")
        else:
            msg ="Which score type would you like to edit?"
            num = 0
            for st in self.settings["SCORE_TYPES"]:
                msg += "\n    " + st["command"]
                num += 1
            if num < 1:
                await self.bot.say("You have not defined any scores yet. Please create one first.")
                return
            await self.bot.say(msg)
            msg = await self.bot.wait_for_message(author=ctx.message.author, timeout=60)
            if msg is None:
                await self.bot.say("No score type selected. Quitting edit mode.")
                return
            if msg.content.lower().strip() == "exit":
                await self.bot.say("Quitting edit mode")
                return
            _velkaset_scoreEditType(msg)

    # Create a new score type
    @velkaset.command(pass_context=True, name="scoreAddType")
    async def _velkaset_scoreAddType(self, ctx, command : str):
        """- Create a new score type to track"""
        if self.scores.get('SCORE_TYPE', 0) == 0:
            self.settings['SCORE_TYPE'] = {}
            saveSettings(self)
        if command:
            if command in self.settings['SCORE_TYPE']:
                await self.bot.say(command + " already exists. Would you like to edit it?")
                msg = await self.bot.wait_for_message(author=ctx.message.author, timeout=60)
                if msg.lower() == "yes" or msg.lower() == "y":
                    _velkaset_scoreEditType(self, ctx, command)
                else:
                    await self.bot.say('No score type was added.')
            else:
                self.settings['SCORE_TYPE'][command] = {"noun":"points", "emoteID":"0", "decayRate":2, "dailyLimit":2, "role":"", "roleCost":0}
                for m in self.scores:
                    self.scores[m][command] = 0
                saveSettings(self)
                saveScores(self)
                await self.bot.say(command + " created.")
                _velkaset_scoreEditType(self, ctx, command)
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
                if msg.lower() == "yes" or msg.lower() == "y":
                    self.settings['SCORE_TYPE'].pop(command)
                    for m in self.scores:
                        self.scores[m].pop(command)
                    saveSettings(self)
                    saveScores(self)
                    await self.bot.say(command + " has been deleted.")
                else:
                    await self.bot.say('No score types were deleted.')
            else:
                await self.bot.say('That score type does not exist.')
        else:
            await self.bot.say('Please type an existing score type command after "scoreDeleteType".')

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
    n = VelkaTest(bot)
    bot.add_listener(n.check_for_score, "on_message")
    bot.add_cog(n)
