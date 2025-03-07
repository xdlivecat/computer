# This project is licensed under the terms of the GPL v3.0 license. Copyright 2024 Cyteon

import discord
import asyncio
import datetime
import logging
import os

logger = logging.getLogger("discord_bot")

from discord.ext import commands, tasks
from discord.ext.commands import Context
from utils import CONSTANTS, DBClient, Checks, CachedDB

KICK_TRESHOLD = 5
BAN_TRESHOLD = 3
DELETE_TRESHOLD = 2
PING_TRESHOLD = 2
WEBHOOK_TRESHOLD = 40

client = DBClient.client
db = client.potatobot

ban_cache = {}
kick_cache = {}
ping_cache = {}
webhook_cache = {}
delete_cache = {}

deleted_channels = {}

users_cant_be_moderated = []

class Security(commands.Cog, name="🛡️ Security"):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.users_cant_be_moderated = users_cant_be_moderated
        self.clear_cache.start()

    @tasks.loop(minutes=10)
    async def clear_cache(self) -> None:
        ban_cache.clear()
        kick_cache.clear()
        ping_cache.clear()
        webhook_cache.clear()
        delete_cache.clear()

        deleted_channels.clear()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author == self.bot.user:
            return

        if message.author == message.guild.owner:
            return

        if message.webhook_id:
            try:
                webhook = await self.bot.fetch_webhook(message.webhook_id)
            except discord.NotFound:
                webhook = None

            if not webhook:
                return

            if message.webhook_id in webhook_cache:
                webhook_cache[message.webhook_id] += 1

                if "@everyone" in message.content.lower() or "@here" in message.content.lower():
                    webhook_cache[message.webhook_id] += 11

                if webhook_cache[message.webhook_id] > WEBHOOK_TRESHOLD:
                    guilds = db["guilds"]
                    data = guilds.find_one({"id": message.guild.id})

                    if not data:
                        data = CONSTANTS.guild_data_template(message.guild.id)
                        guilds.insert_one(data)

                    if not "security" in data:
                        return

                    if "anti_webhook_spam" not in data["security"]["antinuke"]:
                        return

                    if not data["security"]["antinuke"]["anti_webhook_spam"]:
                        return

                    await message.delete()


                    log_channel = message.guild.get_channel(data["log_channel"])

                    try:
                        await webhook.delete()

                        embed = discord.Embed(
                            title="AntiSpam Warning",
                            description=f"Webhook **{message.webhook_id}** has been deleted for spamming",
                            color=0x77dd77
                        )

                        if log_channel != None:
                            await log_channel.send(embed=embed)
                    except:
                        embed = discord.Embed(
                            title="AntiSpam Warning",
                            description=f"Unable to delete webhook **{message.webhook_id}** for spamming, please delete it manually",
                            color=0xff6961
                        )

                        if log_channel != None:
                            await log_channel.send(embed=embed)


                    embed = discord.Embed(
                        title="AntiSpam Warning",
                        description=f"Webhook **{message.webhook_id}** has triggered the antispam system, last message: `{message.content}`",
                        color=0xfdfd96
                    )

                    if log_channel != None:
                        await log_channel.send(embed=embed)
            else:
                webhook_cache[message.webhook_id] = 1

        if message.author in ping_cache:
            if len(message.role_mentions) > 0:
                if message.author.guild_permissions.mention_everyone:
                    ping_cache[message.author] += len(message.role_mentions) * 2

            if "@everyone" in message.content.lower() or "@here" in message.content.lower():
                if message.author.guild_permissions.mention_everyone:
                    ping_cache[message.author] += 1

            if ping_cache[message.author] > PING_TRESHOLD:
                ping_cache[message.author] = 0

                users = db["users"]
                user_data = await CachedDB.find_one(users, {"id": message.author.id, "guild_id": message.guild.id})

                if not user_data:
                    user_data = CONSTANTS.user_data_template(message.author.id, message.guild.id)
                    users.insert_one(user_data)

                if "whitelisted" in user_data:
                    if user_data["whitelisted"]:
                        return

                guilds = db["guilds"]
                data = guilds.find_one({"id": message.guild.id})

                if not data:
                    data = CONSTANTS.guild_data_template(message.guild.id)
                    guilds.insert_one(data)

                if not "security" in data:
                    return

                if "anti_massping" not in data["security"]["antinuke"]:
                    return

                if not data["security"]["antinuke"]["anti_massping"]:
                    return

                await message.delete()

                embed = discord.Embed(
                    title="AntiSpam Warning",
                    description=f"**{message.author.mention}** has triggered the antispam system, last message: `{message.content}`",
                    color=0xfdfd96
                )

                try:
                    await message.channel.send(embed=embed)
                except:
                    pass

                log_channel = message.guild.get_channel(data["log_channel"])

                if log_channel != None:
                    await log_channel.send(embed=embed)

                try:
                    if message.author.id in self.users_cant_be_moderated:
                        return

                    try:
                        embed = discord.Embed(
                            title="You have been muted",
                            description=f"You have been muted for an hour in **{message.guild.name}** for mass pinging",
                            color=0xff6961
                        )

                        await message.author.send(embed=embed)
                    except:
                        pass

                    await message.author.timeout(datetime.timedelta(hours=1), reason="Mass pinging")
                    ban_cache[self.bot.user] = 0

                    embed = discord.Embed(
                        title="User Muted",
                        description=f"**{message.author.mention}** has been muted for mass pinging",
                        color=0xff6961
                    )

                    if log_channel != None:
                        await log_channel.send(embed=embed)
                except discord.Forbidden:
                    self.users_cant_be_moderated.append(message.author.id)
        else:
            ping_cache[message.author] = 0

            if "@everyone" in message.content.lower() or "@here" in message.content.lower():
                if message.author.guild_permissions.mention_everyone:
                    ping_cache[message.author] += 1

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role) -> None:
        if role.permissions.administrator:
            guilds = db["guilds"]
            guild = guilds.find_one({"id": role.guild.id})

            if not guild:
                guild = CONSTANTS.guild_data_template(role.guild.id)
                guilds.insert_one(guild)

            if guild and "security" in guild and "antinuke" in guild["security"]:
                antinuke = guild["security"]["antinuke"]
                if antinuke.get("anti_danger_perms", False):
                    discord_guild = role.guild
                    user = None

                    async for entry in discord_guild.audit_logs(action=discord.AuditLogAction.role_create, limit=2):
                        if entry.target == role:
                            user = entry.user

                    if user == discord_guild.owner:
                        return

                    users = db["users"]
                    user_data = users.find_one({"id": user.id, "guild_id": role.guild.id})

                    if not user_data:
                        user_data = CONSTANTS.user_data_template(user.id, role.guild.id)
                        users.insert_one(user_data)

                    if "whitelisted" in user_data:
                        if user_data["whitelisted"]:
                            embed = discord.Embed(
                                title="AntiNuke Warning",
                                description=f"**{user.mention}** created a dangerous role",
                                color=0xfdfd96
                            )

                            log_channel = role.guild.get_channel(guild["log_channel"])

                            if log_channel is None:
                                return

                            await log_channel.send(embed=embed)
                            return

                    try:
                        await role.delete()
                    except discord.Forbidden:
                        embed = discord.Embed(
                            title="Unable to delete role",
                            description=f"**{user.mention}** created a dangerous role, but I was unable to delete it",
                            color=0xff6961
                        )

                    log_channel = role.guild.get_channel(guild["log_channel"])

                    if log_channel is None:
                        return

                    embed = discord.Embed(
                        title="AntiNuke Alert",
                        description=f"**{user.mention}** tried to create a dangerous role!",
                        color=0xff6961
                    )

                    await log_channel.send(embed=embed)


    @commands.Cog.listener()
    async def on_guild_role_update(self, before: discord.Role, after: discord.Role) -> None:
        if after.permissions.administrator and not before.permissions.administrator:
            guilds = db["guilds"]
            guild = guilds.find_one({"id": after.guild.id})

            if not guild:
                guild = CONSTANTS.guild_data_template(after.guild.id)
                guilds.insert_one(guild)

            if guild and "security" in guild and "antinuke" in guild["security"]:
                antinuke = guild["security"]["antinuke"]
                if antinuke.get("anti_danger_perms", False):
                    discord_guild = before.guild
                    user = None

                    async for entry in discord_guild.audit_logs(action=discord.AuditLogAction.role_update, limit=2):
                        if entry.target == before or after:
                            if user == discord_guild.owner:
                                continue
                            user = entry.user

                    if user == discord_guild.owner:
                        return

                    if not user:
                        return

                    users = db["users"]
                    user_data = users.find_one({"id": user.id, "guild_id": after.guild.id})

                    if not user_data:
                        user_data = CONSTANTS.user_data_template(user.id, after.guild.id)
                        users.insert_one(user_data)

                    if "whitelisted" in user_data:
                        if user_data["whitelisted"]:
                            embed = discord.Embed(
                                title="AntiNuke Warning",
                                description=f"**{user.mention}** gave **{after.mention}** dangerous permissions",
                                color=0xfdfd96
                            )

                            log_channel = after.guild.get_channel(guild["log_channel"])

                            if log_channel is None:
                                return

                            await log_channel.send(embed=embed)
                            return

                    await after.edit(permissions=before.permissions)

                    log_channel = after.guild.get_channel(guild["log_channel"])

                    if log_channel is None:
                        return

                    embed = discord.Embed(
                        title="AntiNuke Alert",
                        description=f"**{user.mention}** tried to give **{after.mention}** dangerous permissions!",
                        color=0xff6961
                    )

                    await log_channel.send(embed=embed)

                    embed = discord.Embed(
                        title="Role Changes Reverted",
                        description=f"**{before.mention}** has been reverted to its previous permissions!",
                        color=0x77dd77
                    )

                    await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_ban(self, discord_guild: discord.Guild, banned_user: discord.User) -> None:
        guilds = db["guilds"]
        guild = guilds.find_one({"id": discord_guild.id})

        if not guild:
            guild = CONSTANTS.guild_data_template(discord_guild.id)
            guilds.insert_one(guild)

        if guild and "security" in guild and "antinuke" in guild["security"]:
            antinuke = guild["security"]["antinuke"]
            if antinuke.get("anti_massban", False):
                user = None

                await asyncio.sleep(0.5)

                async for entry in discord_guild.audit_logs(action=discord.AuditLogAction.ban, limit=2):
                    if entry.target == banned_user:
                        user = entry.user

                if not user:
                    return

                if user == discord_guild.owner:
                    return

                users = db["users"]
                user_data = users.find_one({"id": user.id, "guild_id": discord_guild.id})

                if not user_data:
                    user_data = CONSTANTS.user_data_template(user.id, discord_guild.id)
                    users.insert_one(user_data)

                if "whitelisted" in user_data:
                    if user_data["whitelisted"]:
                        return

                over_limit = False

                if user in ban_cache:
                    ban_cache[user] += 1
                    if ban_cache[user] > BAN_TRESHOLD:
                        over_limit = True
                else:
                    ban_cache[user] = 1

                if over_limit:
                    await discord_guild.unban(banned_user, reason="Mass ban detected")
                    ban_cache[self.bot.user] = 0

                    embed = discord.Embed(
                        title="AntiNuke Warning",
                        description=f"**{user.mention}** has triggered the antinuke system, last banned user: **{banned_user.mention}**",
                        color=0xfdfd96
                    )

                    log_channel = discord_guild.get_channel(guild["log_channel"])

                    if log_channel != None:
                        await log_channel.send(embed=embed)

                    try:
                        await discord_guild.ban(user, reason="AntiNuke Alert - Mass ban detected")
                        ban_cache[self.bot.user] = 0

                        embed = discord.Embed(
                            title="User Banned",
                            description=f"**{user.mention}** has been banned for trying to mass ban members!",
                            color=0xff6961
                        )

                        if log_channel != None:
                            await log_channel.send(embed=embed)
                    except discord.Forbidden:
                        embed = discord.Embed(
                            title="Unable to ban user",
                            description=f"**{user.mention}** could not be banned",
                            color=0xff6961
                        )

                        if log_channel != None:
                            await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        guilds = db["guilds"]
        guild = guilds.find_one({"id": member.guild.id})

        if not guild:
            guild = CONSTANTS.guild_data_template(member.guild.id)
            guilds.insert_one(guild)

        if guild and "security" in guild and "antinuke" in guild["security"]:
            antinuke = guild["security"]["antinuke"]
            if antinuke.get("anti_masskick", False):
                user = None

                async for entry in member.guild.audit_logs(action=discord.AuditLogAction.kick, limit=2):
                    if entry.target == member:
                        user = entry.user

                if not user:
                    return

                if user == member.guild.owner:
                    return

                users = db["users"]
                user_data = users.find_one({"id": user.id, "guild_id": member.guild.id})

                if not user_data:
                    user_data = CONSTANTS.user_data_template(user.id, member.guild.id)
                    users.insert_one(user_data)

                if "whitelisted" in user_data:
                    if user_data["whitelisted"]:
                        return

                over_limit = False

                if user in kick_cache:
                    kick_cache[user] += 1
                    if kick_cache[user] > KICK_TRESHOLD:
                        over_limit = True
                else:
                    kick_cache[user] = 1

                if over_limit:
                    embed = discord.Embed(
                        title="AntiNuke Warning",
                        description=f"**{user.mention}** has triggered the antinuke system, last kicked user: **{member.mention}**",
                        color=0xfdfd96
                    )

                    log_channel = member.guild.get_channel(guild["log_channel"])

                    if log_channel != None:
                        await log_channel.send(embed=embed)

                    try:
                        await member.guild.ban(user, reason="AntiNuke Alert - Mass kick detected")
                        ban_cache[self.bot.user] = 0

                        embed = discord.Embed(
                            title="User Banned",
                            description=f"**{user.mention}** has been banned for trying to mass kick members!",
                            color=0xff6961
                        )

                        if log_channel != None:
                            await log_channel.send(embed=embed)
                    except:
                        embed = discord.Embed(
                            title="Unable to ban user",
                            description=f"**{user.mention}** could not be banned",
                            color=0xff6961
                        )

                        if log_channel != None:
                            await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.TextChannel) -> None:
        guilds = db["guilds"]
        guild = guilds.find_one({"id": channel.guild.id})

        if not guild:
            guild = CONSTANTS.guild_data_template(channel.guild.id)
            guilds.insert_one(guild)

        if guild and "security" in guild and "antinuke" in guild["security"]:
            antinuke = guild["security"]["antinuke"]
            if antinuke.get("anti_massdelete", False):
                user = None

                async for entry in channel.guild.audit_logs(action=discord.AuditLogAction.channel_delete, limit=2):
                    if entry.target.id == channel.id and entry.user:
                        user = entry.user

                if channel.guild in deleted_channels:
                    deleted_channels[channel.guild].append(channel)
                else:
                    deleted_channels[channel.guild] = [channel]

                if not user:
                    return

                if user == channel.guild.owner:
                    pass

                users = db["users"]
                user_data = users.find_one({"id": user.id, "guild_id": channel.guild.id})

                if not user_data:
                    user_data = CONSTANTS.user_data_template(user.id, channel.guild.id)
                    users.insert_one(user_data)


                if "whitelisted" in user_data:
                    if user_data["whitelisted"]:
                        return

                over_limit = False

                if user in delete_cache:
                    delete_cache[user] += 1
                    if delete_cache[user] > DELETE_TRESHOLD:
                        over_limit = True
                else:
                    delete_cache[user] = 1

                if over_limit:

                    log_channel = channel.guild.get_channel(guild["log_channel"])

                    try:
                        await channel.guild.ban(user, reason="AntiNuke Alert - Mass delete detected")
                        ban_cache[self.bot.user] = 0

                        embed = discord.Embed(
                            title="User Banned",
                            description=f"**{user.mention}** has been banned for trying to mass delete channels!",
                            color=0xff6961
                        )

                        if log_channel != None:
                            await log_channel.send(embed=embed)
                    except:
                        pass

                    embed = discord.Embed(
                        title="AntiNuke Warning",
                        description=f"**{user.mention}** has triggered the antinuke system, last deleted channel: **{channel.mention}** ({channel.name})",
                        color=0xfdfd96
                    )

                    if log_channel != None:
                        try:
                            await log_channel.send(embed=embed)
                        except:
                            pass

                    for del_channel in deleted_channels[channel.guild]:
                        if not del_channel in deleted_channels[channel.guild]:
                            return

                        deleted_channels[channel.guild].remove(del_channel)

                        try:
                            new_channel = await del_channel.clone(reason="AntiNuke Alert - Mass delete detected")
                            ban_cache[self.bot.user] = 0

                            embed = discord.Embed(
                                title="Channel Restored",
                                description=f"**{new_channel.mention}** has been restored!",
                                color=0x77dd77
                            )

                            if log_channel != None:
                                await log_channel.send(embed=embed)

                            embed = discord.Embed(
                                title="This channel was nuked",
                                description=f"**{new_channel.mention}** was nuked by **{user.mention}**, channel is restored but message log is gone",
                                color=0xff6961
                            )

                            await new_channel.send(embed=embed)

                            await new_channel.edit(position=del_channel.position)

                        except Exception as e:
                            embed = discord.Embed(
                                title="Error",
                                description=f"An error occured while trying to restore channel **{del_channel.name}**",
                                color=0xff6961
                            )

                            embed.add_field(
                                name="Error",
                                value=f"```{e}```"
                            )

                            if log_channel != None:
                                await log_channel.send(embed=embed)

                    await asyncio.sleep(60)
                    deleted_channels[channel.guild].clear()

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild = await CachedDB.find_one(db["guilds"], {"id": member.guild.id})

        if not guild:
            return

        if member.bot:
            if not member.public_flags.verified_bot:
                guilds = db["guilds"]
                data = await CachedDB.find_one(guilds, {"id": member.guild.id})

                if not data:
                    return

                if "security" not in data:
                    return

                if "antinuke" not in data["security"]:
                    return

                if data["security"]["antinuke"].get("anti_unauthorized_bot", False):
                    if member.id in data["authorized_bots"]:
                        embed = discord.Embed(
                            title="Unverified bot joined",
                            description=f"**{member.mention}** tried to join the guild its not verified, but it is authorized",
                            color=0xfdfd96
                        )

                        embed.set_author(name=member, icon_url=member.avatar.url if member.avatar else member.default_avatar.url)
                        embed.set_footer(text="No action will be taken")

                        log_channel = member.guild.get_channel(guild["log_channel"])

                        if log_channel != None:
                            await log_channel.send(embed=embed)

                        return

                    embed = discord.Embed(
                        title="Unathorized bot tried to join",
                        description=f"**{member.mention}** tried to join the guild, but it's not verified or authorized",
                        color=0xff6961
                    )

                    embed.set_author(name=member, icon_url=member.avatar.url if member.avatar else member.default_avatar.url)
                    embed.set_footer(text="Bot will be kicked, authorize a bot with /antinuke bot authorize <id>")

                    log_channel = member.guild.get_channel(guild["log_channel"])

                    if log_channel != None:
                        await log_channel.send(embed=embed)

                    await member.kick(reason="Unauthorized bot")
                else:
                    embed = discord.Embed(
                        title="Bot Joined",
                        description=f"**{member.mention}** has joined the guild",
                        color=0x77dd77
                    )

                    embed.set_author(name=member, icon_url=member.avatar.url if member.avatar else member.default_avatar.url)

                    log_channel = member.guild.get_channel(guild["log_channel"])

                    if log_channel != None:
                        await log_channel.send(embed=embed)
            else:
                embed = discord.Embed(
                    title="Bot Joined",
                    description=f"**{member.mention}** has joined the guild",
                    color=0x77dd77
                )

                embed.set_footer(text="Bot is verified")

                embed.set_author(name=member, icon_url=member.avatar.url if member.avatar else member.default_avatar.url)

                log_channel = member.guild.get_channel(guild["log_channel"])

                if log_channel != None:
                    await log_channel.send(embed=embed)

        if "lockdown" not in guild:
            return

        if guild["lockdown"]:
            await member.kick(reason="Guild is in lockdown")

    @commands.hybrid_group(
        name="whitelist",
        description="Whitelist users from security measures (guild owner only)"
    )
    async def whitelist(self, context: Context) -> None:
        subcommands = [cmd for cmd in self.whitelist.walk_commands()]

        data = []

        for subcommand in subcommands:
            description = subcommand.description.partition("\n")[0]
            data.append(f"{await self.bot.get_prefix(context)}whitelist {subcommand.name} - {description}")

        help_text = "\n".join(data)
        embed = discord.Embed(
            title=f"Help: Whitelist", description="List of available commands:", color=0xBEBEFE
        )
        embed.add_field(
            name="Commands", value=f"```{help_text}```", inline=False
        )

        await context.send(embed=embed)

    @whitelist.command(
        name="add",
        description="Whitelist a user from security measures (guild owner only)",
        usage="whitelist add <user>"
    )
    @commands.check(Checks.is_not_blacklisted)
    async def add(self, context: Context, user: discord.Member) -> None:
        guild_owner = context.guild.owner

        if context.author != guild_owner and context.author.id != int(os.getenv("OWNER_ID")):
            await context.send("You must be the guild owner to use this command!")
            return

        users = db["users"]
        user_data = users.find_one({"id": user.id, "guild_id": context.guild.id})

        if not user:
            user_data = CONSTANTS.user_data_template(user.id, context.guild.id)
            users.insert_one(user_data)

        newdata = {
            "$set": {
                "whitelisted": True
            }
        }

        users.update_one({"id": user.id, "guild_id": context.guild.id}, newdata)

        await context.send(f"Whitelisted {user.mention}")

    @whitelist.command(
        name="remove",
        description="Remove a user from the whitelist (guild owner only)",
        usage="whitelist remove <user>"
    )
    @commands.check(Checks.is_not_blacklisted)
    async def remove(self, context: Context, user: discord.Member) -> None:
        guild_owner = context.guild.owner

        if context.author != guild_owner:
            await context.send("You must be the guild owner to use this command!")
            return

        users = db["users"]
        user_data = users.find_one({"id": user.id, "guild_id": context.guild.id})

        if not user:
            user_data = CONSTANTS.user_data_template(user.id, context.guild.id)
            users.insert_one(user_data)

        newdata = {
            "$set": {
                "whitelisted": False
            }
        }

        users.update_one({"id": user.id, "guild_id": context.guild.id}, newdata)

        await context.send(f"Unwhitelisted {user.mention}")

    @whitelist.command(
        name="list",
        description="List all whitelisted users (guild owner only)",
        usage="whitelist list"
    )
    @commands.check(Checks.is_not_blacklisted)
    async def list(self, context: Context) -> None:
        users = db["users"]

        whitelisted = users.find({"guild_id": context.guild.id, "whitelisted": True})

        list = "```"

        for user in whitelisted:
            user = context.guild.get_member(user["id"])
            list += f"{user.name}\n"

        list += "```"

        embed = discord.Embed(
            title="Whitelisted Users",
            description=list
        )

        await context.send(embed=embed)

    @commands.hybrid_group(
        name="trusted",
        description="Trusted users can bypass security measures and change security settings"
    )
    async def trusted(self, context: Context) -> None:
        subcommands = [cmd for cmd in self.trusted.walk_commands()]

        data = []

        for subcommand in subcommands:
            description = subcommand.description.partition("\n")[0]
            data.append(f"{await self.bot.get_prefix(context)}trusted {subcommand.name} - {description}")

        help_text = "\n".join(data)
        embed = discord.Embed(
            title=f"Help: Trusted", description="List of available commands:", color=0xBEBEFE
        )
        embed.add_field(
            name="Commands", value=f"```{help_text}```", inline=False
        )

        await context.send(embed=embed)

    @trusted.command(
        name="add",
        description="Trust a user (guild owner only)",
        usage="trusted add <user>"
    )
    @commands.check(Checks.is_not_blacklisted)
    async def trusted_add(self, context: Context, user: discord.Member) -> None:
        guild_owner = context.guild.owner

        if context.author != guild_owner and context.author.id != int(os.getenv("OWNER_ID")):
            await context.send("You must be the guild owner to use this command!")
            return

        users = db["users"]
        user_data = users.find_one({"id": user.id, "guild_id": context.guild.id})

        if not user:
            user_data = CONSTANTS.user_data_template(user.id, context.guild.id)
            users.insert_one(user_data)

        newdata = {
            "$set": {
                "trusted": True
            }
        }

        users.update_one({"id": user.id, "guild_id": context.guild.id}, newdata)

        await context.send(f"Trusted {user.mention}")

    @trusted.command(
        name="remove",
        description="Remove a trusted user (guild owner only)",
        usage="trusted remove <user>"
    )
    @commands.check(Checks.is_not_blacklisted)
    async def trusted_remove(self, context: Context, user: discord.Member) -> None:
        guild_owner = context.guild.owner

        if context.author != guild_owner:
            await context.send("You must be the guild owner to use this command!")
            return

        users = db["users"]
        user_data = users.find_one({"id": user.id, "guild_id": context.guild.id})

        if not user:
            user_data = CONSTANTS.user_data_template(user.id, context.guild.id)
            users.insert_one(user_data)

        newdata = {
            "$set": {
                "trusted": False
            }
        }

        users.update_one({"id": user.id, "guild_id": context.guild.id}, newdata)

        await context.send(f"Untrusted {user.mention}")

    @trusted.command(
        name="list",
        description="List all trusted users",
        usage="trusted list"
    )
    @commands.check(Checks.is_not_blacklisted)
    async def trusted_list(self, context: Context) -> None:
        users = db["users"]

        whitelisted = users.find({"guild_id": context.guild.id, "trusted": True})

        list = "```"

        for user in whitelisted:
            user = context.guild.get_member(user["id"])
            list += f"{user.name}\n"

        list += "```"

        embed = discord.Embed(
            title="Trusted Users",
            description=list
        )

        await context.send(embed=embed)

    @commands.hybrid_group(
        name="antinuke",
        description="Commands to manage antinuke (guild owner/trusted only)",
        usage="antinuke <subcommand>"
    )
    @commands.check(Checks.is_not_blacklisted)
    async def antinuke(self, context: Context) -> None:
        subcommands = [cmd for cmd in self.antinuke.walk_commands()]

        data = []

        for subcommand in subcommands:
            description = subcommand.description.partition("\n")[0]
            data.append(f"{await self.bot.get_prefix(context)}antinuke {subcommand.name} - {description}")

        help_text = "\n".join(data)
        embed = discord.Embed(
            title=f"Help: Antinuke", description="List of available commands:", color=0xBEBEFE
        )
        embed.add_field(
            name="Commands", value=f"```{help_text}```", inline=False
        )

        await context.send(embed=embed)


    @antinuke.command(
        name="anti-danger-perms",
        description="Prevent someone from giving dangerous perms to @everyone (guild owner/trusted only)",
        usage="antinuke anti-danger-perms <true/false>"
    )
    @commands.check(Checks.is_not_blacklisted)
    async def anti_danger_perms(self, context: Context, enabled: bool) -> None:
        guild_owner = context.guild.owner

        if context.author != guild_owner:
            users = db["users"]
            user_data = users.find_one({"id": context.author.id, "guild_id": context.guild.id})

            if not user_data:
                user_data = CONSTANTS.user_data_template(context.author.id, context.guild.id)
                users.insert_one(user_data)

            if "trusted" in user_data:
                if not user_data["trusted"]:
                    await context.send("You must be the guild owner or trusted to use this command!")
                    return
            else:
                return

        guilds = db["guilds"]
        guild = guilds.find_one({"id": context.guild.id})

        if not guild:
            guild = CONSTANTS.guild_data_template(context.guild.id)
            guilds.insert_one(guild)

        if "security" not in guild:
            newdata = {
                "$set": {
                    "security": {
                        "antinuke": {
                            "anti_danger_perms": enabled,
                            "anti_massban": False,
                            "anti_masskick": False,
                            "anti_massdelete": False,
                            "anti_massping": False,
                            "anti_webhook_spam": False,
                            "anti_unauthorized_bot": False

                        }
                    }
                }
            }

            guilds.update_one({"id": context.guild.id}, newdata)
        else:
            newdata = {
                "$set": {
                    "security.antinuke.anti_danger_perms": enabled
                }
            }

            guilds.update_one({"id": context.guild.id}, newdata)

        await context.send(f"Set `anti_danger_perms` to `{enabled}`")

    @antinuke.command(
        name="anti-massban",
        description="Prevent someone from mass banning members (guild owner/trusted only)",
        usage="antinuke anti-massban <true/false>"
    )
    @commands.check(Checks.is_not_blacklisted)
    async def anti_massban(self, context: Context, enabled: bool) -> None:
        guild_owner = context.guild.owner

        if context.author != guild_owner:
            users = db["users"]
            user_data = users.find_one({"id": context.author.id, "guild_id": context.guild.id})

            if not user_data:
                user_data = CONSTANTS.user_data_template(context.author.id, context.guild.id)
                users.insert_one(user_data)

            if "trusted" in user_data:
                if not user_data["trusted"]:
                    await context.send("You must be the guild owner or trusted to use this command!")
                    return
            else:
                return

        guilds = db["guilds"]
        guild = guilds.find_one({"id": context.guild.id})

        if not guild:
            guild = CONSTANTS.guild_data_template(context.guild.id)
            guilds.insert_one(guild)

        if "security" not in guild:
            newdata = {
                "$set": {
                    "security": {
                        "antinuke": {
                            "anti_danger_perms": False,
                            "anti_massban": enabled,
                            "anti_masskick": False,
                            "anti_massdelete": False,
                            "anti_massping": False,
                            "anti_webhook_spam": False,
                            "anti_unauthorized_bot": False
                        }
                    }
                }
            }

            guilds.update_one({"id": context.guild.id}, newdata)
        else:
            newdata = {
                "$set": {
                    "security.antinuke.anti_massban": enabled
                }
            }

            guilds.update_one({"id": context.guild.id}, newdata)

        await context.send(f"Set `anti_massban` to `{enabled}`")

    @antinuke.command(
        name="anti-masskick",
        description="Prevent someone from mass kicking members (guild owner/trusted only)",
        usage="antinuke anti-masskick <true/false>"
    )
    @commands.check(Checks.is_not_blacklisted)
    async def anti_masskick(self, context: Context, enabled: bool) -> None:
        guild_owner = context.guild.owner

        if context.author != guild_owner:
            users = db["users"]
            user_data = users.find_one({"id": context.author.id, "guild_id": context.guild.id})

            if not user_data:
                user_data = CONSTANTS.user_data_template(context.author.id, context.guild.id)
                users.insert_one(user_data)

            if "trusted" in user_data:
                if not user_data["trusted"]:
                    await context.send("You must be the guild owner or trusted to use this command!")
                    return
            else:
                return


        guilds = db["guilds"]
        guild = guilds.find_one({"id": context.guild.id})

        if not guild:
            guild = CONSTANTS.guild_data_template(context.guild.id)
            guilds.insert_one(guild)

        if "security" not in guild:
            newdata = {
                "$set": {
                    "security": {
                        "antinuke": {
                            "anti_danger_perms": False,
                            "anti_massban": False,
                            "anti_masskick": enabled,
                            "anti_massdelete": False,
                            "anti_massping": False,
                            "anti_webhook_spam": False,
                            "anti_unauthorized_bot": False
                        }
                    }
                }
            }

            guilds.update_one({"id": context.guild.id}, newdata)
        else:
            newdata = {
                "$set": {
                    "security.antinuke.anti_masskick": enabled
                }
            }

            guilds.update_one({"id": context.guild.id}, newdata)

        await context.send(f"Set `anti_masskick` to `{enabled}`")

    @antinuke.command(
        name="anti-massdelete",
        description="Prevent someone from mass deleting channels (guild owner/trusted only)",
        usage="antinuke anti-massdelete <true/false>"
    )
    @commands.check(Checks.is_not_blacklisted)
    async def anti_massdelete(self, context: Context, enabled: bool) -> None:
        guild_owner = context.guild.owner

        if context.author != guild_owner:
            users = db["users"]
            user_data = users.find_one({"id": context.author.id, "guild_id": context.guild.id})

            if not user_data:
                user_data = CONSTANTS.user_data_template(context.author.id, context.guild.id)
                users.insert_one(user_data)

            if "trusted" in user_data:
                if not user_data["trusted"]:
                    await context.send("You must be the guild owner or trusted to use this command!")
                    return
            else:
                return

        guilds = db["guilds"]
        guild = guilds.find_one({"id": context.guild.id})

        if not guild:
            guild = CONSTANTS.guild_data_template(context.guild.id)
            guilds.insert_one(guild)

        if "security" not in guild:
            newdata = {
                "$set": {
                    "security": {
                        "antinuke": {
                            "anti_danger_perms": False,
                            "anti_massban": False,
                            "anti_masskick": False,
                            "anti_massdelete": enabled,
                            "anti_massping": False,
                            "anti_webhook_spam": False,
                            "anti_unauthorized_bot": False
                        }
                    }
                }
            }

            guilds.update_one({"id": context.guild.id}, newdata)
        else:
            newdata = {
                "$set": {
                    "security.antinuke.anti_massdelete": enabled
                }
            }

            guilds.update_one({"id": context.guild.id}, newdata)

        await context.send(f"Set `anti_massdelete` to `{enabled}`")

    @antinuke.command(
        name="anti-massping",
        description="Prevent mass pinging (guild owner/trusted only)",
        usage="antinuke anti-massping <true/false>"
    )
    @commands.check(Checks.is_not_blacklisted)
    async def massping(self, context: Context, enabled: bool) -> None:
        guild_owner = context.guild.owner

        if context.author != guild_owner:

            users = db["users"]
            user_data = users.find_one({"id": context.author.id, "guild_id": context.guild.id})

            if not user_data:
                user_data = CONSTANTS.user_data_template(context.author.id, context.guild.id)
                users.insert_one(user_data)

            if "trusted" in user_data:
                if not user_data["trusted"]:
                    await context.send("You must be the guild owner or trusted to use this command!")
                    return
            else:
                return

        guilds = db["guilds"]
        guild = guilds.find_one({"id": context.guild.id})

        if not guild:
            guild = CONSTANTS.guild_data_template(context.guild.id)
            guilds.insert_one(guild)

        if "security" not in guild:
            newdata = {
                "$set": {
                    "security": {
                        "antinuke": {
                            "anti_danger_perms": False,
                            "anti_massban": False,
                            "anti_masskick": False,
                            "anti_massdelete": False,
                            "anti_massping": enabled,
                            "anti_webhook_spam": False,
                            "anti_unauthorized_bot": False
                        }
                    }
                }
            }

            guilds.update_one({"id": context.guild.id}, newdata)
        else:
            newdata = {
                "$set": {
                    "security.antinuke.anti_massping": enabled
                }
            }

            guilds.update_one({"id": context.guild.id}, newdata)

        await context.send(f"Set `anti_massping` to `{enabled}`")

    @antinuke.command(
        name="anti-webhook-spam",
        description="Prevent webhook spam (guild owner/trusted only)",
        usage="antinuke anti-webhook-spam <true/false>"
    )
    @commands.check(Checks.is_not_blacklisted)
    async def anti_webhook_spam(self, context: Context, enabled: bool) -> None:
        guild_owner = context.guild.owner

        if context.author != guild_owner:

            users = db["users"]
            user_data = users.find_one({"id": context.author.id, "guild_id": context.guild.id})

            if not user_data:
                user_data = CONSTANTS.user_data_template(context.author.id, context.guild.id)
                users.insert_one(user_data)

            if "trusted" in user_data:
                if not user_data["trusted"]:
                    await context.send("You must be the guild owner or trusted to use this command!")
                    return
            else:
                return

        guilds = db["guilds"]
        guild = guilds.find_one({"id": context.guild.id})

        if not guild:
            guild = CONSTANTS.guild_data_template(context.guild.id)
            guilds.insert_one(guild)

        if "security" not in guild:
            newdata = {
                "$set": {
                    "security": {
                        "antinuke": {
                            "anti_danger_perms": False,
                            "anti_massban": False,
                            "anti_masskick": False,
                            "anti_massdelete": False,
                            "anti_massping": False,
                            "anti_webhook_spam": enabled,
                            "anti_unauthorized_bot": False
                        }
                    }
                }
            }

            guilds.update_one({"id": context.guild.id}, newdata)
        else:
            newdata = {
                "$set": {
                    "security.antinuke.anti_webhook_spam": enabled
                }
            }

            guilds.update_one({"id": context.guild.id}, newdata)

        await context.send(f"Set `anti_webhook_spam` to `{enabled}`")

    @antinuke.command(
        name="anti-unauthorized-bot",
        description="Prevent bots that are not verified and not athorized from being added (guild owner/trusted only)",
        usage="antinuke anti-unauthorized-bot <true/false>"
    )
    @commands.check(Checks.is_not_blacklisted)
    async def anti_unauthorized_bot(self, context: Context, enabled: bool) -> None:
        guild_owner = context.guild.owner

        if context.author != guild_owner:
            users = db["users"]
            user_data = users.find_one({"id": context.author.id, "guild_id": context.guild.id})

            if not user_data:
                user_data = CONSTANTS.user_data_template(context.author.id, context.guild.id)
                users.insert_one(user_data)

            if "trusted" in user_data:
                if not user_data["trusted"]:
                    await context.send("You must be the guild owner or trusted to use this command!")
                    return
            else:
                return

        guilds = db["guilds"]
        guild = guilds.find_one({"id": context.guild.id})

        if not guild:
            guild = CONSTANTS.guild_data_template(context.guild.id)
            guilds.insert_one(guild)

        if "security" not in guild:
            newdata = {
                "$set": {
                    "security": {
                        "antinuke": {
                            "anti_danger_perms": False,
                            "anti_massban": False,
                            "anti_masskick": False,
                            "anti_massdelete": False,
                            "anti_massping": False,
                            "anti_webhook_spam": False,
                            "anti_unauthorized_bot": enabled
                        }
                    }
                }
            }

            guilds.update_one({"id": context.guild.id}, newdata)
        else:
            newdata = {
                "$set": {
                    "security.antinuke.anti_unauthorized_bot": enabled
                }
            }

            guilds.update_one({"id": context.guild.id}, newdata)

        await context.send(f"Set `anti_unauthorized_bot` to `{enabled}`")

    @antinuke.group(
        name="bot",
        description="Commands for bot related commands in antinuke (guild owner/trusted only)",
        usage="antinuke bot <subcommand>"
    )
    @commands.check(Checks.is_not_blacklisted)
    async def antinuke_bot(self, context: Context) -> None:
        subcommands = [cmd for cmd in self.antinuke_bot.walk_commands()]

        data = []

        for subcommand in subcommands:
            description = subcommand.description.partition("\n")[0]
            data.append(f"{await self.bot.get_prefix(context)}antinuke {subcommand.name} - {description}")

        help_text = "\n".join(data)
        embed = discord.Embed(
            title=f"Help: Antinuke: Bot", description="List of available commands:", color=0xBEBEFE
        )
        embed.add_field(
            name="Commands", value=f"```{help_text}```", inline=False
        )

        await context.send(embed=embed)

    @antinuke_bot.command(
        name="authorize",
        description="Add a bot to the authorized bots list (guild owner/trusted only)",
        usage="antinuke bot authorize <bot_id>"
    )
    @commands.check(Checks.is_not_blacklisted)
    async def antinuke_bot_add(self, context: Context, bot_id: str) -> None:
        await context.defer()

        if not bot_id.isdigit():
            await context.send("Invalid bot ID")
            return

        if context.author != context.guild.owner:
            users = db["users"]
            user_data = users.find_one({"id": context.author.id, "guild_id": context.guild.id})

            if not user_data:
                user_data = CONSTANTS.user_data_template(context.author.id, context.guild.id)
                users.insert_one(user_data)

            if "trusted" in user_data:
                if not user_data["trusted"]:
                    await context.send("You must be the guild owner or trusted to use this command!")
                    return
            else:
                return

        guilds = db["guilds"]
        data = await CachedDB.find_one(guilds, { "id": context.guild.id })

        if "authorized_bots" in data:
            if int(bot_id) in data["authorized_bots"]:
                return await context.send("Bot is already authorized")

            data["authorized_bots"].append(int(bot_id))
        else:
            data["authorized_bots"] = [bot_id]

        newdata = { "$set": { "authorized_bots": data["authorized_bots"] } }
        await CachedDB.update_one(guilds, { "id": context.guild.id }, newdata)

        await context.send(f"Added bot `{bot_id}` to the authorized bots list")

    @commands.hybrid_command(
        name="lockdown",
        description="Lockdown the server (guild owner/trusted only)",
        usage="lockdown"
    )
    @commands.check(Checks.is_not_blacklisted)
    async def lockdown(self, context: Context) -> None:
        guild_owner = context.guild.owner

        if context.author != guild_owner:

            users = db["users"]
            user_data = users.find_one({"id": context.author.id, "guild_id": context.guild.id})

            if not user_data:
                user_data = CONSTANTS.user_data_template(context.author.id, context.guild.id)
                users.insert_one(user_data)

            if "trusted" in user_data:
                if not user_data["trusted"]:
                    await context.send("You must be the guild owner or trusted to use this command!")
                    return
            else:
                return

        guilds = db["guilds"]
        guild = guilds.find_one({"id": context.guild.id})

        if not guild:
            guild = CONSTANTS.guild_data_template(context.guild.id)
            guilds.insert_one(guild)

        embed = discord.Embed(
            title = "Confirm Action",
            description = "Are you sure you want to lockdown the server?",
            color = 0xff6961
        )

        await context.send(embed=embed, view=ConfirmView("lockdown", context.author))

    @commands.hybrid_command(
        name="unlockdown",
        description="Unlockdown the server (guild owner/trusted only)",
        usage="unlockdown"
    )
    @commands.check(Checks.is_not_blacklisted)
    async def unlockdown(self, context: Context) -> None:
        guild_owner = context.guild.owner

        await context.send("Starting Unlockdown")

        if context.author != guild_owner:
            users = db["users"]
            user_data = users.find_one({"id": context.author.id, "guild_id": context.guild.id})

            if not user_data:
                user_data = CONSTANTS.user_data_template(context.author.id, context.guild.id)
                users.insert_one(user_data)

            if "trusted" in user_data:
                if not user_data["trusted"]:
                    await context.send("You must be the guild owner or trusted to use this command!")
                    return
            else:
                return

        guilds = db["guilds"]
        guild_data = guilds.find_one({"id": context.guild.id})

        if not guild_data:
            guild_data = CONSTANTS.guild_data_template(context.guild.id)
            guilds.insert_one(guild_data)

        if "oldperms" in guild_data:
            for channel in context.guild.text_channels:
                channel_id_str = str(channel.id)
                if channel_id_str in guild_data["oldperms"]:
                    # Deserialize the permissions
                    perms_dict = guild_data["oldperms"][channel_id_str]
                    overwrite = discord.PermissionOverwrite(**perms_dict)

                    await channel.set_permissions(context.guild.default_role, overwrite=overwrite)

            # Clear oldperms after restoring
            guilds.update_one({"id": context.guild.id}, {"$unset": {"oldperms": ""}})

        # Update the guild document to indicate the lockdown is over
        guilds.update_one({"id": context.guild.id}, {"$set": {"lockdown": False}})
        await context.send("Server unlockdown complete.")


