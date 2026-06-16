import discord
from discord.ext import commands
import logging
import json
import os
from utils.helpers import error_embed, success_embed, footer, e, BLURPLE, GREEN, RED, YELLOW

class Verification(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config_file = "data/verification_settings.json"
        os.makedirs("data", exist_ok=True)
        self.settings = {}
        self._load_settings()

    def _guild_settings(self, guild_id: int) -> dict:
        if guild_id not in self.settings:
            self.settings[guild_id] = {
                'enabled': False,
                'channel': None,
                'role': None,
                'message_id': None,
                'message': "React with ✅ to verify yourself and gain access to the server."
            }
        return self.settings[guild_id]

    def _load_settings(self):
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    raw = json.load(f)
                self.settings = {int(k): v for k, v in raw.items()}
        except Exception as ex:
            logging.error(f"Verification load error: {ex}")
            self.settings = {}

    def _save_settings(self):
        try:
            with open(self.config_file, 'w') as f:
                json.dump({str(k): v for k, v in self.settings.items()}, f, indent=2)
        except Exception as ex:
            logging.error(f"Verification save error: {ex}")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id:
            return
        if str(payload.emoji) != "✅":
            return
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        gs = self._guild_settings(guild.id)
        if not gs['enabled'] or not gs['role'] or not gs['message_id']:
            return
        if payload.message_id != gs['message_id']:
            return

        role = guild.get_role(gs['role'])
        member = guild.get_member(payload.user_id)
        if role and member and role not in member.roles:
            try:
                await member.add_roles(role, reason="Verification reaction")
                logging.info(f"Verified member {member.id} in guild {guild.id}")
            except discord.Forbidden:
                pass

    @commands.group(invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def verification(self, ctx):
        """Show verification system configuration."""
        gs = self._guild_settings(ctx.guild.id)
        ch   = ctx.guild.get_channel(gs['channel']) if gs['channel'] else None
        role = ctx.guild.get_role(gs['role'])        if gs['role']    else None
        embed = discord.Embed(
            title="✅  Verification System",
            description="Members must react to get access to the server.",
            colour=e(GREEN) if gs['enabled'] else e(RED)
        )
        embed.add_field(name="📊  Status",   value="✅ Enabled" if gs['enabled'] else "❌ Disabled", inline=True)
        embed.add_field(name="📢  Channel",  value=ch.mention   if ch   else "Not set",              inline=True)
        embed.add_field(name="🎭  Role",     value=role.mention if role else "Not set",              inline=True)
        embed.add_field(name="📖  Commands", value=(
            "`g!verification enable` / `disable`\n"
            "`g!verification channel #channel`\n"
            "`g!verification role @role`\n"
            "`g!verification setup` — auto-post verification message"
        ), inline=False)
        footer(embed)
        await ctx.send(embed=embed)

    @verification.command(name="setup")
    @commands.has_permissions(administrator=True)
    async def verification_setup(self, ctx):
        """Post the verification message in the configured channel."""
        gs = self._guild_settings(ctx.guild.id)
        if not gs['channel'] or not gs['role']:
            return await ctx.send(embed=error_embed("Set a channel and role first using `g!verification channel` and `g!verification role`."))

        channel = ctx.guild.get_channel(gs['channel'])
        if not channel:
            return await ctx.send(embed=error_embed("The configured verification channel no longer exists."))

        embed = discord.Embed(
            title="✅  Verification",
            description=gs['message'],
            colour=e(GREEN)
        )
        if ctx.guild.icon:
            embed.set_thumbnail(url=ctx.guild.icon.url)
        footer(embed, ctx.guild.name)
        msg = await channel.send(embed=embed)
        await msg.add_reaction("✅")

        gs['message_id'] = msg.id
        gs['enabled']    = True
        self._save_settings()
        await ctx.send(embed=success_embed(f"Verification message posted in {channel.mention}."))

    @verification.command(name="enable")
    @commands.has_permissions(manage_guild=True)
    async def verification_enable(self, ctx):
        """Enable the verification system."""
        gs = self._guild_settings(ctx.guild.id)
        if not gs['channel'] or not gs['role']:
            return await ctx.send(embed=error_embed("Configure a channel and role first."))
        gs['enabled'] = True
        self._save_settings()
        await ctx.send(embed=success_embed("Verification system **enabled**."))

    @verification.command(name="disable")
    @commands.has_permissions(manage_guild=True)
    async def verification_disable(self, ctx):
        """Disable the verification system."""
        gs = self._guild_settings(ctx.guild.id)
        gs['enabled'] = False
        self._save_settings()
        await ctx.send(embed=error_embed("Verification system **disabled**."))

    @verification.command(name="channel")
    @commands.has_permissions(manage_guild=True)
    async def verification_channel(self, ctx, channel: discord.TextChannel):
        """Set the verification channel.

        Example: g!verification channel #verify"""
        gs = self._guild_settings(ctx.guild.id)
        gs['channel'] = channel.id
        self._save_settings()
        await ctx.send(embed=success_embed(f"Verification channel set to {channel.mention}."))

    @verification.command(name="role")
    @commands.has_permissions(manage_guild=True)
    async def verification_role(self, ctx, role: discord.Role):
        """Set the role given after verification.

        Example: g!verification role @Verified"""
        if role >= ctx.guild.me.top_role:
            return await ctx.send(embed=error_embed("That role is higher than my highest role."))
        gs = self._guild_settings(ctx.guild.id)
        gs['role'] = role.id
        self._save_settings()
        await ctx.send(embed=success_embed(f"Verification role set to {role.mention}."))


async def setup(bot):
    await bot.add_cog(Verification(bot))
