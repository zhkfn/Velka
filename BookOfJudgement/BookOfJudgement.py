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
        finalscore = 0
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
                    finalscore = self.scores[member_id][judgement_type]
            else:
                self.scores[member_id][judgement_type] = score_to_add
                finalscore = self.scores[member_id][judgement_type]
        else:
            self.scores[member_id] = {}
            for st in self.settings["SCORE_TYPE"]:
                self.scores[member_id][st] = 0
            self.scores[member_id][judgement_type] = score_to_add
            finalscore = self.scores[member_id][judgement_type]
        role = self.settings['SCORE_TYPE'][judgement_type]['role']
        roleCost = self.settings['SCORE_TYPE'][judgement_type]['roleCost']
        if role != "" and roleCost > 0:
            if finalscore >= roleCost:
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

    async def parse_message(self, message):
        if message.author.id == self.bot.user.id:
            return
        if message.channel.is_private:
            return
        if not self.get_prefix(message):
            return
        splitted = message.content.split(" ")
        if len(splitted) < 1:
            return
        command = splitted[0].lower()
        await self.check_for_score(message)
        await self.coop(message, command)
        await self.cancelRequest(message, command)
    
    # Give out points to users
    async def check_for_score(self, message):
        user = message.author
        content = message.content
        mentions = message.mentions
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
        if "CHANNELS" in self.settings and scoreType in self.settings["CHANNELS"]:
            if len(self.settings["CHANNELS"][scoreType]) > 0:
                if message.channel.id not in self.settings["CHANNELS"][scoreType]:
                    await self.bot.send_message(message.channel, "That command is not allowed here.")
                    return
        if scoreType == "sunlight":
            await self.removeRequest(message.server, message.author)
        for member in mentions:
            if member == user and self.settings['DEBUG'] == False and not user.server_permissions.manage_messages:
                await self.bot.send_message(message.channel, "Thou canst not judge thyself.")
            else:
                if self.settings['DEBUG'] == False:
                    if member.id in self.timeout["COOLDOWN"] and not user.server_permissions.manage_messages:
                        await self.bot.send_message(message.channel, member.name + " has been judged recently. Please wait a while longer.")
                        return
                    if scoreType in self.timeout["DAILY_LIMIT"]:
                        if user.id in self.timeout["DAILY_LIMIT"][scoreType]:
                            limit = self.settings["SCORE_TYPE"][scoreType]["dailyLimit"]
                            amt = self.timeout["DAILY_LIMIT"][scoreType][user.id]
                            if amt >= limit and not user.server_permissions.manage_messages:
                                msg = user.name + " has already given the maximum "
                                msg += self.settings['SCORE_TYPE'][scoreType]["noun"] + " for " + scoreType
                                msg += " today."
                                await self.bot.send_message(message.channel, msg)
                                return
                            else:
                                self.timeout["DAILY_LIMIT"][scoreType][user.id] = amt + 1
                        else:
                            self.timeout["DAILY_LIMIT"][scoreType][user.id] = 1
                    else:
                        self.timeout["DAILY_LIMIT"][scoreType] = {}
                        self.timeout["DAILY_LIMIT"][scoreType][user.id] = 1
                    self.saveTimeout()
                pts = 1
                if user.server_permissions.manage_messages:
                    for word in splitted:
                        try:
                            pts = int(word)
                            break
                        except:
                            continue
                await self._process_scores(member, message.server, pts, scoreType)
                self.timeout["COOLDOWN"][member.id] = int(time.time())
                if self.settings['RESPOND_ON_POINT']:
                    if member.id in self.scores and str(self.scores[member.id][scoreType]) == "1":
                        noun = self.settings['SCORE_TYPE'][scoreType]["noun_s"]
                    else:
                        noun = self.settings['SCORE_TYPE'][scoreType]["noun"]
                    msg = "{} {} now has {} {}.".format(
                        self.emote(scoreType), member.name,
                        self.scores[member.id][scoreType], noun)
                    await self.bot.send_message(message.channel, msg)
                    log = "{} awarded {} a {} {} in {}".format(
                        message.author.mention, member.mention, scoreType,
                        self.settings['SCORE_TYPE'][scoreType]["noun_s"],
                        message.channel.mention)
                    await self.bot.send_message(discord.utils.get(message.server.channels, id=self.settings["LOGGING"]), log)
                    await self.leaderboardChannel()

    async def coop(self, message, command):
        if not command[0:5] == "!coop":
            return
        # Check which co-op channel to use
        server = message.server
        requests = discord.utils.get(server.channels, id=self.settings["REQUESTS"])
        chl = message.channel
        if chl.id == self.settings["COOP_CHAT"]:
            if len(message.channel_mentions) < 1:
                await self.bot.send_message(message.channel, "Please mention the co-op area channel you need help in after `" + command + "`.\nEx: `!coop #undead-burg-parish`") 
                return
            reqChannel = message.channel_mentions[0]
            if "CHANNELS" in self.settings and "sunlight" in self.settings["CHANNELS"]:
                if len(self.settings["CHANNELS"]["sunlight"]) > 0:
                    goodChannel = False
                for ch in self.settings["CHANNELS"]["sunlight"]:
                    if reqChannel.id == ch:
                        goodChannel = True
                if reqChannel.id == self.settings["COOP_CHAT"]:
                    goodChannel = False
                if not goodChannel:
                    await self.bot.send_message(message.channel, "That is not a valid channel. Please choose a co-op area channel.")
                    return
                chl = message.channel_mentions[0]
            await self.bot.send_message(message.channel, "A request was posted in {}. Please use {} to organize your co-op.".format(requests.mention, chl.mention))
        # check if channel is allowed
        if chl.id not in self.settings["CHANNELS"]["sunlight"]:
            await self.bot.send_message(message.channel, "That command is not allowed here. Please use a designated co-op channel.") 
            return         
        # Put a message in the current channel
        await self.bot.send_message(chl, "A request for help was posted in {} for {}.".format(requests.mention, message.author.mention))
        # Put a message in the request channel (look for NG)
        ng = 0
        if len(command) > 5:
            ng = int(command[5]) 
        ngText = ""
        if ng > 0:
            ngText = " NG+"
            if ng > 1:
                ngText += str(ng)
        reqMsg = await self.bot.send_message(requests, "{} requests co-op assistance in{} {}.".format(message.author.mention, ngText, chl.mention))
        if "COOP" not in self.timeout:
            self.timeout["COOP"] = {} 
        if message.author.id in self.timeout["COOP"]:
            oldch = discord.utils.get(message.server.channels, id=self.timeout["COOP"][message.author.id]["CH"])
            deleted = await self.removeRequest(message.server, message.author)
            if deleted:
                channel = discord.utils.get(message.server.channels, id=self.settings["LOGGING"])
                await self.bot.send_message(channel, message.author.mention + " removed their co-op request in "+oldch.mention+" by posting another request in" +chl.mention) 
        # save the request to timeout to auto-delete
        self.timeout["COOP"][message.author.id] = {}
        self.timeout["COOP"][message.author.id]["MSG"] = reqMsg.id
        self.timeout["COOP"][message.author.id]["TIME"] = int(time.time())
        self.timeout["COOP"][message.author.id]["CH"] = chl.id
        self.saveTimeout()
        
    async def removeRequest(self, server, author):
        if author.id not in self.timeout["COOP"]:
            return False
        requests = discord.utils.get(server.channels, id=self.settings["REQUESTS"])
        done = False
        try:
            await self.bot.http.delete_message(requests.id, self.timeout["COOP"][author.id]["MSG"])
            done = True
        except:
            pass
        self.timeout["COOP"].pop(author.id)
        self.saveTimeout()
        return done
        
    async def cancelRequest(self, message, command):
        if not command == "!complete":
            return
        if "CHANNELS" in self.settings and "sunlight" in self.settings["CHANNELS"]:
            if len(self.settings["CHANNELS"]["sunlight"]) > 0:
                if message.channel.id in self.settings["CHANNELS"]["sunlight"]:
                    if message.author.id in self.timeout["COOP"]:
                        ch = discord.utils.get(message.server.channels, id=self.timeout["COOP"][message.author.id]["CH"])
                        good = await self.removeRequest(message.server, message.author)
                        if good:
                            await self.bot.send_message(message.channel, "Your co-op request has been removed.")
                            channel = discord.utils.get(message.server.channels, id=self.settings["LOGGING"])
                            await self.bot.send_message(channel, message.author.mention + " removed their co-op request in "+ch.mention) 
                            return
                await self.bot.send_message(message.channel, "There was no co-op request to remove.")
                    

    # Credit
    @commands.command(pass_context=True)
    async def credits(self, ctx):
        """Credits for Velka"""
        if ctx.message.channel.is_private or ctx.message.channel.id == self.settings["SPAM"]:
            embed=discord.Embed(description="__**Credits:**__\n\n**[Art](https://www.deviantart.com/matinee79) \n\n[Coding](https://github.com/zhkfn/Velka)**", color=4614258)
            await self.bot.say(embed=embed)
        else:
            chn = discord.utils.get(ctx.message.server.channels, id=self.settings["SPAM"])
            await self.bot.say("That command is not allowed here. Please use the " + chn.mention + " channel.")
            return

    @commands.command(pass_context=True)
    async def velkaHelp(self, ctx):
        """More help with using Velka"""
        msg = "Velka can award points to other users and keep track of scores with a leaderboard. "
        msg += "Points decay weekly to encourage continuous participation. "
        msg += "Achieving certain point thresholds can award you special roles.\n\nCommands:\n"
        msg += "`!judgement <@user>` Check how many points a user has. "
        msg += "Leave `<@user>` blank for your own score.\n"
        msg += "`!book` Show leaderboards.\n"
        for st in self.settings["SCORE_TYPE"]:
            msg += "`!" + st + " <@user>` Award " + st + " point.\n"
        msg += "*Note: You can mention multiple users to award several points at once!*\n"
        msg += "`!credits` Display Velka's credits.\n"
        msg += "`!velkaset` Change Velka's settings (mods only)."
        await self.bot.send_message(ctx.message.author, msg)
    
    async def help(self, server, channel, decay=False):
        emote1 = self.emote(list(self.settings["SCORE_TYPE"].keys())[0])
        emote2 = self.emote(list(self.settings["SCORE_TYPE"].keys())[1])
        
        msg = emote1 + "To check thine sins and victories, speaketh:```!judgement```\n"
        msg += emote2 + "To view the judgement of another, speaketh:```!judgement @<user>```\n"
        msg += emote1 + "To view the most victorious, speaketh:\n```!book sunlight```\n"
        msg += emote2 + "To view the most wretched, speaketh:\n```!book wraith```\n"
        if decay:
            msg += "\n\n{}{} **__The week has ended.__** {}{}".format(emote1, emote2, emote2, emote1) 
            msg += "\nAll scores have been decayed.\n\n"
        await self.bot.send_message(channel,msg)
        if decay:
            for st in self.settings["SCORE_TYPE"]:
                await self.Leaderboard(st, server, channel)

    # Check user score
    @commands.command(pass_context=True)
    async def judgement(self, ctx):
        """Checks a user's judgement points"""
        if not ctx.message.channel.is_private and not ctx.message.channel.id == self.settings["SPAM"]:
            chn = discord.utils.get(ctx.message.server.channels, id=self.settings["SPAM"])
            await self.bot.say("That command is not allowed here. Please use the " + chn.mention + " channel.")
            return
        member = ctx.message.author
        mentions = ctx.message.mentions
        if len(mentions) > 0:
            member = mentions[0]
        if self.scores.get(member.id, 0) != 0:
            member_dict = self.scores[member.id]
            msg = "Judgement for " + member.name + ":"
            for st, s in self.settings["SCORE_TYPE"].items():
                if int(member_dict[st]) < 1:
                    continue 
                if str(member_dict[st]) == "1":
                    noun = s["noun_s"]
                else:
                    noun = s["noun"]
                msg += "\n   {} {} {}.".format(self.emote(st), str(member_dict[st]), noun)
        else:
            msg = member.name + " has not yet been judged."
        msg += "\n\n{} can still give away:".format(member.name)
        cmltv = 0
        for st, s in self.settings["SCORE_TYPE"].items():
            limit = self.settings["SCORE_TYPE"][st]["dailyLimit"]
            amt = 0
            if st in self.timeout["DAILY_LIMIT"] and member.id in self.timeout["DAILY_LIMIT"][st]:
                amt = self.timeout["DAILY_LIMIT"][st][member.id]
            total = limit-amt
            if total < 1:
                continue
            cmltv += total
            if total == 1:
                noun = s["noun_s"]
            else:
                noun = s["noun"]
            
            msg += "\n  {} {} {}.".format(self.emote(st), str(total), noun)
        if cmltv < 1:
            msg += "\n  nothing. " + u"\U0001F622"
        await self.bot.say(msg)

    # Leaderboard
    @commands.command(pass_context=True, no_pm=True)
    async def book(self, ctx):
        """leaderboard"""
        if not ctx.message.channel.id == self.settings["SPAM"]:
            chn = discord.utils.get(ctx.message.server.channels, id=self.settings["SPAM"])
            await self.bot.say("That command is not allowed here. Please use the " + chn.mention + " channel.")
            return
        server = ctx.message.server
        splitted = ctx.message.content.split(" ")
        if len(splitted) >= 2:
            scoreType = splitted[1]
            await self.Leaderboard(scoreType, server, ctx.message.channel)
        else:
            msg = "Which leaderboard would you like to see?"
            for st in self.settings["SCORE_TYPE"]:
                msg += "\n    " + st
            await self.bot.say(msg)
            msg = await self.bot.wait_for_message(author=ctx.message.author, timeout=60)
            if msg is None:
                return
            await self.Leaderboard(msg.content, server, ctx.message.channel)
    
    async def Leaderboard(self, scoreType, server, channel):
        if scoreType in self.settings['SCORE_TYPE']:
            member_ids = [m.id for m in server.members]
            karma_server_members = [key for key in self.scores.keys() if key in member_ids and self.scores[key][scoreType] > 0]
            names = list(map(lambda mid: discord.utils.get(server.members, id=mid).name[:12], karma_server_members))
            scores = list(map(lambda mid: self.scores[mid][scoreType],karma_server_members))
            noun = self.settings['SCORE_TYPE'][scoreType]["noun"]
            headers = ['Pts', "User"]
            body = sorted(zip(scores, names), key=lambda tup: tup[0], reverse=True)[:10]
            table = tabulate.tabulate(body, headers, tablefmt="psql")
            msg = "{} **[Book of {}]** {}\n".format(
                        self.emote(scoreType), noun.capitalize(),
                        self.emote(scoreType))
            await self.bot.send_message(channel, msg + box(table))
        else:
            await self.bot.say("That leaderboard does not exist.")
    
    async def leaderboardChannel(self):
        server = self.bot.get_server(self.settings["SERVER"])
        if "LEADER" not in self.settings:
            return
        channel = discord.utils.get(server.channels, id=self.settings["LEADER"])
        mgs = [] #Empty list to put all the messages in the log
        try:
            async for x in self.bot.logs_from(channel, limit = 10):
                mgs.append(x)
            await self.bot.delete_messages(mgs)
        except:
            pass
        for st in self.settings["SCORE_TYPE"]:
            await self.Leaderboard(st, server, channel)
    
    async def weeklyDecay(self, server):
        for st, s in self.settings["SCORE_TYPE"].items():
            for mid in list(self.scores.keys()):
                member = discord.utils.get(server.members, id=mid)
                if member is None:
                    self.scores.pop(mid)
                else:
                    decay = s["decayRate"]
                    decay *= -1
                    await self._process_scores(member, server, decay, st)
        self.saveScores()
        await self.bot.send_message(discord.utils.get(server.channels, id=self.settings["LOGGING"]), "Scores have been decayed!")

    def dailyLimitReset(self):
        for st in list(self.timeout["DAILY_LIMIT"].keys()):
            self.timeout["DAILY_LIMIT"].pop(st)
        self.saveTimeout()

    def cooldownLoop(self):
        curTime = int(time.time());
        if "COOLDOWN" not in self.timeout:
            self.timeout["COOLDOWN"] = {}
            self.saveTimeout()
        else:
            for mid in list(self.timeout["COOLDOWN"].keys()):
                if curTime - self.timeout["COOLDOWN"][mid] > self.settings["COOLDOWN"]:
                    self.timeout["COOLDOWN"].pop(mid)
                    self.saveTimeout()
        
    async def coopLoop(self, server):
        curTime = int(time.time());
        if "COOP" not in self.timeout:
            self.timeout["COOP"] = {}
            self.saveTimeout()
        else:
            for mid in list(self.timeout["COOP"].keys()):
                if curTime - self.timeout["COOP"][mid]["TIME"] > 3600:
                    if "NOTICE" not in self.timeout["COOP"][mid]:
                        ch = discord.utils.get(server.channels, id=self.timeout["COOP"][mid]["CH"])
                        auth = discord.utils.get(server.members, id=mid)
                        if auth is none:
                            self.timeout["COOP"].pop(mid)
                            self.saveTimeout()
                            return
                        await self.bot.send_message(ch, auth.mention + ", do you still need help? If not, please award those who helped you with `!sunlight @<user>` or mark the request completed with `!complete`.")
                        self.timeout["COOP"][mid]["NOTICE"] = True
                        self.saveTimeout()
                    elif curTime - self.timeout["COOP"][mid]["TIME"] > 10800:
                        ch = discord.utils.get(server.channels, id=self.timeout["COOP"][mid]["CH"])
                        auth = discord.utils.get(server.members, id=mid)
                        await self.bot.send_message(ch, auth.mention + ", your co-op request has timed out. If you still need help, please use the `!coop` command again.")
                        await self.removeRequest(server, auth)
                        channel = discord.utils.get(server.channels, id=self.settings["LOGGING"])
                        await self.bot.send_message(channel, u"\u274C" + auth.mention + "'s co-op request in" + ch.mention + " has timed out." ) 
                
    
    async def loop(self):
        while True:
            self.cooldownLoop()
            server = self.bot.get_server(self.settings["SERVER"])
            if server is None:
                await asyncio.sleep(30)
                continue 
            await self.coopLoop(server)
            if datetime.datetime.today().weekday() != self.timeout["DAY"]:
                day = self.timeout["DAY"]
                self.timeout["DAY"] = datetime.datetime.today().weekday()
                self.saveTimeout()
                if datetime.datetime.today().weekday() < day:
                    await self.weeklyDecay(server)
                spam = discord.utils.get(server.channels, id=self.settings["SPAM"])
                await self.help(server, spam, datetime.datetime.today().weekday() < day)
                channel = discord.utils.get(server.channels, id=self.settings["LOGGING"])
                for st in self.settings["SCORE_TYPE"]:
                    await self.Leaderboard(st, server, channel)
                await self.bot.send_message(channel, "Daily Backup:")
                await self.backup(channel)
                await self.bot.send_message(channel, "Resetting Daily Limits")
                self.dailyLimitReset()
            await asyncio.sleep(30)

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

    # Set up the Bot
    @velkaset.command(pass_context=True, name="setup", no_pm=True)
    async def _velkaset_setup(self, ctx):
        """Sets up Velka"""
        await self.setup(ctx.message.server, ctx.message.channel, ctx.message.author)
  
    async def setup(self, server, channel, author):
        if self.settings["SERVER"] != server.id:
            await self.bot.say("This is a new server. Do you want to set up Velka on this server?")
            msg = await self.bot.wait_for_message(author=author, timeout=60)
            if msg is None:
                await self.bot.say('Exiting Setup')
                return
            msg = msg.content
            if msg.lower() == "yes" or msg.lower() == "y":
                self.settings["SERVER"] != server.id;
                self.saveSettings()
                await self.bot.say("Active server set to "+server.name)
            else:
                await self.bot.say('Exiting Setup')
        msg = "__Channel Settings__\nWhich channel would you like to set up?"
        msg += "\n  1. Logging Channel"
        msg += "\n  2. Spam channel"
        msg += "\n  3. Co-op Requests"
        msg += "\n  4. Co-op Chat"
        msg += "\n  5. Leaderboard" 
        ct = 6
        for st in self.settings["SCORE_TYPE"]:
            msg += "\n  {}. !{} channels".format(str(ct), st)
            ct += 1
        await self.bot.say(msg)
        msg = await self.bot.wait_for_message(author=author, timeout=60)
        if msg is None:
            await self.bot.say('Exiting Setup')
            return
        msg = msg.content
        if str.isdigit(msg) and int(msg) > 0 and int(msg) < ct:
            if int(msg) == 1:
                await self.setChannel(server,channel, author, "LOGGING", "logging")
            elif int(msg) == 2:
                await self.setChannel(server, channel, author, "SPAM", "bot spam")
            elif int(msg) == 3:
                await self.setChannel(server, channel, author, "REQUESTS", "co-op requests")
            elif int(msg) == 4:
                await self.setChannel(server, channel, author, "COOP_CHAT", "co-op chat")
            elif int(msg) == 5:
                await self.setChannel(server, channel, author, "LEADER", "leaderboard")
            else:
                st = list(self.settings["SCORE_TYPE"].keys())[int(msg)-6]
                if "CHANNELS" not in self.settings:
                    self.settings["CHANNELS"] = {}
                    self.saveSettings()
                if st in self.settings["CHANNELS"] and len(self.settings["CHANNELS"][st])>0:
                    msg = "Here are the channels where the !"+st+" command is allowed:"
                    for ch in list(self.settings["CHANNELS"][st]):
                        chn = discord.utils.get(server.channels, id=ch)
                        if chn is None:
                            self.settings["CHANNELS"][st].pop(ch)
                        else:
                            msg += "\n  " + chn.name
                    msg += "\nType an existing channel to remove it, type a new channel to add it."
                    await self.bot.say(msg)
                else:
                    self.settings["CHANNELS"][st] = []
                    self.saveSettings()
                    await self.bot.say("There are no channels set up for !" +st+". Type a channel name to add it.")
                msg = await self.bot.wait_for_message(author=author, timeout=60)
                if msg is None:
                    await self.bot.say('Exiting Setup')
                    return
                msg = msg.content
                ch = discord.utils.get(server.channels, name=msg)
                if ch is None:
                    await self.bot.say("That channel doesn't exist. Exiting setup.")
                    return
                if ch.id in self.settings["CHANNELS"][st]:
                    self.settings["CHANNELS"][st].remove(ch.id)
                    await self.bot.say(ch.name + " has been removed.")
                else:
                    self.settings["CHANNELS"][st].append(ch.id)
                    await self.bot.say(ch.name + " has been added.")
                self.saveSettings()
                await self.setup(server, channel, author)
        else:
            await self.bot.say('Invalid Selection. Exiting Setup.')
            
            
    async def setChannel(self, server, channel, author, keyword, desc):
        if keyword in self.settings:
            chn = discord.utils.get(server.channels, id=self.settings[keyword])
            if chn is None:
                self.settings.pop(keyword)
                self.saveSettings()
                await self.bot.send_message(channel, "The " + desc + " channel has not yet been set up. What should it be set to?")
            else:
                await self.bot.send_message(channel, "The " + desc + " channel is currently set to "
                                 + chn.name + ". What should it be set to?")
        else:
            await self.bot.send_message(channel, "The " + desc + " channel has not yet been set up. What should it be set to?")
        msg = await self.bot.wait_for_message(author=author, timeout=60)
        if msg is None:
            await self.bot.send_message(channel, 'Exiting Setup')
            return
        msg = msg.content
        ch = discord.utils.get(server.channels, name=msg)
        if ch is None:
            await self.bot.send_message(channel, "That channel doesn't exist. Exiting setup.")
            return
        self.settings[keyword] = ch.id
        self.saveSettings()
        await self.bot.send_message(channel, desc.capitalize() + " channel set to " + ch.name)
        await self.setup(server, channel, author)
        
    @velkaset.command(pass_context=True, name="stats")
    async def _velkaset_stats(self, ctx):
        server = self.bot.get_server(self.settings["SERVER"])
        msg = "__**Total points currently awarded:**__" 
        for st, s in self.settings["SCORE_TYPE"].items():
            total = 0
            for mid in list(self.scores.keys()):
                member = discord.utils.get(server.members, id=mid)
                if member is not None:
                    if st in self.scores[mid]:
                        total += self.scores[mid][st]
            msg += "\n{}: {}".format(st, total) 
        await self.bot.say(msg)
    
    
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
        
    # Test Weekly loop
    @velkaset.command(pass_context=True, name="testWeek")
    async def _velkaset_testWeek(self, ctx):
        """[debugging] Test weekly decay and logging."""
        self.timeout["DAY"] = 8
        self.saveTimeout()
       
    # Backup
    @velkaset.command(pass_context=True, name="backup")
    async def _velkaset_backup(self, ctx):
        """Back up scores and settings"""
        await self.backup(ctx.message.channel)
    
    async def backup(self, channel):
        await self.bot.send_file(channel,"data/judgement/scores.json")
        await self.bot.send_file(channel,"data/judgement/settings.json")
        await self.bot.send_file(channel,"data/judgement/timeout.json")
    
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
                await self.EditUserScore(ctx)
                
                
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
    
    def get_prefix(self, message):
        for p in self.bot.settings.get_prefixes(message.server):
            if message.content.startswith(p):
                return p
        return False
    
def check_folder():
    if not os.path.exists("data/judgement"):
        print("Creating data/judgement folder...")
        os.makedirs("data/judgement")

def check_file():
    scores = {}
    settings = {"RESPOND_ON_POINT": True, "DEBUG": False, "COOLDOWN":300, "SERVER":""}
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
    bot.add_listener(n.parse_message, "on_message")
    loop = asyncio.get_event_loop()
    loop.create_task(n.loop())
    bot.add_cog(n)  
