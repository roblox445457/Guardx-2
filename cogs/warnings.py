import discord
from discord.ext import commands
import logging
import json
import os
from utils.helpers import error_embed, success_embed, footer, e, BLURPLE, GREEN, RED, YELLOW

VALID_ACTIONS = ('mute', 'kick', 'ban')

class Warnings(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config_file = "data/warnpunish_settings.json"
        os.makedirs("data", exist_ok=True)
        self.punishments = {}
        self._load_settings()

    def _load_settings(self):
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    raw = json.load(f)
                self.punishments = {int(k): {int(c): a for c, a in v.items()} for k, v in raw.items()}
        except Exception as ex:
            logging.error(f"Failed to load warnpunish settings: {ex}")
            self.punishments = {}

    def _save_settings(self):
        try:
            with open(self.config_file, 'w') as f:
                json.dump({str(k): {str(c): a for c, a in v.items()} for k, v in self.punishments.items()}, f, indent=2)
        except Exception as ex:
            logging.error(f"Failed to save warnpunish settings: {ex}")

    def get_punishments(self, guild_id: int) -> dict:
        return self.punishments.get(guild_id, {})

    async def check_and_apply(self, ctx, member: discord.Member, warn_count: int):
        """Called after a new warning is added — applies auto-punishment if threshold is met."""
        punishments = self.get_punishments(ctx.guild.id)
        if warn_count in punishments:
            action = punishments[warn_count]
            reason = f"Auto-punishment: {warn_count} warnings reached"
            try:
                if action == 'mute':
                    muted = discord.utils.get(ctx.guild.roles, name="Muted")
                    if not muted:
                        muted = await ctx.guild.create_role(name="Muted")
                        for ch in ctx.guild.channels:
                            await ch.set_permissions(muted, send_messages=False, speak=False)
                    await member.add_roles(muted, reason=reason)
                elif action == 'kick':
                    await member.kick(reason=reason)
                elif action == 'ban':
                    await member.ban(reason=reason, delete_message_days=0)

                embed = discord.Embed(
                    title=f"⚖️  Auto-Punishment — {action.title()}",
                    description=f"{member.mention} reached **{warn_count}** warnings and was automatically **{action}d**.",
                    colour=e(RED)
                )
                embed.set_thumbnail(url=member.display_avatar.url)
                footer(embed, "Guard Bot  •  Auto-Punish")
                await ctx.send(embed=embed)
            except discord.Forbidden:
                pass

    @commands.group(invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def warnpunish(self, ctx):
        """Show auto-punishment thresholds for warnings."""
        punishments = self.get_punishments(ctx.guild.id)
        embed = discord.Embed(
            title="⚖️  Warning Auto-Punishment",
            description="Automatic actions triggered when a member reaches a warning threshold.",
            colour=e(BLURPLE)
        )
        if punishments:
            lines = [f"**{count}** warnings → `{action.title()}`" for count, action in sorted(punishments.items())]
            embed.add_field(name="📋  Thresholds", value="\n".join(lines), inline=False)
        else:
            embed.add_field(name="📋  Thresholds", value="No auto-punishments configured.", inline=False)
        embed.add_field(name="📖  Commands", value=(
            "`g!warnpunish set <count> <action>` — add threshold\n"
            "`g!warnpunish remove <count>` — remove threshold"
        ), inline=False)
        footer(embed)
        await ctx.send(embed=embed)

    @warnpunish.command(name="set")
    @commands.has_permissions(administrator=True)
    async def warnpunish_set(self, ctx, count: int, action: str):
        """Set an auto-punishment threshold.

        Parameters:
        count: Warning count to trigger punishment
        action: mute, kick, or ban

        Example: g!warnpunish set 3 mute"""
        action = action.lower()
        if action not in VALID_ACTIONS:
            return await ctx.send(embed=error_embed(f"Valid actions: `{'`, `'.join(VALID_ACTIONS)}`"))
        if count < 1:
            return await ctx.send(embed=error_embed("Warning count must be at least 1."))
        if ctx.guild.id not in self.punishments:
            self.punishments[ctx.guild.id] = {}
        self.punishments[ctx.guild.id][count] = action
        self._save_settings()
        embed = discord.Embed(
            title="✅  Auto-Punishment Set",
            description=f"Members with **{count}** warnings will be **{action}d** automatically.",
            colour=e(GREEN)
        )
        footer(embed)
        await ctx.send(embed=embed)

    @warnpunish.command(name="remove")
    @commands.has_permissions(administrator=True)
    async def warnpunish_remove(self, ctx, count: int):
        """Remove an auto-punishment threshold.

        Parameters:
        count: The warning count threshold to remove

        Example: g!warnpunish remove 3"""
        punishments = self.punishments.get(ctx.guild.id, {})
        if count not in punishments:
            return await ctx.send(embed=error_embed(f"No punishment set for **{count}** warnings."))
        del self.punishments[ctx.guild.id][count]
        self._save_settings()
        await ctx.send(embed=success_embed(f"Auto-punishment at **{count}** warnings removed."))


async def setup(bot):
    await bot.add_cog(Warnings(bot))
