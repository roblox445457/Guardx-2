import discord
from discord.ext import commands
import asyncio
import uuid
from datetime import datetime, timedelta
from utils.helpers import create_log_embed, check_permissions, error_embed, success_embed, info_embed, e, footer, BLURPLE, GREEN, RED, YELLOW, FUCHSIA

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.temp_bans = {}

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _warnings(self, guild_id: int) -> dict:
        if not hasattr(self.bot, 'warnings_data'):
            self.bot.warnings_data = {}
        return self.bot.warnings_data.setdefault(guild_id, {})

    def _user_warns(self, guild_id: int, user_id: int) -> list:
        return self._warnings(guild_id).setdefault(user_id, [])

    # ── Ban/Kick ───────────────────────────────────────────────────────────────

    @commands.command()
    @commands.has_permissions(manage_guild=True)
    async def kick(self, ctx, member: discord.Member, *, reason=None):
        """Kicks a member from the server.

        Example: g!kick @user Breaking rules"""
        if not check_permissions(ctx, member, "kick"):
            return await ctx.send(embed=error_embed("I don't have permission to kick members!"))
        await member.kick(reason=reason)
        await ctx.send(embed=create_log_embed("Kick", member, ctx.author, reason))

    @commands.command()
    @commands.has_permissions(manage_guild=True)
    async def ban(self, ctx, member: discord.Member, *, reason=None):
        """Permanently bans a member from the server.

        Example: g!ban @user Repeated violations"""
        if not check_permissions(ctx, member, "ban"):
            return await ctx.send(embed=error_embed("I don't have permission to ban members!"))
        await member.ban(reason=reason, delete_message_days=1)
        await ctx.send(embed=create_log_embed("Ban", member, ctx.author, reason))

    @commands.command()
    @commands.has_permissions(manage_guild=True)
    async def unban(self, ctx, *, user: str):
        """Unban a user by name#discriminator or user ID.

        Parameters:
        user: Username#discriminator or user ID

        Example: g!unban 123456789"""
        banned = [entry async for entry in ctx.guild.bans()]
        target = None
        try:
            uid = int(user)
            target = next((entry for entry in banned if entry.user.id == uid), None)
        except ValueError:
            target = next((entry for entry in banned if str(entry.user) == user), None)

        if not target:
            return await ctx.send(embed=error_embed(f"No banned user matching `{user}` found."))

        await ctx.guild.unban(target.user, reason=f"Unbanned by {ctx.author}")
        await ctx.send(embed=create_log_embed("Unban", target.user, ctx.author))

    @commands.command()
    @commands.has_permissions(manage_guild=True)
    async def softban(self, ctx, member: discord.Member, *, reason=None):
        """Ban then immediately unban a member (deletes recent messages).

        Example: g!softban @user Spam"""
        if not check_permissions(ctx, member, "ban"):
            return await ctx.send(embed=error_embed("I don't have permission to ban members!"))
        await member.ban(reason=f"Softban: {reason}", delete_message_days=1)
        await ctx.guild.unban(member, reason="Softban complete")
        embed = create_log_embed("Soft Ban", member, ctx.author, reason)
        await ctx.send(embed=embed)

    @commands.command()
    @commands.has_permissions(ban_members=True)
    async def massban(self, ctx, *members: discord.Member, reason: str = "Mass ban"):
        """Ban multiple members at once.

        Example: g!massban @user1 @user2 @user3"""
        if not members:
            return await ctx.send(embed=error_embed("Mention at least one member to mass-ban."))
        banned = []
        for member in members:
            try:
                await member.ban(reason=f"Mass ban by {ctx.author}: {reason}", delete_message_days=1)
                banned.append(str(member))
            except discord.Forbidden:
                pass
        embed = discord.Embed(
            title=f"🔨  Mass Ban — {len(banned)} members",
            description="\n".join(f"• `{m}`" for m in banned) or "None banned.",
            colour=e(RED)
        )
        embed.add_field(name="📋  Reason",      value=reason,            inline=True)
        embed.add_field(name="🛡️  Moderator",   value=ctx.author.mention, inline=True)
        footer(embed)
        await ctx.send(embed=embed)

    @commands.command()
    @commands.has_permissions(manage_guild=True)
    async def tempban(self, ctx, member: discord.Member, duration: int, *, reason=None):
        """Temporarily bans a member for a given number of minutes.

        Parameters:
        duration: Ban duration in minutes

        Example: g!tempban @user 60 Spamming"""
        if not check_permissions(ctx, member, "ban"):
            return await ctx.send(embed=error_embed("I don't have permission to ban members!"))
        await member.ban(reason=f"Temporary ban: {reason}", delete_message_days=1)
        self.temp_bans[member.id] = {'guild': ctx.guild.id, 'unban_time': datetime.utcnow() + timedelta(minutes=duration)}
        embed = create_log_embed("Temporary Ban", member, ctx.author, reason)
        embed.add_field(name="⏱️  Duration", value=f"`{duration}` minutes", inline=True)
        await ctx.send(embed=embed)
        await asyncio.sleep(duration * 60)
        if member.id in self.temp_bans:
            try:
                await ctx.guild.unban(member, reason="Temporary ban expired")
            except Exception:
                pass
            del self.temp_bans[member.id]

    # ── Mute/Timeout ───────────────────────────────────────────────────────────

    @commands.command()
    @commands.has_permissions(manage_guild=True)
    async def mute(self, ctx, member: discord.Member, duration: int = None, *, reason=None):
        """Mutes a member using the Muted role.

        Parameters:
        duration: Optional duration in minutes
        reason: Reason for the mute

        Example: g!mute @user 30 Spamming"""
        if not check_permissions(ctx, member, "mute"):
            return await ctx.send(embed=error_embed("I don't have permission to manage roles!"))
        muted_role = discord.utils.get(ctx.guild.roles, name="Muted")
        if not muted_role:
            muted_role = await ctx.guild.create_role(name="Muted")
            for channel in ctx.guild.channels:
                await channel.set_permissions(muted_role, speak=False, send_messages=False)
        await member.add_roles(muted_role, reason=reason)
        embed = create_log_embed("Mute", member, ctx.author, reason)
        if duration:
            embed.add_field(name="⏱️  Duration", value=f"`{duration}` minutes", inline=True)
        await ctx.send(embed=embed)
        if duration:
            await asyncio.sleep(duration * 60)
            if muted_role in member.roles:
                await member.remove_roles(muted_role, reason="Mute duration expired")

    @commands.command()
    @commands.has_permissions(manage_guild=True)
    async def unmute(self, ctx, member: discord.Member, *, reason=None):
        """Unmutes a member by removing the Muted role.

        Example: g!unmute @user"""
        muted_role = discord.utils.get(ctx.guild.roles, name="Muted")
        if not muted_role or muted_role not in member.roles:
            return await ctx.send(embed=error_embed(f"{member.mention} is not muted!"))
        await member.remove_roles(muted_role, reason=reason)
        await ctx.send(embed=create_log_embed("Unmute", member, ctx.author, reason))

    @commands.command()
    @commands.has_permissions(moderate_members=True)
    async def timeout(self, ctx, member: discord.Member, duration: int, *, reason=None):
        """Apply a Discord timeout to a member.

        Parameters:
        duration: Timeout duration in minutes (max 40320 / 28 days)
        reason: Reason for the timeout

        Example: g!timeout @user 10 Spamming"""
        if duration < 1 or duration > 40320:
            return await ctx.send(embed=error_embed("Duration must be between 1 and 40320 minutes (28 days)."))
        await member.timeout(timedelta(minutes=duration), reason=reason)
        embed = discord.Embed(
            title="⏱️  Timeout Applied",
            colour=e(YELLOW)
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="👤  User",        value=f"{member.mention} `{member.id}`", inline=True)
        embed.add_field(name="⏱️  Duration",    value=f"`{duration}` minutes",            inline=True)
        embed.add_field(name="🛡️  Moderator",   value=ctx.author.mention,                 inline=True)
        if reason:
            embed.add_field(name="📋  Reason", value=reason, inline=False)
        footer(embed)
        await ctx.send(embed=embed)

    @commands.command()
    @commands.has_permissions(moderate_members=True)
    async def untimeout(self, ctx, member: discord.Member, *, reason=None):
        """Remove a timeout from a member.

        Example: g!untimeout @user"""
        await member.timeout(None, reason=reason)
        embed = discord.Embed(
            description=f"✅  Timeout removed from {member.mention}.",
            colour=e(GREEN)
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        footer(embed)
        await ctx.send(embed=embed)

    # ── Warnings ───────────────────────────────────────────────────────────────

    @commands.command()
    @commands.has_permissions(manage_guild=True)
    async def warn(self, ctx, member: discord.Member, *, reason: str):
        """Warn a member and log it.

        Example: g!warn @user Breaking rule #3"""
        if member.bot:
            return await ctx.send(embed=error_embed("You can't warn a bot."))
        warns = self._user_warns(ctx.guild.id, member.id)
        warn_id = str(uuid.uuid4())[:8]
        warns.append({'id': warn_id, 'reason': reason, 'moderator': ctx.author.id, 'time': datetime.utcnow().isoformat()})

        embed = discord.Embed(title="⚠️  Warning Issued", colour=e(YELLOW))
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="👤  User",        value=f"{member.mention} `{member.id}`", inline=True)
        embed.add_field(name="🛡️  Moderator",   value=ctx.author.mention,                 inline=True)
        embed.add_field(name="🔢  Warning #",   value=f"**{len(warns)}**",                inline=True)
        embed.add_field(name="📋  Reason",      value=reason,                             inline=False)
        embed.add_field(name="🪪  Warn ID",     value=f"`{warn_id}`",                     inline=True)
        footer(embed)
        await ctx.send(embed=embed)

        # Try to DM the warned user
        try:
            dm_embed = discord.Embed(
                title=f"⚠️  You received a warning in {ctx.guild.name}",
                description=f"**Reason:** {reason}\n**Total warnings:** {len(warns)}",
                colour=e(YELLOW)
            )
            footer(dm_embed)
            await member.send(embed=dm_embed)
        except discord.Forbidden:
            pass

        # Auto-punish check
        warnings_cog = self.bot.get_cog("Warnings")
        if warnings_cog:
            await warnings_cog.check_and_apply(ctx, member, len(warns))

    @commands.command(name="warnings")
    @commands.has_permissions(manage_guild=True)
    async def warnings_list(self, ctx, member: discord.Member):
        """List all warnings for a member.

        Example: g!warnings @user"""
        warns = self._user_warns(ctx.guild.id, member.id)
        if not warns:
            return await ctx.send(embed=discord.Embed(
                description=f"✅  {member.mention} has no warnings.",
                colour=e(GREEN)
            ))
        embed = discord.Embed(
            title=f"⚠️  Warnings for {member}",
            colour=e(YELLOW)
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        for i, w in enumerate(warns[-10:], 1):
            mod = ctx.guild.get_member(w['moderator'])
            embed.add_field(
                name=f"#{i}  ID: `{w['id']}`",
                value=f"**Reason:** {w['reason']}\n**By:** {mod.mention if mod else 'Unknown'}\n**When:** <t:{int(datetime.fromisoformat(w['time']).timestamp())}:R>",
                inline=False
            )
        embed.set_footer(text=f"Total: {len(warns)} warning(s) • Guard Bot")
        embed.timestamp = datetime.utcnow()
        await ctx.send(embed=embed)

    @commands.command()
    @commands.has_permissions(manage_guild=True)
    async def clearwarn(self, ctx, member: discord.Member, warn_id: str):
        """Remove a specific warning by its ID.

        Example: g!clearwarn @user a1b2c3d4"""
        warns = self._user_warns(ctx.guild.id, member.id)
        before = len(warns)
        self._warnings(ctx.guild.id)[member.id] = [w for w in warns if w['id'] != warn_id]
        if len(self._warnings(ctx.guild.id)[member.id]) == before:
            return await ctx.send(embed=error_embed(f"No warning with ID `{warn_id}` found for {member.mention}."))
        await ctx.send(embed=success_embed(f"Removed warning `{warn_id}` from {member.mention}."))

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def clearwarns(self, ctx, member: discord.Member):
        """Clear all warnings for a member.

        Example: g!clearwarns @user"""
        self._warnings(ctx.guild.id)[member.id] = []
        await ctx.send(embed=success_embed(f"All warnings cleared for {member.mention}."))

    # ── Channel Management ─────────────────────────────────────────────────────

    @commands.command()
    @commands.has_permissions(manage_guild=True)
    async def clear(self, ctx, amount: int):
        """Delete a number of messages from this channel (max 100).

        Example: g!clear 50"""
        if amount > 100:
            return await ctx.send(embed=error_embed("Cannot delete more than **100** messages at once!"))
        deleted = await ctx.channel.purge(limit=amount + 1)
        embed = discord.Embed(description=f"🗑️  Cleared **{len(deleted) - 1}** messages.", colour=e(BLURPLE))
        footer(embed)
        msg = await ctx.send(embed=embed)
        await asyncio.sleep(4)
        await msg.delete()

    @commands.command()
    @commands.has_permissions(manage_guild=True)
    async def purge(self, ctx, amount: int, member: discord.Member = None, *, contains: str = None):
        """Purge messages, optionally filtered by user and/or text content.

        Parameters:
        amount: Number of messages to check (max 100)
        member: Optional — only delete this member's messages
        contains: Optional — only delete messages containing this text

        Example: g!purge 50
        Example: g!purge 50 @spammer
        Example: g!purge 50 @spammer bad word"""
        if amount > 100:
            return await ctx.send(embed=error_embed("Max 100 messages."))

        def check(m):
            if member and m.author != member:
                return False
            if contains and contains.lower() not in m.content.lower():
                return False
            return True

        deleted = await ctx.channel.purge(limit=amount + 1, check=check)
        filters = []
        if member:
            filters.append(f"from {member.mention}")
        if contains:
            filters.append(f"containing `{contains}`")
        filter_text = " ".join(filters)
        embed = discord.Embed(
            description=f"🗑️  Purged **{len(deleted)}** messages{' ' + filter_text if filter_text else ''}.",
            colour=e(BLURPLE)
        )
        footer(embed)
        msg = await ctx.send(embed=embed)
        await asyncio.sleep(4)
        await msg.delete()

    @commands.command()
    @commands.has_permissions(manage_channels=True)
    async def slowmode(self, ctx, seconds: int):
        """Set the slowmode for this channel.

        Parameters:
        seconds: Delay in seconds (0 to disable)

        Example: g!slowmode 5"""
        if seconds < 0 or seconds > 21600:
            return await ctx.send(embed=error_embed("Slowmode must be between 0 and 21600 seconds."))
        await ctx.channel.edit(slowmode_delay=seconds)
        if seconds == 0:
            await ctx.send(embed=success_embed("Slowmode **disabled**."))
        else:
            await ctx.send(embed=success_embed(f"Slowmode set to **{seconds}** second{'s' if seconds != 1 else ''}."))

    @commands.command()
    @commands.has_permissions(manage_channels=True)
    async def lock(self, ctx, channel: discord.TextChannel = None):
        """Lock a channel so @everyone cannot send messages.

        Example: g!lock #general"""
        target = channel or ctx.channel
        await target.set_permissions(ctx.guild.default_role, send_messages=False)
        embed = discord.Embed(
            title="🔒  Channel Locked",
            description=f"{target.mention} has been locked.",
            colour=e(RED)
        )
        embed.add_field(name="🛡️  By", value=ctx.author.mention, inline=True)
        footer(embed)
        await ctx.send(embed=embed)

    @commands.command()
    @commands.has_permissions(manage_channels=True)
    async def unlock(self, ctx, channel: discord.TextChannel = None):
        """Unlock a previously locked channel.

        Example: g!unlock #general"""
        target = channel or ctx.channel
        await target.set_permissions(ctx.guild.default_role, send_messages=True)
        embed = discord.Embed(
            title="🔓  Channel Unlocked",
            description=f"{target.mention} is now unlocked.",
            colour=e(GREEN)
        )
        embed.add_field(name="🛡️  By", value=ctx.author.mention, inline=True)
        footer(embed)
        await ctx.send(embed=embed)

    # ── Nickname ───────────────────────────────────────────────────────────────

    @commands.command()
    @commands.has_permissions(manage_nicknames=True)
    async def nick(self, ctx, member: discord.Member, *, nickname: str = None):
        """Change or reset a member's nickname.

        Parameters:
        member: The member to rename
        nickname: New nickname (leave blank to reset)

        Example: g!nick @user Cool Name"""
        old = member.nick or member.name
        await member.edit(nick=nickname, reason=f"Nickname changed by {ctx.author}")
        embed = discord.Embed(
            title="✏️  Nickname Changed",
            colour=e(BLURPLE)
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="👤  Member",  value=member.mention, inline=True)
        embed.add_field(name="📛  Before",  value=f"`{old}`",     inline=True)
        embed.add_field(name="📛  After",   value=f"`{nickname or 'Reset'}`", inline=True)
        footer(embed)
        await ctx.send(embed=embed)



async def setup(bot):
    await bot.add_cog(Moderation(bot))
