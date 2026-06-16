import discord
from discord.ext import commands
import asyncio
import logging
from collections import defaultdict
import re
from datetime import datetime, timedelta
from utils.helpers import error_embed, success_embed, footer, e, BLURPLE, GREEN, RED, YELLOW

class Security(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config_file = "data/security_settings.json"

        import os
        os.makedirs("data", exist_ok=True)

        self.spam_detection = defaultdict(lambda: {
            'messages': 0,
            'last_message': None,
            'repeated_content': defaultdict(int),
            'warns': 0,
            'last_warn': None
        })
        self.spam_thresholds = {
            'messages_per_second': 1.5,
            'similar_messages': 3,
            'max_mentions': 5,
            'max_warns': 3
        }

        self.join_tracker = defaultdict(list)
        self.raid_settings = defaultdict(lambda: {
            'enabled': True,
            'joins_per_minute': 10,
            'account_age': 7,
            'action': 'kick'
        })

        self._load_settings()

        self.automod_rules = {
            'invite_filter': True,
            'scam_detection': True,
            'phishing_links': True,
            'mass_mentions': True,
            'zalgo_text': True,
            'caps_spam': True
        }

        self.invite_pattern  = re.compile(r"(?:https?://)?(?:www\.)?(discord\.(?:gg|io|me|li)|discordapp\.com/invite)/[a-zA-Z0-9]+")
        self.zalgo_pattern   = re.compile(r"[\u0300-\u036F\u0489]")
        self.url_pattern     = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*(),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')
        self.phishing_domains = [
            "nitro-free", "dlscord", "dlscordgift",
            "steamcommumity", "stearncommunity",
            "dlscordnitro", "discordgift"
        ]

    # ── Listeners ──────────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_member_join(self, member):
        guild = member.guild
        now   = datetime.utcnow()
        created_at_naive = member.created_at.replace(tzinfo=None)

        self.join_tracker[guild.id] = [t for t in self.join_tracker[guild.id]
                                       if now - t < timedelta(minutes=1)]
        self.join_tracker[guild.id].append(now)

        settings = self.raid_settings[guild.id]

        if len(self.join_tracker[guild.id]) >= settings['joins_per_minute']:
            if settings['action'] == 'kick':
                await member.kick(reason="Raid protection: Too many joins")
            elif settings['action'] == 'ban':
                await member.ban(reason="Raid protection: Too many joins", delete_message_days=1)

            log_channel = discord.utils.get(guild.text_channels, name="mod-logs")
            if log_channel:
                embed = discord.Embed(
                    title="🚨  Raid Alert",
                    description=f"Raid protection triggered — **{len(self.join_tracker[guild.id])}** joins/minute detected.",
                    colour=e(RED)
                )
                embed.add_field(name="Action Taken", value=settings['action'].title(), inline=True)
                embed.add_field(name="Triggered By", value=member.mention,             inline=True)
                footer(embed, "Guard Bot  •  Raid Protection")
                await log_channel.send(embed=embed)

        account_age = (now - created_at_naive).days
        if account_age < settings['account_age']:
            quarantine_role = discord.utils.get(guild.roles, name="Quarantine")
            if quarantine_role:
                await member.add_roles(quarantine_role, reason=f"New account ({account_age} days old)")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or isinstance(message.channel, discord.DMChannel):
            return

        spam_data = self.spam_detection[message.author.id]
        now       = datetime.utcnow()

        if spam_data['last_message'] and (now - spam_data['last_message']).seconds > 60:
            spam_data['messages'] = 0
            spam_data['repeated_content'].clear()

        spam_data['messages'] += 1
        spam_data['last_message'] = now
        spam_data['repeated_content'][message.content] += 1

        if await self._check_spam(message, spam_data):
            return
        if self.automod_rules['invite_filter'] and await self._check_invites(message):
            return
        if self.automod_rules['phishing_links'] and await self._check_phishing(message):
            return
        if self.automod_rules['mass_mentions'] and len(message.mentions) > self.spam_thresholds['max_mentions']:
            await message.delete()
            embed = discord.Embed(
                description=f"🚫  {message.author.mention} Mass mentions are not allowed!",
                colour=e(RED)
            )
            await message.channel.send(embed=embed, delete_after=6)
            return
        if self.automod_rules['caps_spam'] and self._check_caps(message.content):
            await message.delete()
            embed = discord.Embed(
                description=f"🔤  {message.author.mention} Please don't use excessive caps!",
                colour=e(YELLOW)
            )
            await message.channel.send(embed=embed, delete_after=6)
            return

    # ── Internal helpers ───────────────────────────────────────────────────────

    async def _check_spam(self, message, spam_data):
        if spam_data['messages'] / 60 > self.spam_thresholds['messages_per_second']:
            await self._warn_user(message, "Sending messages too quickly")
            return True
        if any(count >= self.spam_thresholds['similar_messages']
               for count in spam_data['repeated_content'].values()):
            await self._warn_user(message, "Sending repeated messages")
            return True
        return False

    async def _check_invites(self, message):
        if self.invite_pattern.search(message.content):
            if not message.author.guild_permissions.manage_messages:
                await message.delete()
                embed = discord.Embed(
                    description=f"🔗  {message.author.mention} Server invites are not allowed here!",
                    colour=e(RED)
                )
                await message.channel.send(embed=embed, delete_after=6)
                return True
        return False

    async def _check_phishing(self, message):
        urls = self.url_pattern.findall(message.content.lower())
        for url in urls:
            if any(domain in url for domain in self.phishing_domains):
                await message.delete()
                await self._take_action(message, "Posting phishing links", severe=True)
                return True
        return False

    def _check_caps(self, content):
        if len(content) >= 8:
            caps_count = sum(1 for c in content if c.isupper())
            return caps_count / len(content) > 0.7
        return False

    async def _warn_user(self, message, reason):
        spam_data = self.spam_detection[message.author.id]
        now       = datetime.utcnow()

        if spam_data['last_warn'] and (now - spam_data['last_warn']).seconds > 300:
            spam_data['warns'] = 0

        spam_data['warns']    += 1
        spam_data['last_warn'] = now
        await message.delete()

        if spam_data['warns'] >= self.spam_thresholds['max_warns']:
            await self._take_action(message, reason, severe=True)
        else:
            embed = discord.Embed(
                description=(
                    f"⚠️  {message.author.mention} **Warning "
                    f"({spam_data['warns']}/{self.spam_thresholds['max_warns']}):** {reason}"
                ),
                colour=e(YELLOW)
            )
            await message.channel.send(embed=embed, delete_after=8)

    async def _take_action(self, message, reason, severe=False):
        if severe:
            try:
                await message.author.timeout(timedelta(minutes=10), reason=reason)
                embed = discord.Embed(
                    title="🔇  User Timed Out",
                    description=f"{message.author.mention} has been timed out for 10 minutes.",
                    colour=e(RED)
                )
                embed.add_field(name="Reason", value=reason)
                footer(embed, "Guard Bot  •  AutoMod")
                await message.channel.send(embed=embed, delete_after=10)
            except discord.Forbidden:
                pass

        log_channel = discord.utils.get(message.guild.text_channels, name="mod-logs")
        if log_channel:
            embed = discord.Embed(
                title="🛡️  AutoMod Action",
                colour=e(RED)
            )
            embed.set_thumbnail(url=message.author.display_avatar.url)
            embed.add_field(name="👤  User",    value=f"{message.author.mention} `{message.author.id}`", inline=True)
            embed.add_field(name="📋  Reason",  value=reason,                                             inline=True)
            embed.add_field(name="💬  Channel", value=message.channel.mention,                            inline=True)
            footer(embed, "Guard Bot  •  AutoMod")
            await log_channel.send(embed=embed)

    # ── Commands ───────────────────────────────────────────────────────────────

    @commands.group(invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def automod(self, ctx):
        """Show automod settings and status of all protection rules"""
        embed = discord.Embed(
            title="🤖  AutoMod Settings",
            description="Current state of all automated moderation rules.",
            colour=e(BLURPLE)
        )
        for rule, enabled in self.automod_rules.items():
            label = rule.replace('_', ' ').title()
            embed.add_field(
                name=label,
                value="✅ Enabled" if enabled else "❌ Disabled",
                inline=True
            )
        embed.add_field(
            name="\u200b",
            value="`g!automod toggle <rule>` to enable/disable a rule.",
            inline=False
        )
        footer(embed)
        await ctx.send(embed=embed)

    @automod.command()
    @commands.has_permissions(manage_guild=True)
    async def toggle(self, ctx, rule: str):
        """Toggle an automod rule on or off

        Parameters:
        rule: The name of the rule to toggle (spam, caps, invites, etc.)

        Example: g!automod toggle caps_spam"""
        rule = rule.lower()
        if rule not in self.automod_rules:
            rules_list = "\n".join(f"• `{r}`" for r in self.automod_rules)
            embed = discord.Embed(
                title="❌  Invalid Rule",
                description=f"Available rules:\n{rules_list}",
                colour=e(0xED4245)
            )
            footer(embed)
            return await ctx.send(embed=embed)

        self.automod_rules[rule] = not self.automod_rules[rule]
        self._save_settings()
        status = "enabled" if self.automod_rules[rule] else "disabled"
        colour = e(0x57F287) if self.automod_rules[rule] else e(0xED4245)
        embed = discord.Embed(
            description=f"{'✅' if self.automod_rules[rule] else '❌'}  **{rule.replace('_', ' ').title()}** has been **{status}**.",
            colour=colour
        )
        footer(embed)
        await ctx.send(embed=embed)

    @commands.group(invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def raidmode(self, ctx):
        """Show raid protection settings and status"""
        settings = self.raid_settings[ctx.guild.id]
        embed = discord.Embed(
            title="🚨  Raid Protection Settings",
            colour=e(BLURPLE)
        )
        embed.add_field(name="📊  Status",           value="✅ Enabled" if settings['enabled'] else "❌ Disabled", inline=True)
        embed.add_field(name="⚡  Joins / Minute",   value=f"`{settings['joins_per_minute']}`",                    inline=True)
        embed.add_field(name="📅  Min Account Age",  value=f"`{settings['account_age']}` days",                   inline=True)
        embed.add_field(name="⚖️  Action",           value=f"`{settings['action'].title()}`",                     inline=True)
        embed.add_field(
            name="ℹ️  Configure",
            value="`g!raidmode setup <joins> <age_days> <action>`",
            inline=False
        )
        footer(embed)
        await ctx.send(embed=embed)

    @raidmode.command()
    @commands.has_permissions(administrator=True)
    async def setup(self, ctx, joins: int, age: int, action: str):
        """Configure raid protection settings

        Parameters:
        joins: Number of joins per minute to trigger raid protection
        age: Minimum account age in days
        action: 'kick', 'ban', or 'quarantine'

        Example: g!raidmode setup 15 3 ban"""
        if action.lower() not in ['kick', 'ban', 'quarantine']:
            return await ctx.send(embed=error_embed("Invalid action. Use `kick`, `ban`, or `quarantine`."))

        self.raid_settings[ctx.guild.id].update({
            'joins_per_minute': joins,
            'account_age': age,
            'action': action.lower()
        })
        self._save_settings()

        embed = discord.Embed(
            title="✅  Raid Protection Updated",
            colour=e(GREEN)
        )
        embed.add_field(name="⚡  Joins / Minute", value=f"`{joins}`",           inline=True)
        embed.add_field(name="📅  Min Age",        value=f"`{age}` days",        inline=True)
        embed.add_field(name="⚖️  Action",         value=f"`{action.title()}`",  inline=True)
        footer(embed)
        await ctx.send(embed=embed)

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def lockdown(self, ctx, duration: int = 300):
        """Locks down the current channel for a specified duration (seconds)

        Parameters:
        duration: Time in seconds (default 300)

        Example: g!lockdown 600"""
        await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=False)
        embed = discord.Embed(
            title="🔒  Channel Locked",
            description=f"This channel is locked for **{duration}** seconds.",
            colour=e(RED)
        )
        embed.add_field(name="🛡️  By",       value=ctx.author.mention, inline=True)
        embed.add_field(name="⏱️  Duration", value=f"`{duration}s`",   inline=True)
        footer(embed, "Guard Bot  •  Lockdown")
        await ctx.send(embed=embed)

        await asyncio.sleep(duration)
        await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=True)
        embed2 = discord.Embed(
            title="🔓  Channel Unlocked",
            description="The lockdown has been lifted. You may send messages again.",
            colour=e(GREEN)
        )
        footer(embed2, "Guard Bot  •  Lockdown")
        await ctx.send(embed=embed2)

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setraid(self, ctx, joins: int, seconds: int):
        """Configure raid protection thresholds

        Parameters:
        joins: Number of joins to trigger raid protection
        seconds: Time window in seconds

        Example: g!setraid 10 30"""
        self.raid_threshold    = joins
        self.raid_time_window  = seconds
        self._save_settings()
        embed = discord.Embed(
            title="✅  Raid Threshold Updated",
            description=f"Protection triggers at **{joins}** joins within **{seconds}** seconds.",
            colour=e(GREEN)
        )
        footer(embed)
        await ctx.send(embed=embed)

    # ── Persistence ────────────────────────────────────────────────────────────

    def _save_settings(self):
        import json
        from datetime import datetime as dt

        def serialize(obj):
            if isinstance(obj, dt):
                return obj.isoformat()
            return str(obj)

        try:
            settings = {
                'automod_rules': self.automod_rules,
                'raid_settings': {
                    str(guild_id): {k: v for k, v in s.items()}
                    for guild_id, s in self.raid_settings.items()
                    if not isinstance(s, defaultdict)
                }
            }
            with open(self.config_file, 'w') as f:
                json.dump(settings, f, default=serialize)
            logging.info("Security settings saved to file")
        except Exception as ex:
            logging.error(f"Failed to save security settings: {ex}")

    def _load_settings(self):
        import json
        import os

        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    settings = json.load(f)
                if 'automod_rules' in settings:
                    for rule, value in settings['automod_rules'].items():
                        if rule in self.automod_rules:
                            self.automod_rules[rule] = value
                if 'raid_settings' in settings:
                    for guild_id_str, gs in settings['raid_settings'].items():
                        guild_id = int(guild_id_str)
                        for key, value in gs.items():
                            self.raid_settings[guild_id][key] = value
                logging.info("Security settings loaded from file")
            else:
                logging.info("No existing security settings found, using defaults")
        except Exception as ex:
            logging.error(f"Failed to load security settings: {ex}")


async def setup(bot):
    await bot.add_cog(Security(bot))
