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
import datetime
try:
    import tabulate
except:
    tabulate = None

log = logging.getLogger("red.judgement")

class Velka:
    """Keep track of user scores through ![judgement_type] @mention"""

    # Initiate: Load existing scores and settings
    def __init__(self, bot):
        self.bot = bot
        self.scores = fileIO("data/judgement/scores.json", "load")
        self.timeout = fileIO("data/judgement/timeout.json", "load")
        self.settingsLoc = ("data/judgement/settings.json")
        self.settings = fileIO(self.settingsLoc, 'load')
        if "DAILY_LIMIT" not in self.timeout:
            self.timeout["DAILY_LIMIT"] = {}
        
    # Method for storing and adding points
    async def _process_scores(self, member, server, score_to_add, judgement_type):
        member_id = member.id
        score = 0
        if member_id in self.scores:
            if judgement_type in self.scores.get(member_id, {}):
                if not str.isdigit(str(self.scores[member_id][judgement_type])): 
                    self.scores[member_id][judgement_type] = 0
                if self.scores[member_id][judgement_type] + score_to_add <= 0:
                    self.scores[member_id][judgement_type] = 0
                    total = 0
                    for score in self.scores[member_id]:
                        total += self.scores[member_id][score]
                    if total <= 0 and score_to_add < 0:
                        self.scores.pop(member_id)
                else:
                    self.scores[member_id][judgement_type] += score_to_add
                    score = self.scores[member_id][judgement_type]
            else:
                self.scores[member_id][judgement_type] = score_to_add
                score = self.scores[member_id][judgement_type]
        else:
            self.scores[member_id] = {}
            for st in self.settings["SCORE_TYPE"]:
                self.scores[member_id][st] = 0
            self.scores[member_id][judgement_type] = score_to_add
            score = self.scores[member_id][judgement_type]
        role = self.settings['SCORE_TYPE'][judgement_type]['role']
        roleCost = self.settings['SCORE_TYPE'][judgement_type]['roleCost']
        if role != "" and roleCost > 0:
            if int(score) >= int(roleCost):
                await self.addRole(server, member, role)
            else:
                await self.remRole(server, member, role)
        self.saveScores()
        
    # Method for adding roles
    async def addRole(self, server, user, role : str):
        role_obj = discord.utils.get(server.roles, name=role)
        if role_obj is None:
            return False
        await self.bot.add_roles(user, role_obj) 
        return True
    
    # Method for removing roles
    async def remRole(self, server, user, role : str):
        role_obj = discord.utils.get(server.roles, name=role)
        if role_obj is None:
            return False
        await self.bot.remove_roles(user, role_obj) 
        return True

    # Give out points to users
    async def check_for_score(self, message):
        user = message.author
        content = message.content
        mentions = message.mentions
        if message.author.id == self.bot.user.id:
            return
        if message.channel.is_private:
            return
        if len(mentions) < 1:
            return
        splitted = content.split(" ")
        if len(splitted) >= 1:
            command = splitted[0].lower()
            scoreType = ""
            for st, s in self.settings['SCORE_TYPE'].items():
                if "!"+st.lower() == splitted[0].lower():
                    scoreType = st
                    break
            if scoreType == "":
                return
        else:
            return
        for member in mentions:
            if member == user and self.settings['DEBUG'] == False:
                await self.bot.send_message(message.channel, "Thou canst not judge thyself.")
            else:
                if self.settings['DEBUG'] == False:
                    if member.id in self.timeout["COOLDOWN"]:
                        await self.bot.send_message(message.channel, member.name + " has been judged recently. Please wait a while longer.")
                        return
                    if scoreType in self.timeout["DAILY_LIMIT"]:
                        if member.id in self.timeout["DAILY_LIMIT"][scoreType]:
                            limit = self.settings["SCORE_TYPE"][scoreType]["dailyLimit"]
                            amt = self.timeout["DAILY_LIMIT"][scoreType][member.id]
                            if amt >= limit:
                                msg = member.name + " has already recieved the maximum "
                                msg += self.settings['SCORE_TYPE'][scoreType]["noun"] + " for " + scoreType
                                msg += " today."
                                await self.bot.send_message(message.channel, msg)
                                return
                            else:
                                self.timeout["DAILY_LIMIT"][scoreType][member.id] = amt + 1
                        else:
                            self.timeout["DAILY_LIMIT"][scoreType][member.id] = 1
                    else:
                        self.timeout["DAILY_LIMIT"][scoreType] = {}
                        self.timeout["DAILY_LIMIT"][scoreType][member.id] = 1
                    self.saveTimeout()
                await self._process_scores(member, message.server, 1, scoreType)
                self.timeout["COOLDOWN"][member.id] = int(time.time())
                if self.settings['RESPOND_ON_POINT']:
                    if str(self.scores[member.id][scoreType]) == "1":
                        noun = self.settings['SCORE_TYPE'][scoreType]["noun_s"]
                    else:
                        noun = self.settings['SCORE_TYPE'][scoreType]["noun"]
                    msg = "{}{} now has {} {}.".format(
                        self.emote(scoreType), member.name,
                        self.scores[member.id][scoreType], noun)
                    await self.bot.send_message(message.channel, msg)

    # Credit
    @commands.command(pass_context=True)
    async def credit(self, ctx):
        """Credits for Velka"""  
        await self.bot.say("Art: https://www.deviantart.com/thequietsoul21\nCoding: https://github.com/zhkfn/Velka") 
        
    @commands.command(pass_context=True)
    async def velkaHelp(self, ctx):
        """More help with using Velka"""
        msg = "Velka can award points to other users and keep track of scores with a leaderboard. "
        msg += "Points decay weekly to encourage continuous participation. "
        msg += "Achieving certain point thresholds can award you special roles.\n\nCommands:\n"
        msg += "`!judgement <@user>` Check how many points you have. If another user is "
        msg += "mentioned, it will show their score instead.\n"
        msg += "`!book` Show leaderboards.\n"
        for st in self.settings["SCORE_TYPE"]:
            msg += "`!" + st + " <@user>` Award " + st + " point.\n"
        msg += "`!credits` Display Velka's credits.\n"
        msg += "`!velkaset` Change Velka's settings (mods only)."
        await self.bot.say(msg)
        
                    
    # Check user score
    @commands.command(pass_context=True)
    async def judgement(self, ctx):
        """Checks a user's judgement points"""
        member = ctx.message.author
        mentions = ctx.message.mentions
        if len(mentions) > 0:
            member = mentions[0]
        if self.scores.get(member.id, 0) != 0:
            member_dict = self.scores[member.id]
            msg = "Judgement for " + member.name + ":"
            for st, s in self.settings["SCORE_TYPE"].items():
                if str(member_dict[st]) == "1":
                    noun = s["noun_s"]
                else:
                    noun = s["noun"]
                msg += "\n" + self.emote(st) + str(member_dict[st]) + " " + noun + "."
            await self.bot.say(msg)
        else:
            await self.bot.say(member.name + " has not yet been judged.")

    # Leaderboard
    @commands.command(pass_context=True, no_pm=True)
    async def book(self, ctx):
        """leaderboard"""
        server = ctx.message.server
        splitted = ctx.message.content.split(" ")
        if len(splitted) >= 2:
            scoreType = splitted[1]
            await self.Leaderboard(scoreType, server)
        else:
            msg = "Which leaderboard would you like to see?"
            for st in self.settings["SCORE_TYPE"]:
                msg += "\n    " + st
            await self.bot.say(msg)
            msg = await self.bot.wait_for_message(author=ctx.message.author, timeout=60)
            if msg is None:
                return
            await self.Leaderboard(msg.content, server)
    
    async def Leaderboard(self, scoreType, server):
        if scoreType in self.settings['SCORE_TYPE']:
            member_ids = [m.id for m in server.members]
            karma_server_members = [key for key in self.scores.keys() if key in member_ids and self.scores[key][scoreType] > 0]
            names = list(map(lambda mid: discord.utils.get(server.members, id=mid), karma_server_members))
            scores = list(map(lambda mid: self.scores[mid][scoreType],karma_server_members))
            noun = self.settings['SCORE_TYPE'][scoreType]["noun"]
            headers = [noun, "User"]
            body = sorted(zip(scores, names), key=lambda tup: tup[0], reverse=True)[:10]
            table = tabulate.tabulate(body, headers, tablefmt="psql")
            await self.bot.say("Book of " + scoreType +" "+ noun + ":")
            await self.bot.say(box(table))
        else:
            await self.bot.say("That leaderboard does not exist.")
    
    async def weeklyDecay(self, server):
        for st, s in self.settings["SCORE_TYPE"].items():
            for mid in list(self.scores.keys()):
                member = discord.utils.get(server.members, id=mid)
                if member is None:
                    self.scores.pop(mid)
                else:
                    decay = s["decayRate"]
                    decay *= -1
                    await self._process_scores(member, server, s["decayRate"], st)
        self.saveScores()
                    
    def dailyLimitReset(self):
        for st in list(self.timeout["DAILY_LIMIT"].keys()):
            self.timeout["DAILY_LIMIT"].pop(st)
        self.saveTimeout()
            
    def cooldownLoop(self):
        curTime = int(time.time());
        if "COOLDOWN" not in self.timeout:
            self.timeout["COOLDOWN"] = {}
        else:
            for mid in list(self.timeout["COOLDOWN"].keys()):
                if curTime - self.timeout["COOLDOWN"][mid] > self.settings["COOLDOWN"]:
                    self.timeout["COOLDOWN"].pop(mid)
        self.saveTimeout()
    
    
    async def loop(self):
        while True:
            self.cooldownLoop()
            if datetime.datetime.today().weekday() != self.timeout["DAY"]:
                self.dailyLimitReset()
                if datetime.datetime.today().weekday() < self.timeout["DAY"]:
                    server = self.bot.get_server(self.settings["SERVER"])
                    await self.weeklyDecay(server)
                self.timeout["DAY"] = datetime.datetime.today().weekday()
                self.saveTimeout()
            await asyncio.sleep(10)

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
        """Toggles if Velka will respond when points are awarded"""
        if 'RESPOND_ON_POINT' not in self.settings:
            self.settings['RESPOND_ON_POINT'] = True
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
        """Toggles debug mode - award yourself points with no limits"""
        if 'DEBUG' not in self.settings:
            self.settings['DEBUG'] = True
        if self.settings['DEBUG']:
            await self.bot.say("Debug mode disabled.")
        else:
            await self.bot.say('Debug mode enabled.')
        self.settings['DEBUG'] = \
            not self.settings['DEBUG']
        self.saveSettings()
        
    # Set the server?
    @velkaset.command(pass_context=True, name="server", no_pm=True)
    async def _velkaset_server(self, ctx):
        """Sets the server Velka will use"""
        self.settings["SERVER"] = ctx.message.server.id;
        self.saveSettings()
        await self.bot.say("Active server set to " + ctx.message.server.name)
    
    # Edit score types
    @velkaset.command(pass_context=True, name="scoreEditType")
    async def _velkaset_scoreEditType(self, ctx, scoreType : str):
        """Edit the categories of scores"""
        await self.ScoreEditType(ctx, scoreType)
            
    # Edit score types
    async def ScoreEditType(self, ctx, scoreType : str):
        if scoreType:
            if scoreType in self.settings['SCORE_TYPE']:
                st = scoreType
                msg = "Currently Editing " + st + ".\n"
                msg += "Which property do you want to edit?"
                msg += "\n    1. Plural Counter Noun: " + str(self.settings["SCORE_TYPE"][st]["noun"])
                msg += "\n    2. Singular Counter Noun: "
                if "noun_s" in self.settings["SCORE_TYPE"][st]:
                    msg += str(self.settings["SCORE_TYPE"][st]["noun_s"])
                else:
                    msg += str(self.settings["SCORE_TYPE"][st]["noun"])
                msg += "\n    3. Emote ID: " + str(self.settings["SCORE_TYPE"][st]["emoteID"])
                msg += "\n    4. Weekly Decay Rate: " + str(self.settings["SCORE_TYPE"][st]["decayRate"])
                msg += "\n    5. Daily Limit: " + str(self.settings["SCORE_TYPE"][st]["dailyLimit"])
                msg += "\n    6. Award Role: " + str(self.settings["SCORE_TYPE"][st]["role"])
                msg += "\n    7. Role Cost: " + str(self.settings["SCORE_TYPE"][st]["roleCost"])
                msg += "\n    0. Exit"
                await self.bot.say(msg)
                msg = await self.bot.wait_for_message(author=ctx.message.author, timeout=60)
                if msg is None:
                    await self.bot.say("Nothing selected. Quitting edit mode.")
                    return
                msg = msg.content
                if str.isdigit(msg) and int(msg) > 0 and int(msg) < 8:
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
                        self.settings["SCORE_TYPE"][st]["noun_s"] = val
                    elif sel == 3:
                        self.settings["SCORE_TYPE"][st]["emoteID"] = val
                    elif sel == 6:
                        self.settings["SCORE_TYPE"][st]["role"] = val
                    elif str.isdigit(val):
                        if sel == 4:
                            self.settings["SCORE_TYPE"][st]["decayRate"] = int(val)
                        elif sel == 5:
                            self.settings["SCORE_TYPE"][st]["dailyLimit"] = int(val)
                        elif sel == 7:
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
        """Set the cooldown timer between points awarded to one person."""
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
        """Create a new score type to track"""
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
                self.settings['SCORE_TYPE'][command] = {"noun":"points", "noun_s":"point", "emoteID":"0", "decayRate":2, "dailyLimit":2, "role":"", "roleCost":0}
                for m in self.scores:
                    self.scores[m][command] = 0
                self.saveSettings()
                self.saveScores()
                await self.bot.say(command + " created.")
                await self.ScoreEditType(ctx, command)
        else:
            await self.bot.say('Please type a unique score type command name after "scoreAddType".')
    
    # delete an existing score type
    @velkaset.command(pass_context=True, name="scoreDeleteType")
    async def _velkaset_scoreDeleteType(self, ctx, command : str):
        """Delete an existing score type"""
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
            
    # Reset daily limits
    @velkaset.command(pass_context=True, name="resetDailyLimits")
    async def _velkaset_resetDailyLimits(self, ctx):
        """[debugging] Reset todays limits for all users"""
        self.dailyLimitReset()   
        await self.bot.say("Daily limits reset.")
            
    # Redo weekly decay
    @velkaset.command(pass_context=True, name="decayScores")
    async def _velkaset_decayScores(self, ctx):
        """[debugging] Decay all user scores by the weekly decay rate."""
        await self.weeklyDecay(ctx.message.server)
        await self.bot.say("Scores have been decayed.")
       
    
    # Edit a user score
    @velkaset.command(pass_context=True, name="editUserScore")
    async def _velkaset_editUserScore(self, ctx):
        """Manage a user's scores"""
        await self.EditUserScore(ctx)
    
    # Edit a user score
    async def EditUserScore(self, ctx):
        if len(ctx.message.mentions) != 1:
            await self.bot.say('Please mention a user after "editUserScore"')
            return
        member = ctx.message.mentions[0]
        if self.scores.get(member.id, 0) != 0:
            member_dict = self.scores[member.id]
            msg = "Judgement for " + member.name + ":"
            for st, s in member_dict.items():
                msg += "\n   " + st + " : " + str(s)
            msg += "\nWhich score would you like to edit?"
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
                    await self._process_scores(member, ctx.message.server, int(msg) - member_dict[scoreType], scoreType)
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
                await self._process_scores(member, ctx.message.server, 0, list(self.settings["SCORE_TYPE"].keys())[0])
                await self.editUserScore(ctx)
    # Helper functions
    
    def saveSettings(self):
        fileIO(self.settingsLoc, 'save', self.settings)
        
    def saveScores(self):
        fileIO("data/judgement/scores.json", "save", self.scores)
    
    def saveTimeout(self):
        fileIO("data/judgement/timeout.json", "save", self.timeout)
        
    def emote(self, scoreType):
        if self.settings["SCORE_TYPE"][scoreType]["emoteID"] == "0":
            return ""
        return str(discord.utils.get(self.bot.get_all_emojis(), id=str(self.settings["SCORE_TYPE"][scoreType]["emoteID"])))
    
def check_folder():
    if not os.path.exists("data/judgement"):
        print("Creating data/judgement folder...")
        os.makedirs("data/judgement")


def check_file():
    scores = {}
    settings = {"RESPOND_ON_POINT": True, "DEBUG": False, "COOLDOWN":300}
    timeout = {"DAY":datetime.datetime.today().weekday()}

    f = "data/judgement/scores.json"
    if not fileIO(f, "check"):
        print("Creating default scores.json...")
        fileIO(f, "save", scores)
        
    f = "data/judgement/settings.json"
    if not fileIO(f, "check"):
        print("Creating default settings.json...")
        fileIO(f, "save", settings)

    f = "data/judgement/timeout.json"
    if not fileIO(f, "check"):
        print("Creating default timeout.json...")
        fileIO(f, "save", timeout)


def setup(bot):
    if tabulate is None:
        raise RuntimeError("Run `pip install tabulate` to use judgement.")
    check_folder()
    check_file()
    n = Velka(bot)
    bot.add_listener(n.check_for_score, "on_message")
    loop = asyncio.get_event_loop()
    loop.create_task(n.loop())
    bot.add_cog(n)
