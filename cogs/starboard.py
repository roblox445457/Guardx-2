import discord
from discord.ext import commands
import logging
import json
import os
from utils.helpers import error_embed, success_embed, footer, e, BLURPLE, GREEN, RED, YELLOW

STAR_EMOJI = "⭐"

class Starboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config_file = "data/starboard_settings.json"
        self.posted_file  = "data/starboard_posted.json"
        os.makedirs("data", exist_ok=True)
        self.settings = {}
        self.posted   = {}
        self._load_settings()

    def _guild_settings(self, guild_id: int) -> dict:
        if guild_id not in self.settings:
            self.settings[guild_id] = {
                'enabled': False,
                'channel': None,
                'threshold': 3,
                'ignored_channels': []
            }
        return self.settings[guild_id]

    def _load_settings(self):
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    raw = json.load(f)
                self.settings = {int(k): v for k, v in raw.items()}
            if os.path.exists(self.posted_file):
                with open(self.posted_file, 'r') as f:
                    raw2 = json.load(f)
                self.posted = {int(k): v for k, v in raw2.items()}
        except Exception as ex:
            logging.error(f"Starboard load error: {ex}")

    def _save_settings(self):
        try:
            with open(self.config_file, 'w') as f:
                json.dump({str(k): v for k, v in self.settings.items()}, f, indent=2)
            with open(self.posted_file, 'w') as f:
                json.dump({str(k): v for k, v in self.posted.items()}, f, indent=2)
        except Exception as ex:
            logging.error(f"Starboard save error: {ex}")

    def _get_star_count(self, message: discord.Message) -> int:
        for reaction in message.reactions:
            if str(reaction.emoji) == STAR_EMOJI:
                return reaction.count
        return 0

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.User):
        if str(reaction.emoji) != STAR_EMOJI or user.bot:
            return
        await self._check_starboard(reaction.message)

    @commands.Cog.listener()
    async def on_reaction_remove(self, reaction: discord.Reaction, user: discord.User):
        if str(reaction.emoji) != STAR_EMOJI or user.bot:
            return
        await self._update_starboard(reaction.message)

    async def _check_starboard(self, message: discord.Message):
        guild = message.guild
        if not guild:
            return
        gs = self._guild_settings(guild.id)
        if not gs['enabled'] or not gs['channel']:
            return
        if message.channel.id in gs['ignored_channels']:
            return
        if message.author.bot:
            return

        star_count = self._get_star_count(message)
        if star_count < gs['threshold']:
            return

        sb_channel = guild.get_channel(gs['channel'])
        if not sb_channel:
            return

        guild_posted = self.posted.setdefault(guild.id, {})
        msg_id_str = str(message.id)

        embed = self._build_embed(message, star_count)

        if msg_id_str in guild_posted:
            try:
                sb_msg = await sb_channel.fetch_message(guild_posted[msg_id_str])
                await sb_msg.edit(embed=embed)
            except discord.NotFound:
                del guild_posted[msg_id_str]
                sb_msg = await sb_channel.send(embed=embed)
                guild_posted[msg_id_str] = sb_msg.id
        else:
            sb_msg = await sb_channel.send(embed=embed)
            guild_posted[msg_id_str] = sb_msg.id

        self._save_settings()

    async def _update_starboard(self, message: discord.Message):
        guild = message.guild
        if not guild:
            return
        gs = self._guild_settings(guild.id)
        if not gs['enabled'] or not gs['channel']:
            return

        guild_posted = self.posted.get(guild.id, {})
        msg_id_str = str(message.id)
        if msg_id_str not in guild_posted:
            return

        star_count = self._get_star_count(message)
        sb_channel = guild.get_channel(gs['channel'])
        if not sb_channel:
            return

        try:
            sb_msg = await sb_channel.fetch_message(guild_posted[msg_id_str])
            if star_count < gs['threshold']:
                await sb_msg.delete()
                del self.posted[guild.id][msg_id_str]
            else:
                embed = self._build_embed(message, star_count)
                await sb_msg.edit(embed=embed)
            self._save_settings()
        except discord.NotFound:
            pass

    def _build_embed(self, message: discord.Message, star_count: int) -> discord.Embed:
        embed = discord.Embed(
            description=message.content[:2000] if message.content else "",
            colour=e(YELLOW)
        )
        embed.set_author(name=str(message.author), icon_url=message.author.display_avatar.url)
        embed.add_field(name="⭐  Stars",    value=f"**{star_count}**",                              inline=True)
        embed.add_field(name="💬  Channel",  value=message.channel.mention,                          inline=True)
        embed.add_field(name="🔗  Jump",     value=f"[View Message]({message.jump_url})",             inline=True)
        if message.attachments:
            att = message.attachments[0]
            if att.content_type and att.content_type.startswith("image"):
                embed.set_image(url=att.url)
        footer(embed, "Guard Bot  •  Starboard")
        return embed

    @commands.group(invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def starboard(self, ctx):
        """Show starboard configuration."""
        gs = self._guild_settings(ctx.guild.id)
        ch = ctx.guild.get_channel(gs['channel']) if gs['channel'] else None
        ignored = [ctx.guild.get_channel(c) for c in gs['ignored_channels'] if ctx.guild.get_channel(c)]
        embed = discord.Embed(title="⭐  Starboard", colour=e(YELLOW) if gs['enabled'] else e(RED))
        embed.add_field(name="📊  Status",    value="✅ Enabled" if gs['enabled'] else "❌ Disabled",   inline=True)
        embed.add_field(name="📢  Channel",   value=ch.mention if ch else "Not set",                    inline=True)
        embed.add_field(name="⭐  Threshold", value=f"`{gs['threshold']}` stars",                       inline=True)
        if ignored:
            embed.add_field(name="🚫  Ignored", value=" ".join(c.mention for c in ignored), inline=False)
        embed.add_field(name="📖  Commands", value=(
            "`g!starboard setup #channel <threshold>`\n"
            "`g!starboard enable` / `disable`\n"
            "`g!starboard channel #channel`\n"
            "`g!starboard threshold <n>`\n"
            "`g!starboard ignore #channel`"
        ), inline=False)
        footer(embed)
        await ctx.send(embed=embed)

    @starboard.command(name="setup")
    @commands.has_permissions(manage_guild=True)
    async def starboard_setup(self, ctx, channel: discord.TextChannel, threshold: int = 3):
        """Configure the starboard channel and threshold.

        Parameters:
        channel: Channel where starred messages appear
        threshold: Minimum stars needed (default 3)

        Example: g!starboard setup #starboard 3"""
        gs = self._guild_settings(ctx.guild.id)
        gs['channel']   = channel.id
        gs['threshold'] = max(1, threshold)
        gs['enabled']   = True
        self._save_settings()
        embed = discord.Embed(title="✅  Starboard Configured", colour=e(GREEN))
        embed.add_field(name="📢  Channel",   value=channel.mention,         inline=True)
        embed.add_field(name="⭐  Threshold", value=f"`{threshold}` stars",  inline=True)
        footer(embed)
        await ctx.send(embed=embed)

    @starboard.command(name="enable")
    @commands.has_permissions(manage_guild=True)
    async def starboard_enable(self, ctx):
        """Enable the starboard."""
        gs = self._guild_settings(ctx.guild.id)
        if not gs['channel']:
            return await ctx.send(embed=error_embed("Set a channel first with `g!starboard channel #channel`."))
        gs['enabled'] = True
        self._save_settings()
        await ctx.send(embed=success_embed("Starboard **enabled**."))

    @starboard.command(name="channel")
    @commands.has_permissions(manage_guild=True)
    async def starboard_channel(self, ctx, channel: discord.TextChannel):
        """Set the starboard channel.

        Example: g!starboard channel #starboard"""
        gs = self._guild_settings(ctx.guild.id)
        gs['channel'] = channel.id
        self._save_settings()
        await ctx.send(embed=success_embed(f"Starboard channel set to {channel.mention}."))

    @starboard.command(name="threshold")
    @commands.has_permissions(manage_guild=True)
    async def starboard_threshold(self, ctx, threshold: int):
        """Set the minimum star count to appear on the starboard.

        Example: g!starboard threshold 5"""
        if threshold < 1:
            return await ctx.send(embed=error_embed("Threshold must be at least 1."))
        gs = self._guild_settings(ctx.guild.id)
        gs['threshold'] = threshold
        self._save_settings()
        await ctx.send(embed=success_embed(f"Starboard threshold set to **{threshold}** ⭐."))

    @starboard.command(name="ignore")
    @commands.has_permissions(manage_guild=True)
    async def starboard_ignore(self, ctx, channel: discord.TextChannel):
        """Toggle ignoring a channel from the starboard.

        Example: g!starboard ignore #nsfw"""
        gs = self._guild_settings(ctx.guild.id)
        if channel.id in gs['ignored_channels']:
            gs['ignored_channels'].remove(channel.id)
            self._save_settings()
            await ctx.send(embed=success_embed(f"{channel.mention} is no longer ignored by the starboard."))
        else:
            gs['ignored_channels'].append(channel.id)
            self._save_settings()
            await ctx.send(embed=success_embed(f"{channel.mention} will now be **ignored** by the starboard."))


async def setup(bot):
    await bot.add_cog(Starboard(bot))