class ConfirmView(discord.ui.View):
    def __init__(self, value: str, author: discord.Member):
        super().__init__()

        self.value = value
        self.author = author

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.author != interaction.user:
            return interaction.response.send_message("no", ephemeral=True)

        await interaction.response.defer()

        if self.value == "lockdown":
            await interaction.message.edit(content="Locking down the server...", view=None, embed=None)

            oldperms = {}

            for channel in interaction.guild.text_channels:
                try:
                    overwrite = channel.overwrites_for(interaction.guild.default_role)
                    # Serialize the PermissionOverwrite object
                    perms_dict = {perm: value for perm, value in overwrite}

                    oldperms[str(channel.id)] = perms_dict

                    overwrite.send_messages = False
                    await channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
                except:
                    pass

            newdata = {
                "$set": {
                    "lockdown": True,
                    "oldperms": oldperms
                }
            }

            guilds = db["guilds"]
            guilds.update_one({"id": interaction.guild.id}, newdata)

            await interaction.message.edit(content="Server lockdown complete.", view=None, embed=None)


    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.primary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.author != interaction.user:
            return interaction.response.send_message("no", ephemeral=True)

        await interaction.response.edit_message("Action cancelled", view=None)



async def setup(bot) -> None:
    await bot.add_cog(Security(bot))
