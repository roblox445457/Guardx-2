import discord
from discord.ext import commands
from datetime import datetime
from utils.helpers import footer, e, BLURPLE, GREEN, RED, YELLOW, FUCHSIA

class Logging(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def log_event(self, guild, event_type, embed):
        if guild.id not in self.bot.guild_settings:
            return
        log_channels = self.bot.guild_settings[guild.id]['logging']
        if event_type in ['kick', 'ban', 'unban', 'mute', 'unmute']:
            channel_id = log_channels.get('mod_log')
        elif event_type in ['message_delete', 'message_edit', 'bulk_delete']:
            channel_id = log_channels.get('message_log')
        else:
            channel_id = log_channels.get('server_log')
        if channel_id:
            channel = guild.get_channel(channel_id)
            if channel:
                await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.author.bot:
            return
        embed = discord.Embed(
            title="🗑️  Message Deleted",
            colour=e(RED),
        )
        embed.set_author(
            name=str(message.author),
            icon_url=message.author.display_avatar.url
        )
        embed.add_field(name="👤  Author",   value=f"{message.author.mention} `{message.author.id}`", inline=True)
        embed.add_field(name="💬  Channel",  value=message.channel.mention,                           inline=True)
        if message.content:
            embed.add_field(name="📝  Content", value=message.content[:1000], inline=False)
        footer(embed, "Guard Bot  •  Message Log")
        await self.log_event(message.guild, 'message_delete', embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if before.author.bot or before.content == after.content:
            return
        embed = discord.Embed(
            title="✏️  Message Edited",
            colour=e(BLURPLE),
        )
        embed.set_author(
            name=str(before.author),
            icon_url=before.author.display_avatar.url
        )
        embed.add_field(name="👤  Author",  value=f"{before.author.mention} `{before.author.id}`", inline=True)
        embed.add_field(name="💬  Channel", value=before.channel.mention,                          inline=True)
        embed.add_field(name="🔗  Jump",    value=f"[View Message]({after.jump_url})",             inline=True)
        embed.add_field(name="📝  Before",  value=before.content[:500] or "*empty*",              inline=False)
        embed.add_field(name="📝  After",   value=after.content[:500]  or "*empty*",              inline=False)
        footer(embed, "Guard Bot  •  Message Log")
        await self.log_event(before.guild, 'message_edit', embed)

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if before.roles == after.roles:
            return
        added   = set(after.roles)  - set(before.roles)
        removed = set(before.roles) - set(after.roles)
        parts   = []
        if added:
            parts.append(f"**Added:** {' '.join(r.mention for r in added)}")
        if removed:
            parts.append(f"**Removed:** {' '.join(r.mention for r in removed)}")

        embed = discord.Embed(
            title="🎭  Member Roles Updated",
            description="\n".join(parts),
            colour=e(BLURPLE),
        )
        embed.set_author(name=str(after), icon_url=after.display_avatar.url)
        embed.set_thumbnail(url=after.display_avatar.url)
        embed.add_field(name="👤  Member", value=f"{after.mention} `{after.id}`", inline=True)
        footer(embed, "Guard Bot  •  Server Log")
        await self.log_event(after.guild, 'member_update', embed)

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        async for entry in guild.audit_logs(action=discord.AuditLogAction.ban, limit=1):
            if entry.target.id != user.id:
                continue
            embed = discord.Embed(
                title="🔨  Member Banned",
                colour=e(RED),
            )
            embed.set_thumbnail(url=user.display_avatar.url)
            embed.add_field(name="👤  User",       value=f"{user.mention} `{user.id}`",            inline=True)
            embed.add_field(name="🛡️  Moderator",  value=f"{entry.user.mention}",                  inline=True)
            embed.add_field(name="📋  Reason",      value=entry.reason or "No reason provided",     inline=False)
            footer(embed, "Guard Bot  •  Mod Log")
            await self.log_event(guild, 'ban', embed)

    @commands.Cog.listener()
    async def on_member_unban(self, guild, user):
        async for entry in guild.audit_logs(action=discord.AuditLogAction.unban, limit=1):
            if entry.target.id != user.id:
                continue
            embed = discord.Embed(
                title="🔓  Member Unbanned",
                colour=e(GREEN),
            )
            embed.set_thumbnail(url=user.display_avatar.url)
            embed.add_field(name="👤  User",      value=f"{user.mention} `{user.id}`", inline=True)
            embed.add_field(name="🛡️  Moderator", value=entry.user.mention,           inline=True)
            footer(embed, "Guard Bot  •  Mod Log")
            await self.log_event(guild, 'unban', embed)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        log_channel = discord.utils.get(member.guild.text_channels, name="server-logs")
        if not log_channel:
            return
        created_ts = int(member.created_at.timestamp())
        embed = discord.Embed(
            title="📥  Member Joined",
            colour=e(GREEN),
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="👤  User",        value=f"{member.mention} `{member.id}`",      inline=True)
        embed.add_field(name="📅  Account Age", value=f"<t:{created_ts}:R>",                  inline=True)
        embed.add_field(name="👥  Members",     value=f"`{member.guild.member_count}`",        inline=True)
        footer(embed, "Guard Bot  •  Server Log")
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        log_channel = discord.utils.get(member.guild.text_channels, name="server-logs")
        if not log_channel:
            return
        embed = discord.Embed(
            title="📤  Member Left",
            colour=e(YELLOW),
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="👤  User",    value=f"{member.mention} `{member.id}`", inline=True)
        embed.add_field(name="🎭  Roles",   value=" ".join(r.mention for r in member.roles[1:]) or "None", inline=False)
        footer(embed, "Guard Bot  •  Server Log")
        await log_channel.send(embed=embed)


    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        log_channel = discord.utils.get(member.guild.text_channels, name="server-logs")
        if not log_channel:
            return

        if before.channel == after.channel and before.self_mute == after.self_mute and before.self_deaf == after.self_deaf:
            return

        embed = discord.Embed(colour=e(BLURPLE))
        embed.set_author(name=str(member), icon_url=member.display_avatar.url)
        embed.set_thumbnail(url=member.display_avatar.url)

        if before.channel is None and after.channel:
            embed.title = "🔊  Joined Voice"
            embed.add_field(name="📢  Channel", value=after.channel.mention, inline=True)
            embed.colour = e(GREEN)
        elif before.channel and after.channel is None:
            embed.title = "🔇  Left Voice"
            embed.add_field(name="📢  Channel", value=before.channel.mention, inline=True)
            embed.colour = e(RED)
        elif before.channel and after.channel and before.channel != after.channel:
            embed.title = "🔀  Moved Voice Channel"
            embed.add_field(name="📤  From", value=before.channel.mention, inline=True)
            embed.add_field(name="📥  To",   value=after.channel.mention,  inline=True)
        elif before.self_mute != after.self_mute:
            embed.title = "🎙️  Self-Mute Toggled"
            embed.add_field(name="🎙️  Muted", value="Yes" if after.self_mute else "No", inline=True)
            embed.add_field(name="📢  Channel", value=after.channel.mention if after.channel else "Unknown", inline=True)
            embed.colour = e(YELLOW)
        elif before.self_deaf != after.self_deaf:
            embed.title = "🎧  Self-Deafen Toggled"
            embed.add_field(name="🎧  Deafened", value="Yes" if after.self_deaf else "No", inline=True)
            embed.add_field(name="📢  Channel", value=after.channel.mention if after.channel else "Unknown", inline=True)
            embed.colour = e(YELLOW)
        else:
            return

        embed.add_field(name="👤  Member", value=f"{member.mention} `{member.id}`", inline=False)
        footer(embed, "Guard Bot  •  Voice Log")
        await log_channel.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Logging(bot))
