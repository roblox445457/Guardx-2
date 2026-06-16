import discord
from discord.ext import commands
import logging
import json
import os
from utils.helpers import error_embed, success_embed, footer, e, BLURPLE, GREEN, RED, YELLOW

class AutoRole(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config_file = "data/autorole_settings.json"
        os.makedirs("data", exist_ok=True)
        self.settings = {}
        self._load_settings()

    def _guild_settings(self, guild_id: int) -> dict:
        if guild_id not in self.settings:
            self.settings[guild_id] = {'human_role': None, 'bot_role': None}
        return self.settings[guild_id]

    def _load_settings(self):
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    raw = json.load(f)
                self.settings = {int(k): v for k, v in raw.items()}
        except Exception as ex:
            logging.error(f"Failed to load autorole settings: {ex}")
            self.settings = {}

    def _save_settings(self):
        try:
            with open(self.config_file, 'w') as f:
                json.dump({str(k): v for k, v in self.settings.items()}, f, indent=2)
        except Exception as ex:
            logging.error(f"Failed to save autorole settings: {ex}")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        gs = self._guild_settings(member.guild.id)
        role_id = gs['bot_role'] if member.bot else gs['human_role']
        if not role_id:
            return
        role = member.guild.get_role(role_id)
        if role:
            try:
                await member.add_roles(role, reason="Auto-role on join")
            except discord.Forbidden:
                logging.warning(f"AutoRole: Missing permissions in guild {member.guild.id}")

    @commands.group(invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def autorole(self, ctx):
        """Show auto-role configuration for this server."""
        gs = self._guild_settings(ctx.guild.id)
        h_role = ctx.guild.get_role(gs['human_role']) if gs['human_role'] else None
        b_role = ctx.guild.get_role(gs['bot_role'])   if gs['bot_role']   else None
        embed = discord.Embed(
            title="🎭  Auto-Role",
            description="Roles assigned automatically when members join.",
            colour=e(BLURPLE)
        )
        embed.add_field(name="👤  Human Role", value=h_role.mention if h_role else "Not set", inline=True)
        embed.add_field(name="🤖  Bot Role",   value=b_role.mention if b_role else "Not set", inline=True)
        embed.add_field(name="📖  Commands", value=(
            "`g!autorole set @role` — set human role\n"
            "`g!autorole bot @role` — set bot role\n"
            "`g!autorole remove` — clear human role\n"
            "`g!autorole list` — view config"
        ), inline=False)
        footer(embed)
        await ctx.send(embed=embed)

    @autorole.command(name="set")
    @commands.has_permissions(manage_roles=True)
    async def autorole_set(self, ctx, role: discord.Role):
        """Set the role given to humans on join.

        Parameters:
        role: The role to assign to new human members

        Example: g!autorole set @Member"""
        if role >= ctx.guild.me.top_role:
            return await ctx.send(embed=error_embed("That role is higher than my highest role — I can't assign it."))
        gs = self._guild_settings(ctx.guild.id)
        gs['human_role'] = role.id
        self._save_settings()
        embed = discord.Embed(
            title="✅  Auto-Role Set",
            description=f"New **human** members will now receive {role.mention}.",
            colour=e(GREEN)
        )
        footer(embed)
        await ctx.send(embed=embed)

    @autorole.command(name="bot")
    @commands.has_permissions(manage_roles=True)
    async def autorole_bot(self, ctx, role: discord.Role):
        """Set the role given to bots on join.

        Parameters:
        role: The role to assign to new bots

        Example: g!autorole bot @Bots"""
        if role >= ctx.guild.me.top_role:
            return await ctx.send(embed=error_embed("That role is higher than my highest role — I can't assign it."))
        gs = self._guild_settings(ctx.guild.id)
        gs['bot_role'] = role.id
        self._save_settings()
        embed = discord.Embed(
            title="✅  Bot Auto-Role Set",
            description=f"New **bots** will now receive {role.mention}.",
            colour=e(GREEN)
        )
        footer(embed)
        await ctx.send(embed=embed)

    @autorole.command(name="remove")
    @commands.has_permissions(manage_roles=True)
    async def autorole_remove(self, ctx):
        """Remove the human auto-role."""
        gs = self._guild_settings(ctx.guild.id)
        if not gs['human_role']:
            return await ctx.send(embed=error_embed("No human auto-role is set."))
        gs['human_role'] = None
        self._save_settings()
        await ctx.send(embed=success_embed("Human auto-role **removed**."))

    @autorole.command(name="list")
    @commands.has_permissions(manage_guild=True)
    async def autorole_list(self, ctx):
        """List current auto-role configuration."""
        gs = self._guild_settings(ctx.guild.id)
        h_role = ctx.guild.get_role(gs['human_role']) if gs['human_role'] else None
        b_role = ctx.guild.get_role(gs['bot_role'])   if gs['bot_role']   else None
        embed = discord.Embed(title="📋  Auto-Role List", colour=e(BLURPLE))
        embed.add_field(name="👤  Human Role", value=h_role.mention if h_role else "`Not configured`", inline=True)
        embed.add_field(name="🤖  Bot Role",   value=b_role.mention if b_role else "`Not configured`", inline=True)
        footer(embed)
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(AutoRole(bot))
