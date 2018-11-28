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
    

    # Settings
    @commands.group(pass_context=True)
    @checks.mod_or_permissions(manage_messages=True)
    async def velkaset(self, ctx):
        """Manage Velka's settings"""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)
            return
    
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
                #self.settings['SCORE_TYPE'][command] = {"noun":"points", "emoteID":"0", "decayRate":2, "dailyLimit":2, "role":"", "roleCost":0}
                #for m in self.scores:
                #    self.scores[m][command] = 0
                #saveSettings(self)
                #saveScores(self)
                await self.bot.say(command + " created.")
                #_velkaset_scoreEditType(self, ctx, command)
        else:
            await self.bot.say('Please type a unique score type command name after "scoreAddType".')
            
    # Helper Functions
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
