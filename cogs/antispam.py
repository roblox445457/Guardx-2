import discord
from discord.ext import commands
import logging
import json
import os
from collections import defaultdict, deque
from datetime import datetime, timedelta
from utils.helpers import error_embed, success_embed, footer, e, BLURPLE, GREEN, RED, YELLOW

class AntiSpam(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config_file = "data/antispam_settings.json"
        os.makedirs("data", exist_ok=True)
        self.settings = {}
        self.message_cache = defaultdict(lambda: defaultdict(deque))
        self._load_settings()

    def _guild_settings(self, guild_id: int) -> dict:
        if guild_id not in self.settings:
            self.settings[guild_id] = {
                'enabled': False,
                'threshold': 5,
                'interval': 5,
                'action': 'mute',
                'whitelist': []
            }
        return self.settings[guild_id]

    def _load_settings(self):
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    raw = json.load(f)
                self.settings = {int(k): v for k, v in raw.items()}
        except Exception as ex:
            logging.error(f"Failed to load antispam settings: {ex}")
            self.settings = {}

    def _save_settings(self):
        try:
            with open(self.config_file, 'w') as f:
                json.dump({str(k): v for k, v in self.settings.items()}, f, indent=2)
        except Exception as ex:
            logging.error(f"Failed to save antispam settings: {ex}")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        gs = self._guild_settings(message.guild.id)
        if not gs['enabled']:
            return
        if message.author.id in gs['whitelist']:
            return
        if message.author.guild_permissions.manage_messages:
            return

        uid = message.author.id
        gid = message.guild.id
        now = datetime.utcnow()
        cache = self.message_cache[gid][uid]
        cutoff = now - timedelta(seconds=gs['interval'])
        while cache and cache[0] < cutoff:
            cache.popleft()
        cache.append(now)

        if len(cache) >= gs['threshold']:
            cache.clear()
            await self._punish(message, gs['action'])

    async def _punish(self, message: discord.Message, action: str):
        member = message.author
        guild = message.guild
        reason = "Anti-Spam: Sending messages too fast"

        try:
            if action == 'mute':
                muted = discord.utils.get(guild.roles, name="Muted")
                if not muted:
                    muted = await guild.create_role(name="Muted")
                    for ch in guild.channels:
                        await ch.set_permissions(muted, speak=False, send_messages=False)
                await member.add_roles(muted, reason=reason)
            elif action == 'kick':
                await member.kick(reason=reason)
            elif action == 'ban':
                await member.ban(reason=reason, delete_message_days=0)
            elif action == 'timeout':
                await member.timeout(timedelta(minutes=10), reason=reason)
        except discord.Forbidden:
            pass

        embed = discord.Embed(
            title="🚨  Anti-Spam Action",
            description=f"{member.mention} was **{action}d** for spamming.",
            colour=e(RED)
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        footer(embed, "Guard Bot  •  Anti-Spam")
        try:
            await message.channel.send(embed=embed, delete_after=8)
        except discord.Forbidden:
            pass

        log_channel = discord.utils.get(guild.text_channels, name="mod-logs")
        if log_channel:
            embed2 = discord.Embed(title="🚨  Anti-Spam Triggered", colour=e(RED))
            embed2.set_thumbnail(url=member.display_avatar.url)
            embed2.add_field(name="👤  User",    value=f"{member.mention} `{member.id}`", inline=True)
            embed2.add_field(name="⚖️  Action",  value=action.title(),                    inline=True)
            embed2.add_field(name="💬  Channel", value=message.channel.mention,            inline=True)
            footer(embed2, "Guard Bot  •  Anti-Spam")
            await log_channel.send(embed=embed2)

    @commands.group(invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def antispam(self, ctx):
        """Show anti-spam status and configuration."""
        gs = self._guild_settings(ctx.guild.id)
        colour = e(GREEN) if gs['enabled'] else e(RED)
        embed = discord.Embed(
            title="🚨  Anti-Spam",
            description="Automatically punishes users who send messages too fast.",
            colour=colour
        )
        embed.add_field(name="📊  Status",      value="✅ Enabled" if gs['enabled'] else "❌ Disabled", inline=True)
        embed.add_field(name="⚡  Threshold",   value=f"`{gs['threshold']}` msgs / `{gs['interval']}s`", inline=True)
        embed.add_field(name="⚖️  Action",      value=f"`{gs['action'].title()}`",                       inline=True)
        embed.add_field(name="👥  Whitelist",   value=f"`{len(gs['whitelist'])}` users",                 inline=True)
        embed.add_field(name="📖  Commands", value=(
            "`g!antispam enable` / `disable`\n"
            "`g!antispam setup <msgs> <seconds>`\n"
            "`g!antispam action <mute|kick|ban|timeout>`\n"
            "`g!antispam whitelist add/remove @user`"
        ), inline=False)
        footer(embed)
        await ctx.send(embed=embed)

    @antispam.command(name="enable")
    @commands.has_permissions(manage_guild=True)
    async def antispam_enable(self, ctx):
        """Enable anti-spam for this server."""
        gs = self._guild_settings(ctx.guild.id)
        if gs['enabled']:
            return await ctx.send(embed=discord.Embed(description="✅  Anti-spam is **already enabled**.", colour=e(GREEN)))
        gs['enabled'] = True
        self._save_settings()
        await ctx.send(embed=success_embed("Anti-spam **enabled**. Messages are now being rate-limited."))

    @antispam.command(name="disable")
    @commands.has_permissions(manage_guild=True)
    async def antispam_disable(self, ctx):
        """Disable anti-spam for this server."""
        gs = self._guild_settings(ctx.guild.id)
        if not gs['enabled']:
            return await ctx.send(embed=discord.Embed(description="❌  Anti-spam is **already disabled**.", colour=e(RED)))
        gs['enabled'] = False
        self._save_settings()
        await ctx.send(embed=error_embed("Anti-spam **disabled**."))

    @antispam.command(name="setup")
    @commands.has_permissions(manage_guild=True)
    async def antispam_setup(self, ctx, messages: int, seconds: int):
        """Set the spam threshold.

        Parameters:
        messages: Number of messages that triggers the filter
        seconds: Time window in seconds

        Example: g!antispam setup 5 5"""
        if messages < 2 or seconds < 1:
            return await ctx.send(embed=error_embed("Messages must be ≥ 2, seconds must be ≥ 1."))
        gs = self._guild_settings(ctx.guild.id)
        gs['threshold'] = messages
        gs['interval'] = seconds
        self._save_settings()
        embed = discord.Embed(
            title="✅  Anti-Spam Threshold Updated",
            description=f"Users sending **{messages}+** messages in **{seconds}s** will be flagged.",
            colour=e(GREEN)
        )
        footer(embed)
        await ctx.send(embed=embed)

    @antispam.command(name="action")
    @commands.has_permissions(manage_guild=True)
    async def antispam_action(self, ctx, action: str):
        """Set the action taken against spammers.

        Parameters:
        action: mute, kick, ban, or timeout

        Example: g!antispam action mute"""
        action = action.lower()
        if action not in ('mute', 'kick', 'ban', 'timeout'):
            return await ctx.send(embed=error_embed("Valid actions: `mute`, `kick`, `ban`, `timeout`"))
        gs = self._guild_settings(ctx.guild.id)
        gs['action'] = action
        self._save_settings()
        await ctx.send(embed=success_embed(f"Anti-spam action set to **{action}**."))

    @antispam.group(name="whitelist", invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def antispam_whitelist(self, ctx):
        """Manage anti-spam whitelist."""
        gs = self._guild_settings(ctx.guild.id)
        wl = gs['whitelist']
        if not wl:
            return await ctx.send(embed=discord.Embed(description="No users are whitelisted from anti-spam.", colour=e(BLURPLE)))
        mentions = " ".join(f"<@{uid}>" for uid in wl)
        embed = discord.Embed(title="👥  Anti-Spam Whitelist", description=mentions, colour=e(BLURPLE))
        footer(embed)
        await ctx.send(embed=embed)

    @antispam_whitelist.command(name="add")
    @commands.has_permissions(manage_guild=True)
    async def antispam_whitelist_add(self, ctx, member: discord.Member):
        """Add a user to the anti-spam whitelist."""
        gs = self._guild_settings(ctx.guild.id)
        if member.id in gs['whitelist']:
            return await ctx.send(embed=error_embed(f"{member.mention} is already whitelisted."))
        gs['whitelist'].append(member.id)
        self._save_settings()
        await ctx.send(embed=success_embed(f"{member.mention} is now **exempt** from anti-spam."))

    @antispam_whitelist.command(name="remove")
    @commands.has_permissions(manage_guild=True)
    async def antispam_whitelist_remove(self, ctx, member: discord.Member):
        """Remove a user from the anti-spam whitelist."""
        gs = self._guild_settings(ctx.guild.id)
        if member.id not in gs['whitelist']:
            return await ctx.send(embed=error_embed(f"{member.mention} is not whitelisted."))
        gs['whitelist'].remove(member.id)
        self._save_settings()
        await ctx.send(embed=success_embed(f"{member.mention} removed from the whitelist."))


async def setup(bot):
    await bot.add_cog(AntiSpam(bot))
