import discord
from discord.ext import commands
import logging
import json
import os
from utils.helpers import error_embed, success_embed, footer, e, BLURPLE, GREEN, RED, YELLOW

class Invites(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data_file = "data/invites_data.json"
        os.makedirs("data", exist_ok=True)
        self.invite_counts = {}
        self.invite_cache  = {}
        self._load_data()

    def _load_data(self):
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r') as f:
                    raw = json.load(f)
                self.invite_counts = {int(k): {int(u): c for u, c in v.items()} for k, v in raw.items()}
        except Exception as ex:
            logging.error(f"Invites load error: {ex}")
            self.invite_counts = {}

    def _save_data(self):
        try:
            with open(self.data_file, 'w') as f:
                json.dump({str(k): {str(u): c for u, c in v.items()} for k, v in self.invite_counts.items()}, f, indent=2)
        except Exception as ex:
            logging.error(f"Invites save error: {ex}")

    def _guild_counts(self, guild_id: int) -> dict:
        if guild_id not in self.invite_counts:
            self.invite_counts[guild_id] = {}
        return self.invite_counts[guild_id]

    @commands.Cog.listener()
    async def on_ready(self):
        for guild in self.bot.guilds:
            try:
                invites = await guild.invites()
                self.invite_cache[guild.id] = {inv.code: inv.uses for inv in invites}
            except discord.Forbidden:
                pass

    @commands.Cog.listener()
    async def on_invite_create(self, invite: discord.Invite):
        if invite.guild:
            self.invite_cache.setdefault(invite.guild.id, {})[invite.code] = invite.uses or 0

    @commands.Cog.listener()
    async def on_invite_delete(self, invite: discord.Invite):
        if invite.guild:
            self.invite_cache.get(invite.guild.id, {}).pop(invite.code, None)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild = member.guild
        try:
            current_invites = await guild.invites()
        except discord.Forbidden:
            return

        cached = self.invite_cache.get(guild.id, {})
        inviter_id = None

        for inv in current_invites:
            prev_uses = cached.get(inv.code, 0)
            if inv.uses > prev_uses:
                inviter_id = inv.inviter.id if inv.inviter else None
                break

        self.invite_cache[guild.id] = {inv.code: inv.uses for inv in current_invites}

        if inviter_id:
            counts = self._guild_counts(guild.id)
            counts[inviter_id] = counts.get(inviter_id, 0) + 1
            self._save_data()

    @commands.command()
    @commands.has_permissions(manage_guild=True)
    async def invites(self, ctx, member: discord.Member = None):
        """Show how many members a user has invited.

        Example: g!invites @user"""
        target = member or ctx.author
        counts = self._guild_counts(ctx.guild.id)
        count  = counts.get(target.id, 0)
        embed  = discord.Embed(
            title="📨  Invite Count",
            colour=e(BLURPLE)
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="👤  User",    value=target.mention, inline=True)
        embed.add_field(name="📨  Invites", value=f"**{count}**", inline=True)
        footer(embed)
        await ctx.send(embed=embed)

    @commands.command()
    @commands.has_permissions(manage_guild=True)
    async def inviteleaderboard(self, ctx):
        """Show the top inviters for this server."""
        counts = self._guild_counts(ctx.guild.id)
        if not counts:
            return await ctx.send(embed=discord.Embed(description="No invite data yet.", colour=e(BLURPLE)))

        sorted_counts = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:10]
        lines = []
        for idx, (uid, count) in enumerate(sorted_counts, 1):
            member = ctx.guild.get_member(uid)
            name = member.mention if member else f"`{uid}`"
            medal = ["🥇", "🥈", "🥉"][idx - 1] if idx <= 3 else f"`#{idx}`"
            lines.append(f"{medal}  {name} — **{count}** invite{'s' if count != 1 else ''}")

        embed = discord.Embed(
            title="📨  Invite Leaderboard",
            description="\n".join(lines),
            colour=e(BLURPLE)
        )
        if ctx.guild.icon:
            embed.set_thumbnail(url=ctx.guild.icon.url)
        footer(embed)
        await ctx.send(embed=embed)

    @commands.command()
    @commands.has_permissions(manage_guild=True)
    async def inviteinfo(self, ctx, code: str):
        """Show information about a Discord invite.

        Parameters:
        code: The invite code or URL

        Example: g!inviteinfo discord.gg/abc123"""
        code = code.split("/")[-1].split("?")[0]
        try:
            invite = await self.bot.fetch_invite(code, with_counts=True)
        except discord.NotFound:
            return await ctx.send(embed=error_embed(f"Invite `{code}` not found."))
        except discord.HTTPException:
            return await ctx.send(embed=error_embed("Could not fetch invite information."))

        embed = discord.Embed(title="📨  Invite Info", colour=e(BLURPLE))
        if invite.guild:
            embed.add_field(name="🏰  Server",    value=invite.guild.name,                          inline=True)
            embed.add_field(name="👥  Members",   value=f"{invite.approximate_member_count}",        inline=True)
            embed.add_field(name="🟢  Online",    value=f"{invite.approximate_presence_count}",      inline=True)
        embed.add_field(name="📢  Channel",       value=f"#{invite.channel.name if invite.channel else 'Unknown'}", inline=True)
        embed.add_field(name="👤  Inviter",       value=str(invite.inviter) if invite.inviter else "Unknown", inline=True)
        embed.add_field(name="🔗  Code",          value=f"`{invite.code}`",                          inline=True)
        footer(embed)
        await ctx.send(embed=embed)

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def resetinvites(self, ctx, member: discord.Member):
        """Reset a member's invite count to zero.

        Example: g!resetinvites @user"""
        counts = self._guild_counts(ctx.guild.id)
        counts[member.id] = 0
        self._save_data()
        await ctx.send(embed=success_embed(f"Reset invite count for {member.mention} to **0**."))

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def addinvites(self, ctx, member: discord.Member, amount: int):
        """Manually add invites to a member's count.

        Parameters:
        member: The member to add invites to
        amount: Number of invites to add

        Example: g!addinvites @user 10"""
        counts = self._guild_counts(ctx.guild.id)
        counts[member.id] = counts.get(member.id, 0) + amount
        self._save_data()
        await ctx.send(embed=success_embed(f"Added **{amount}** invites to {member.mention}. New total: **{counts[member.id]}**."))


async def setup(bot):
    await bot.add_cog(Invites(bot))
