import discord
from discord.ext import commands
import logging
import json
import os
from utils.helpers import error_embed, success_embed, footer, e, BLURPLE, GREEN, RED, YELLOW

class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config_file = "data/welcome_settings.json"
        os.makedirs("data", exist_ok=True)
        self.settings = {}
        self._load_settings()

    def _guild_settings(self, guild_id: int) -> dict:
        if guild_id not in self.settings:
            self.settings[guild_id] = {
                'welcome_enabled': False,
                'welcome_channel': None,
                'welcome_message': "Welcome to **{server}**, {user}! You're member #{count}.",
                'goodbye_enabled': False,
                'goodbye_channel': None,
                'goodbye_message': "**{user}** has left **{server}**. We now have {count} members.",
            }
        return self.settings[guild_id]

    def _load_settings(self):
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    raw = json.load(f)
                self.settings = {int(k): v for k, v in raw.items()}
        except Exception as ex:
            logging.error(f"Failed to load welcome settings: {ex}")
            self.settings = {}

    def _save_settings(self):
        try:
            with open(self.config_file, 'w') as f:
                json.dump({str(k): v for k, v in self.settings.items()}, f, indent=2)
        except Exception as ex:
            logging.error(f"Failed to save welcome settings: {ex}")

    def _format_message(self, template: str, member: discord.Member) -> str:
        return (template
                .replace('{user}', member.mention)
                .replace('{username}', str(member))
                .replace('{server}', member.guild.name)
                .replace('{count}', str(member.guild.member_count)))

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        gs = self._guild_settings(member.guild.id)
        if not gs['welcome_enabled'] or not gs['welcome_channel']:
            return
        channel = member.guild.get_channel(gs['welcome_channel'])
        if not channel:
            return
        embed = discord.Embed(
            title="👋  Welcome!",
            description=self._format_message(gs['welcome_message'], member),
            colour=e(GREEN)
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="🪪  Account Created", value=f"<t:{int(member.created_at.timestamp())}:R>", inline=True)
        embed.add_field(name="👥  Total Members",   value=f"`{member.guild.member_count}`",               inline=True)
        footer(embed, f"Guard Bot  •  {member.guild.name}")
        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            pass

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        gs = self._guild_settings(member.guild.id)
        if not gs['goodbye_enabled'] or not gs['goodbye_channel']:
            return
        channel = member.guild.get_channel(gs['goodbye_channel'])
        if not channel:
            return
        embed = discord.Embed(
            title="👋  Goodbye!",
            description=self._format_message(gs['goodbye_message'], member),
            colour=e(YELLOW)
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        roles = [r.mention for r in member.roles if r.name != "@everyone"]
        if roles:
            embed.add_field(name="🎭  Roles Had", value=" ".join(roles[:10]), inline=False)
        footer(embed, f"Guard Bot  •  {member.guild.name}")
        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            pass

    # ── Welcome commands ──────────────────────────────────────────────────────

    @commands.group(invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def welcome(self, ctx):
        """Show welcome/goodbye configuration."""
        gs = self._guild_settings(ctx.guild.id)
        wch = ctx.guild.get_channel(gs['welcome_channel']) if gs['welcome_channel'] else None
        gch = ctx.guild.get_channel(gs['goodbye_channel']) if gs['goodbye_channel'] else None
        embed = discord.Embed(title="👋  Welcome / Goodbye", colour=e(BLURPLE))
        embed.add_field(name="📥  Welcome",         value="✅ On" if gs['welcome_enabled'] else "❌ Off", inline=True)
        embed.add_field(name="📤  Goodbye",         value="✅ On" if gs['goodbye_enabled'] else "❌ Off", inline=True)
        embed.add_field(name="\u200b",              value="\u200b",                                        inline=True)
        embed.add_field(name="📢  Welcome Channel", value=wch.mention if wch else "Not set",              inline=True)
        embed.add_field(name="📢  Goodbye Channel", value=gch.mention if gch else "Not set",              inline=True)
        embed.add_field(name="\u200b",              value="\u200b",                                        inline=True)
        embed.add_field(name="📝  Placeholders", value="`{user}` `{username}` `{server}` `{count}`", inline=False)
        footer(embed)
        await ctx.send(embed=embed)

    @welcome.command(name="enable")
    @commands.has_permissions(manage_guild=True)
    async def welcome_enable(self, ctx):
        """Enable welcome messages."""
        gs = self._guild_settings(ctx.guild.id)
        if gs['welcome_enabled']:
            return await ctx.send(embed=discord.Embed(description="✅  Welcome messages already enabled.", colour=e(GREEN)))
        gs['welcome_enabled'] = True
        self._save_settings()
        await ctx.send(embed=success_embed("Welcome messages **enabled**."))

    @welcome.command(name="disable")
    @commands.has_permissions(manage_guild=True)
    async def welcome_disable(self, ctx):
        """Disable welcome messages."""
        gs = self._guild_settings(ctx.guild.id)
        gs['welcome_enabled'] = False
        self._save_settings()
        await ctx.send(embed=error_embed("Welcome messages **disabled**."))

    @welcome.command(name="channel")
    @commands.has_permissions(manage_guild=True)
    async def welcome_channel(self, ctx, channel: discord.TextChannel):
        """Set the welcome message channel.

        Parameters:
        channel: The channel to send welcome messages in

        Example: g!welcome channel #general"""
        gs = self._guild_settings(ctx.guild.id)
        gs['welcome_channel'] = channel.id
        self._save_settings()
        await ctx.send(embed=success_embed(f"Welcome channel set to {channel.mention}."))

    @welcome.command(name="message")
    @commands.has_permissions(manage_guild=True)
    async def welcome_message(self, ctx, *, message: str):
        """Set a custom welcome message.

        Placeholders: {user}, {username}, {server}, {count}

        Example: g!welcome message Hey {user}, welcome to {server}!"""
        gs = self._guild_settings(ctx.guild.id)
        gs['welcome_message'] = message
        self._save_settings()
        embed = discord.Embed(title="✅  Welcome Message Updated", description=f"**Preview:**\n{message}", colour=e(GREEN))
        footer(embed)
        await ctx.send(embed=embed)

    @welcome.command(name="test")
    @commands.has_permissions(manage_guild=True)
    async def welcome_test(self, ctx):
        """Send a test welcome message to preview it."""
        gs = self._guild_settings(ctx.guild.id)
        if not gs['welcome_enabled'] or not gs['welcome_channel']:
            return await ctx.send(embed=error_embed("Welcome is not enabled or no channel is set."))
        await self.on_member_join(ctx.author)
        await ctx.send(embed=success_embed("Test welcome message sent!"), delete_after=5)

    # ── Goodbye commands ──────────────────────────────────────────────────────

    @commands.group(invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def goodbye(self, ctx):
        """Show goodbye configuration."""
        gs = self._guild_settings(ctx.guild.id)
        ch = ctx.guild.get_channel(gs['goodbye_channel']) if gs['goodbye_channel'] else None
        embed = discord.Embed(title="👋  Goodbye Config", colour=e(BLURPLE))
        embed.add_field(name="📤  Status",  value="✅ On" if gs['goodbye_enabled'] else "❌ Off", inline=True)
        embed.add_field(name="📢  Channel", value=ch.mention if ch else "Not set",               inline=True)
        footer(embed)
        await ctx.send(embed=embed)

    @goodbye.command(name="enable")
    @commands.has_permissions(manage_guild=True)
    async def goodbye_enable(self, ctx):
        """Enable goodbye messages."""
        gs = self._guild_settings(ctx.guild.id)
        gs['goodbye_enabled'] = True
        self._save_settings()
        await ctx.send(embed=success_embed("Goodbye messages **enabled**."))

    @goodbye.command(name="channel")
    @commands.has_permissions(manage_guild=True)
    async def goodbye_channel(self, ctx, channel: discord.TextChannel):
        """Set the goodbye message channel.

        Example: g!goodbye channel #goodbye"""
        gs = self._guild_settings(ctx.guild.id)
        gs['goodbye_channel'] = channel.id
        self._save_settings()
        await ctx.send(embed=success_embed(f"Goodbye channel set to {channel.mention}."))

    @goodbye.command(name="message")
    @commands.has_permissions(manage_guild=True)
    async def goodbye_message(self, ctx, *, message: str):
        """Set a custom goodbye message.

        Placeholders: {user}, {username}, {server}, {count}

        Example: g!goodbye message {username} has left {server}."""
        gs = self._guild_settings(ctx.guild.id)
        gs['goodbye_message'] = message
        self._save_settings()
        embed = discord.Embed(title="✅  Goodbye Message Updated", description=f"**Preview:**\n{message}", colour=e(GREEN))
        footer(embed)
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Welcome(bot))
