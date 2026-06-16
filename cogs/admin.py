import discord
from discord.ext import commands
import aiohttp
import io
from datetime import datetime
from utils.helpers import error_embed, success_embed, footer, e, BLURPLE, GREEN, RED, YELLOW

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.start_time = datetime.utcnow()

    # ── Server / Info ──────────────────────────────────────────────────────────

    @commands.command()
    @commands.has_permissions(manage_guild=True)
    async def serverinfo(self, ctx):
        """Displays detailed server information."""
        guild  = ctx.guild
        owner  = guild.owner
        online = sum(1 for m in guild.members if m.status != discord.Status.offline)
        embed  = discord.Embed(title=f"🏰  {guild.name}", description=guild.description or "", colour=e(BLURPLE))
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        if guild.banner:
            embed.set_image(url=guild.banner.url)
        embed.add_field(name="👑  Owner",       value=owner.mention,                                              inline=True)
        embed.add_field(name="🪪  ID",          value=f"`{guild.id}`",                                            inline=True)
        embed.add_field(name="📅  Created",     value=f"<t:{int(guild.created_at.timestamp())}:D>",               inline=True)
        embed.add_field(name="👥  Members",     value=f"**{guild.member_count}** total  🟢 {online} online",      inline=True)
        embed.add_field(name="💬  Channels",    value=f"📝 {len(guild.text_channels)}  🔊 {len(guild.voice_channels)}  📁 {len(guild.categories)}", inline=True)
        embed.add_field(name="🎭  Roles",       value=f"`{len(guild.roles)}`",                                    inline=True)
        embed.add_field(name="🔒  Verification",value=str(guild.verification_level).title(),                      inline=True)
        embed.add_field(name="🚀  Boosts",      value=f"`{guild.premium_subscription_count}` (Tier {guild.premium_tier})", inline=True)
        embed.add_field(name="😀  Emojis",      value=f"`{len(guild.emojis)}/{guild.emoji_limit}`",               inline=True)
        embed.set_footer(text=f"Guard Bot  •  Requested by {ctx.author}")
        embed.timestamp = datetime.utcnow()
        await ctx.send(embed=embed)

    @commands.command()
    async def userinfo(self, ctx, member: discord.Member = None):
        """Show detailed information about a member.

        Example: g!userinfo @user"""
        member = member or ctx.author
        roles  = [r.mention for r in reversed(member.roles) if r.name != "@everyone"]
        flags  = [f.name.replace("_", " ").title() for f, v in member.public_flags if v]
        embed  = discord.Embed(
            title=f"👤  {member}",
            colour=member.colour if member.colour.value else e(BLURPLE)
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="🪪  ID",          value=f"`{member.id}`",                                                inline=True)
        embed.add_field(name="🤖  Bot",         value="Yes" if member.bot else "No",                                  inline=True)
        embed.add_field(name="📅  Joined",      value=f"<t:{int(member.joined_at.timestamp())}:R>" if member.joined_at else "Unknown", inline=True)
        embed.add_field(name="🗓️  Created",    value=f"<t:{int(member.created_at.timestamp())}:R>",                    inline=True)
        embed.add_field(name="📛  Nickname",    value=member.nick or "None",                                           inline=True)
        embed.add_field(name="🎨  Top Role",    value=member.top_role.mention,                                         inline=True)
        if roles:
            embed.add_field(name=f"🎭  Roles ({len(roles)})", value=" ".join(roles[:15]), inline=False)
        if flags:
            embed.add_field(name="🏅  Badges", value=", ".join(flags), inline=False)
        footer(embed)
        await ctx.send(embed=embed)

    @commands.command()
    async def channelinfo(self, ctx, channel: discord.TextChannel = None):
        """Show information about a channel.

        Example: g!channelinfo #general"""
        ch = channel or ctx.channel
        embed = discord.Embed(title=f"💬  #{ch.name}", colour=e(BLURPLE))
        embed.add_field(name="🪪  ID",          value=f"`{ch.id}`",                                              inline=True)
        embed.add_field(name="📁  Category",    value=ch.category.name if ch.category else "None",               inline=True)
        embed.add_field(name="📅  Created",     value=f"<t:{int(ch.created_at.timestamp())}:R>",                  inline=True)
        embed.add_field(name="⏱️  Slowmode",   value=f"`{ch.slowmode_delay}s`" if ch.slowmode_delay else "Off",  inline=True)
        embed.add_field(name="🔞  NSFW",        value="Yes" if ch.is_nsfw() else "No",                           inline=True)
        embed.add_field(name="📌  Position",    value=f"`{ch.position}`",                                        inline=True)
        if ch.topic:
            embed.add_field(name="📝  Topic", value=ch.topic[:200], inline=False)
        footer(embed)
        await ctx.send(embed=embed)

    @commands.command()
    async def roleinfo(self, ctx, role: discord.Role):
        """Show information about a role.

        Example: g!roleinfo @Moderator"""
        perms = [p.replace("_", " ").title() for p, v in role.permissions if v]
        embed = discord.Embed(title=f"🎭  {role.name}", colour=role.colour)
        embed.add_field(name="🪪  ID",          value=f"`{role.id}`",                                            inline=True)
        embed.add_field(name="👥  Members",     value=f"`{len(role.members)}`",                                  inline=True)
        embed.add_field(name="📅  Created",     value=f"<t:{int(role.created_at.timestamp())}:R>",                inline=True)
        embed.add_field(name="🎨  Colour",      value=str(role.colour),                                          inline=True)
        embed.add_field(name="📌  Position",    value=f"`{role.position}`",                                      inline=True)
        embed.add_field(name="📢  Mentionable", value="Yes" if role.mentionable else "No",                       inline=True)
        if perms:
            embed.add_field(name="🔑  Key Perms", value=", ".join(perms[:12]), inline=False)
        footer(embed)
        await ctx.send(embed=embed)

    @commands.command()
    async def avatar(self, ctx, member: discord.Member = None):
        """Show a member's full avatar.

        Example: g!avatar @user"""
        member = member or ctx.author
        embed  = discord.Embed(title=f"🖼️  {member}'s Avatar", colour=e(BLURPLE))
        embed.set_image(url=member.display_avatar.url)
        embed.add_field(name="🔗  PNG",  value=f"[Link]({member.display_avatar.replace(format='png').url})",  inline=True)
        embed.add_field(name="🔗  WEBP", value=f"[Link]({member.display_avatar.replace(format='webp').url})", inline=True)
        footer(embed)
        await ctx.send(embed=embed)

    @commands.command()
    async def membercount(self, ctx):
        """Show the current member count."""
        guild  = ctx.guild
        humans = sum(1 for m in guild.members if not m.bot)
        bots   = sum(1 for m in guild.members if m.bot)
        embed  = discord.Embed(title="👥  Member Count", colour=e(BLURPLE))
        embed.add_field(name="👥  Total",  value=f"**{guild.member_count}**", inline=True)
        embed.add_field(name="👤  Humans", value=f"**{humans}**",             inline=True)
        embed.add_field(name="🤖  Bots",   value=f"**{bots}**",               inline=True)
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        footer(embed)
        await ctx.send(embed=embed)

    @commands.command()
    async def ping(self, ctx):
        """Show the bot's latency."""
        ws_latency  = round(self.bot.latency * 1000)
        import time
        t1 = time.monotonic()
        msg = await ctx.send("📡  Measuring...")
        api_latency = round((time.monotonic() - t1) * 1000)
        embed = discord.Embed(title="🏓  Pong!", colour=e(GREEN))
        embed.add_field(name="📡  WebSocket", value=f"`{ws_latency}ms`",  inline=True)
        embed.add_field(name="⚡  API",        value=f"`{api_latency}ms`", inline=True)
        footer(embed)
        await msg.edit(content=None, embed=embed)

    @commands.command()
    async def uptime(self, ctx):
        """Show how long the bot has been running."""
        delta = datetime.utcnow() - self.start_time
        days, rem = divmod(int(delta.total_seconds()), 86400)
        hours, rem = divmod(rem, 3600)
        minutes, seconds = divmod(rem, 60)
        embed = discord.Embed(
            title="⏱️  Bot Uptime",
            description=f"`{days}d {hours}h {minutes}m {seconds}s`",
            colour=e(GREEN)
        )
        embed.add_field(name="🚀  Since", value=f"<t:{int(self.start_time.timestamp())}:F>", inline=True)
        footer(embed)
        await ctx.send(embed=embed)

    @commands.command()
    async def botinfo(self, ctx):
        """Show information about Guard Bot."""
        total_members = sum(g.member_count for g in self.bot.guilds)
        embed = discord.Embed(title="🛡️  Guard Bot", colour=e(BLURPLE))
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.add_field(name="🏰  Servers",   value=f"`{len(self.bot.guilds)}`",   inline=True)
        embed.add_field(name="👥  Users",     value=f"`{total_members}`",          inline=True)
        embed.add_field(name="⚙️  Cogs",     value=f"`{len(self.bot.cogs)}`",     inline=True)
        embed.add_field(name="🔧  Commands", value=f"`{len(self.bot.commands)}`",  inline=True)
        embed.add_field(name="🏓  Latency",  value=f"`{round(self.bot.latency * 1000)}ms`", inline=True)
        embed.add_field(name="📌  Prefix",   value="`g!`",                         inline=True)
        embed.add_field(name="📖  Help",     value="`g!help`",                     inline=False)
        footer(embed, "Guard Bot")
        await ctx.send(embed=embed)

    # ── Role Management ────────────────────────────────────────────────────────

    @commands.command()
    @commands.has_permissions(manage_roles=True)
    async def role(self, ctx, member: discord.Member, role: discord.Role):
        """Add or remove a role from a member.

        Example: g!role @user @Moderator"""
        if role >= ctx.guild.me.top_role:
            return await ctx.send(embed=error_embed("I can't manage a role that is higher than or equal to my own!"))
        if role in member.roles:
            await member.remove_roles(role)
            embed = discord.Embed(title="➖  Role Removed", description=f"Removed {role.mention} from {member.mention}", colour=role.colour if role.colour.value else e(BLURPLE))
        else:
            await member.add_roles(role)
            embed = discord.Embed(title="➕  Role Added",   description=f"Gave {role.mention} to {member.mention}",       colour=role.colour if role.colour.value else e(BLURPLE))
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="👤  Member",    value=f"{member.mention} `{member.id}`", inline=True)
        embed.add_field(name="🎭  Role",      value=f"{role.mention} `{role.id}`",    inline=True)
        embed.add_field(name="🛡️  By",       value=ctx.author.mention,               inline=True)
        footer(embed)
        await ctx.send(embed=embed)

    @commands.command()
    @commands.has_permissions(manage_roles=True)
    async def createrole(self, ctx, *, name: str):
        """Create a new role with the given name.

        Example: g!createrole VIP Members"""
        role = await ctx.guild.create_role(name=name, reason=f"Created by {ctx.author}")
        embed = discord.Embed(title="✅  Role Created", description=f"{role.mention} has been created.", colour=role.colour if role.colour.value else e(GREEN))
        embed.add_field(name="🪪  ID", value=f"`{role.id}`", inline=True)
        footer(embed)
        await ctx.send(embed=embed)

    @commands.command()
    @commands.has_permissions(manage_roles=True)
    async def deleterole(self, ctx, role: discord.Role):
        """Delete a role.

        Example: g!deleterole @OldRole"""
        if role >= ctx.guild.me.top_role:
            return await ctx.send(embed=error_embed("I can't delete a role higher than my own."))
        name = role.name
        await role.delete(reason=f"Deleted by {ctx.author}")
        await ctx.send(embed=success_embed(f"Role **{name}** deleted."))

    @commands.command()
    @commands.has_permissions(manage_channels=True)
    async def createchannel(self, ctx, *, name: str):
        """Create a new text channel.

        Example: g!createchannel announcements"""
        channel = await ctx.guild.create_text_channel(name.replace(" ", "-"), reason=f"Created by {ctx.author}")
        await ctx.send(embed=success_embed(f"Channel {channel.mention} created."))

    @commands.command()
    @commands.has_permissions(manage_channels=True)
    async def deletechannel(self, ctx, channel: discord.TextChannel = None):
        """Delete a text channel.

        Example: g!deletechannel #old-channel"""
        target = channel or ctx.channel
        name = target.name
        await target.delete(reason=f"Deleted by {ctx.author}")
        if target != ctx.channel:
            await ctx.send(embed=success_embed(f"Channel **#{name}** deleted."))

    # ── Announcements / Messaging ──────────────────────────────────────────────

    @commands.command()
    @commands.has_permissions(manage_guild=True)
    async def announce(self, ctx, channel: discord.TextChannel, *, message: str):
        """Send an announcement embed to a channel.

        Parameters:
        channel: Destination channel
        message: Announcement content

        Example: g!announce #announcements Server maintenance tonight!"""
        embed = discord.Embed(
            title="📢  Announcement",
            description=message,
            colour=e(BLURPLE)
        )
        if ctx.guild.icon:
            embed.set_thumbnail(url=ctx.guild.icon.url)
        embed.set_footer(text=f"{ctx.guild.name}  •  {ctx.author}")
        embed.timestamp = datetime.utcnow()
        await channel.send(embed=embed)
        await ctx.send(embed=success_embed(f"Announcement sent to {channel.mention}."))

    @commands.command()
    @commands.has_permissions(manage_guild=True)
    async def say(self, ctx, channel: discord.TextChannel, *, message: str):
        """Make the bot say something in a channel.

        Example: g!say #general Hello everyone!"""
        try:
            await channel.send(message)
            await ctx.message.delete()
        except discord.Forbidden:
            await ctx.send(embed=error_embed("I can't send messages in that channel."))

    @commands.command()
    @commands.has_permissions(manage_guild=True)
    async def dm(self, ctx, member: discord.Member, *, message: str):
        """DM a member as the bot.

        Example: g!dm @user Welcome to the server!"""
        try:
            embed = discord.Embed(description=message, colour=e(BLURPLE))
            embed.set_footer(text=f"Message from {ctx.guild.name}")
            embed.timestamp = datetime.utcnow()
            await member.send(embed=embed)
            await ctx.send(embed=success_embed(f"DM sent to {member.mention}."))
        except discord.Forbidden:
            await ctx.send(embed=error_embed(f"Couldn't DM {member.mention}. They may have DMs disabled."))

    @commands.command()
    @commands.has_permissions(manage_guild=True)
    async def embed(self, ctx, title: str, *, description: str):
        """Send a custom embed to this channel.

        Parameters:
        title: Embed title (use quotes for spaces)
        description: Embed content

        Example: g!embed \"Server Rules\" Please follow the rules!"""
        custom_embed = discord.Embed(title=title, description=description, colour=e(BLURPLE))
        custom_embed.set_footer(text=ctx.guild.name)
        custom_embed.timestamp = datetime.utcnow()
        await ctx.send(embed=custom_embed)
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass

    # ── Emoji Management ───────────────────────────────────────────────────────

    @commands.command()
    @commands.has_permissions(manage_emojis=True)
    async def addemoji(self, ctx, name: str, url: str):
        """Add a custom emoji from a URL.

        Parameters:
        name: Name for the emoji
        url: Direct image URL

        Example: g!addemoji cool https://example.com/image.png"""
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return await ctx.send(embed=error_embed("Failed to download image."))
                data = await resp.read()
        try:
            emoji = await ctx.guild.create_custom_emoji(name=name, image=data, reason=f"Added by {ctx.author}")
            embed = discord.Embed(title="✅  Emoji Added", description=f"{emoji} `::{emoji.name}::`", colour=e(GREEN))
            footer(embed)
            await ctx.send(embed=embed)
        except discord.HTTPException as ex:
            await ctx.send(embed=error_embed(f"Failed: {ex}"))

    @commands.command()
    @commands.has_permissions(manage_emojis=True)
    async def steal(self, ctx, emoji: discord.PartialEmoji):
        """Steal an emoji from another server and add it here.

        Example: g!steal :CoolEmoji:"""
        async with aiohttp.ClientSession() as session:
            async with session.get(str(emoji.url)) as resp:
                if resp.status != 200:
                    return await ctx.send(embed=error_embed("Could not download the emoji."))
                data = await resp.read()
        try:
            new_emoji = await ctx.guild.create_custom_emoji(name=emoji.name, image=data, reason=f"Stolen by {ctx.author}")
            embed = discord.Embed(title="✅  Emoji Stolen", description=f"{new_emoji} added as `::{new_emoji.name}::`", colour=e(GREEN))
            footer(embed)
            await ctx.send(embed=embed)
        except discord.HTTPException as ex:
            await ctx.send(embed=error_embed(f"Failed: {ex}"))


async def setup(bot):
    await bot.add_cog(Admin(bot))
