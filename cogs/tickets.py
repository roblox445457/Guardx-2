import discord
from discord.ext import commands
import logging
import json
import os
import io
from datetime import datetime
from utils.helpers import error_embed, success_embed, footer, e, BLURPLE, GREEN, RED, YELLOW

class TicketButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📩  Open Ticket", style=discord.ButtonStyle.blurple, custom_id="guard_ticket_open")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog = interaction.client.get_cog("Tickets")
        if cog:
            await cog.create_ticket(interaction)

class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config_file  = "data/tickets_config.json"
        self.active_file  = "data/tickets_active.json"
        os.makedirs("data", exist_ok=True)
        self.settings = {}
        self.active   = {}
        self._load_settings()
        bot.add_view(TicketButton())

    def _guild_settings(self, guild_id: int) -> dict:
        if guild_id not in self.settings:
            self.settings[guild_id] = {
                'category': None,
                'staff_role': None,
                'log_channel': None,
                'count': 0
            }
        return self.settings[guild_id]

    def _load_settings(self):
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    raw = json.load(f)
                self.settings = {int(k): v for k, v in raw.items()}
            if os.path.exists(self.active_file):
                with open(self.active_file, 'r') as f:
                    raw2 = json.load(f)
                self.active = {int(k): v for k, v in raw2.items()}
        except Exception as ex:
            logging.error(f"Tickets load error: {ex}")

    def _save_settings(self):
        try:
            with open(self.config_file, 'w') as f:
                json.dump({str(k): v for k, v in self.settings.items()}, f, indent=2)
            with open(self.active_file, 'w') as f:
                json.dump({str(k): v for k, v in self.active.items()}, f, indent=2)
        except Exception as ex:
            logging.error(f"Tickets save error: {ex}")

    async def create_ticket(self, interaction: discord.Interaction):
        guild = interaction.guild
        member = interaction.user
        gs = self._guild_settings(guild.id)

        # Check if user already has an open ticket
        for ch_id, info in self.active.items():
            if info.get('user') == member.id and info.get('guild') == guild.id:
                ch = guild.get_channel(ch_id)
                if ch:
                    return await interaction.response.send_message(
                        embed=error_embed(f"You already have an open ticket: {ch.mention}"),
                        ephemeral=True
                    )

        category = guild.get_channel(gs['category']) if gs['category'] else None
        staff_role = guild.get_role(gs['staff_role']) if gs['staff_role'] else None
        gs['count'] += 1
        ticket_num = gs['count']

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            member: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True)
        }
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

        try:
            channel = await guild.create_text_channel(
                name=f"ticket-{ticket_num:04d}",
                category=category,
                overwrites=overwrites,
                topic=f"Ticket by {member} ({member.id})"
            )
        except discord.Forbidden:
            return await interaction.response.send_message(embed=error_embed("I don't have permission to create channels."), ephemeral=True)

        self.active[channel.id] = {'user': member.id, 'guild': guild.id, 'claimed_by': None, 'number': ticket_num}
        self._save_settings()

        embed = discord.Embed(
            title=f"🎫  Ticket #{ticket_num:04d}",
            description=f"Welcome {member.mention}! Please describe your issue.\n\nA staff member will be with you shortly.",
            colour=e(BLURPLE)
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="📖  Commands", value=(
            "`g!ticket close` — close this ticket\n"
            "`g!ticket add @user` — add someone\n"
            "`g!ticket remove @user` — remove someone"
        ), inline=False)
        footer(embed, f"Guard Bot  •  Ticket #{ticket_num:04d}")

        close_view = discord.ui.View(timeout=None)
        close_btn = discord.ui.Button(label="🔒 Close Ticket", style=discord.ButtonStyle.red, custom_id=f"guard_ticket_close_{channel.id}")
        async def close_cb(inter):
            t_cog = inter.client.get_cog("Tickets")
            if t_cog:
                ctx_like = type('obj', (object,), {'guild': inter.guild, 'channel': inter.channel, 'author': inter.user})()
                await inter.response.defer()
                await t_cog._close_ticket(inter.channel, inter.user)
        close_btn.callback = close_cb
        close_view.add_item(close_btn)

        await channel.send(content=f"{member.mention}{' ' + staff_role.mention if staff_role else ''}", embed=embed, view=close_view)
        await interaction.response.send_message(embed=success_embed(f"Your ticket has been created: {channel.mention}"), ephemeral=True)

    async def _close_ticket(self, channel: discord.TextChannel, closer: discord.Member):
        if channel.id not in self.active:
            return
        info = self.active[channel.id]
        guild = channel.guild

        embed = discord.Embed(
            title="🔒  Ticket Closed",
            description=f"This ticket is being closed by {closer.mention}.",
            colour=e(RED)
        )
        footer(embed, "Guard Bot  •  Tickets")
        await channel.send(embed=embed)

        transcript = await self._generate_transcript(channel)

        user = guild.get_member(info['user'])
        if user:
            try:
                dm_embed = discord.Embed(
                    title="🎫  Your Ticket Was Closed",
                    description=f"Your ticket in **{guild.name}** has been closed by {closer.mention}.",
                    colour=e(BLURPLE)
                )
                footer(dm_embed, "Guard Bot  •  Tickets")
                await user.send(embed=dm_embed, file=transcript)
            except discord.Forbidden:
                pass

        del self.active[channel.id]
        self._save_settings()

        import asyncio
        await asyncio.sleep(3)
        try:
            await channel.delete(reason=f"Ticket closed by {closer}")
        except discord.Forbidden:
            pass

    async def _generate_transcript(self, channel: discord.TextChannel) -> discord.File:
        lines = []
        async for msg in channel.history(limit=500, oldest_first=True):
            ts = msg.created_at.strftime('%Y-%m-%d %H:%M:%S')
            lines.append(f"[{ts}] {msg.author}: {msg.content}")
            for att in msg.attachments:
                lines.append(f"[{ts}] {msg.author}: [Attachment: {att.url}]")
        content = "\n".join(lines) or "No messages."
        buf = io.BytesIO(content.encode())
        return discord.File(buf, filename=f"transcript-{channel.name}.txt")

    @commands.group(invoke_without_command=True)
    @commands.has_permissions(manage_channels=True)
    async def ticket(self, ctx):
        """Open a support ticket or manage tickets."""
        gs = self._guild_settings(ctx.guild.id)
        if not gs['category']:
            return await ctx.send(embed=error_embed("Tickets are not configured. Use `g!ticket setup` first."))

        # Open a ticket for the command author
        class FakeInteraction:
            def __init__(self, ctx):
                self.guild = ctx.guild
                self.user = ctx.author
                self.client = ctx.bot
                self._resp = None
            async def response_send(self, embed=None, ephemeral=False):
                await ctx.send(embed=embed)
            class response:
                @staticmethod
                async def send_message(embed=None, ephemeral=False):
                    pass

        # Instead, just create the ticket inline
        member = ctx.author
        for ch_id, info in self.active.items():
            if info.get('user') == member.id and info.get('guild') == ctx.guild.id:
                ch = ctx.guild.get_channel(ch_id)
                if ch:
                    return await ctx.send(embed=error_embed(f"You already have an open ticket: {ch.mention}"))

        category = ctx.guild.get_channel(gs['category']) if gs['category'] else None
        staff_role = ctx.guild.get_role(gs['staff_role']) if gs['staff_role'] else None
        gs['count'] += 1
        ticket_num = gs['count']

        overwrites = {
            ctx.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            member: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True),
            ctx.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True)
        }
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

        try:
            channel = await ctx.guild.create_text_channel(
                name=f"ticket-{ticket_num:04d}",
                category=category,
                overwrites=overwrites,
                topic=f"Ticket by {member} ({member.id})"
            )
        except discord.Forbidden:
            return await ctx.send(embed=error_embed("I don't have permission to create channels."))

        self.active[channel.id] = {'user': member.id, 'guild': ctx.guild.id, 'claimed_by': None, 'number': ticket_num}
        self._save_settings()

        embed = discord.Embed(
            title=f"🎫  Ticket #{ticket_num:04d}",
            description=f"Welcome {member.mention}! Please describe your issue.\n\nA staff member will be with you shortly.",
            colour=e(BLURPLE)
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        footer(embed, f"Guard Bot  •  Ticket #{ticket_num:04d}")
        await channel.send(content=f"{member.mention}{' ' + staff_role.mention if staff_role else ''}", embed=embed)
        await ctx.send(embed=success_embed(f"Ticket created: {channel.mention}"))

    @ticket.command(name="setup")
    @commands.has_permissions(administrator=True)
    async def ticket_setup(self, ctx, category: discord.CategoryChannel, staff_role: discord.Role):
        """Configure the ticket system.

        Parameters:
        category: Category where ticket channels will be created
        staff_role: Role that can see all tickets

        Example: g!ticket setup Support @Staff"""
        gs = self._guild_settings(ctx.guild.id)
        gs['category']   = category.id
        gs['staff_role'] = staff_role.id
        self._save_settings()
        embed = discord.Embed(title="✅  Ticket System Configured", colour=e(GREEN))
        embed.add_field(name="📁  Category",   value=category.name,   inline=True)
        embed.add_field(name="🎭  Staff Role", value=staff_role.mention, inline=True)
        embed.add_field(name="ℹ️  Next Step",  value="Use `g!ticket panel` to post the ticket panel.", inline=False)
        footer(embed)
        await ctx.send(embed=embed)

    @ticket.command(name="panel")
    @commands.has_permissions(manage_guild=True)
    async def ticket_panel(self, ctx, channel: discord.TextChannel = None):
        """Send the ticket open panel to a channel.

        Example: g!ticket panel #support"""
        target = channel or ctx.channel
        embed = discord.Embed(
            title="🎫  Support Tickets",
            description="Click the button below to open a support ticket.\nOur staff team will assist you as soon as possible.",
            colour=e(BLURPLE)
        )
        if ctx.guild.icon:
            embed.set_thumbnail(url=ctx.guild.icon.url)
        footer(embed, ctx.guild.name)
        await target.send(embed=embed, view=TicketButton())
        if target != ctx.channel:
            await ctx.send(embed=success_embed(f"Ticket panel sent to {target.mention}."))

    @ticket.command(name="close")
    async def ticket_close(self, ctx):
        """Close the current ticket channel."""
        if ctx.channel.id not in self.active:
            return await ctx.send(embed=error_embed("This is not a ticket channel."))
        info = self.active[ctx.channel.id]
        if ctx.author.id != info['user'] and not ctx.author.guild_permissions.manage_channels:
            return await ctx.send(embed=error_embed("You don't have permission to close this ticket."))
        await self._close_ticket(ctx.channel, ctx.author)

    @ticket.command(name="add")
    @commands.has_permissions(manage_channels=True)
    async def ticket_add(self, ctx, member: discord.Member):
        """Add a user to the current ticket.

        Example: g!ticket add @user"""
        if ctx.channel.id not in self.active:
            return await ctx.send(embed=error_embed("This is not a ticket channel."))
        await ctx.channel.set_permissions(member, view_channel=True, send_messages=True)
        await ctx.send(embed=success_embed(f"{member.mention} has been added to this ticket."))

    @ticket.command(name="remove")
    @commands.has_permissions(manage_channels=True)
    async def ticket_remove(self, ctx, member: discord.Member):
        """Remove a user from the current ticket.

        Example: g!ticket remove @user"""
        if ctx.channel.id not in self.active:
            return await ctx.send(embed=error_embed("This is not a ticket channel."))
        info = self.active[ctx.channel.id]
        if member.id == info['user']:
            return await ctx.send(embed=error_embed("You can't remove the ticket creator."))
        await ctx.channel.set_permissions(member, overwrite=None)
        await ctx.send(embed=success_embed(f"{member.mention} has been removed from this ticket."))

    @ticket.command(name="rename")
    @commands.has_permissions(manage_channels=True)
    async def ticket_rename(self, ctx, *, name: str):
        """Rename the current ticket channel.

        Example: g!ticket rename billing-issue"""
        if ctx.channel.id not in self.active:
            return await ctx.send(embed=error_embed("This is not a ticket channel."))
        safe_name = name.lower().replace(" ", "-")[:90]
        await ctx.channel.edit(name=safe_name)
        await ctx.send(embed=success_embed(f"Ticket renamed to `{safe_name}`."))

    @ticket.command(name="claim")
    @commands.has_permissions(manage_channels=True)
    async def ticket_claim(self, ctx):
        """Claim this ticket as a staff member."""
        if ctx.channel.id not in self.active:
            return await ctx.send(embed=error_embed("This is not a ticket channel."))
        info = self.active[ctx.channel.id]
        if info.get('claimed_by'):
            claimer = ctx.guild.get_member(info['claimed_by'])
            return await ctx.send(embed=error_embed(f"This ticket is already claimed by {claimer.mention if claimer else 'someone'}."))
        info['claimed_by'] = ctx.author.id
        self._save_settings()
        embed = discord.Embed(
            description=f"✋  {ctx.author.mention} has **claimed** this ticket.",
            colour=e(BLURPLE)
        )
        footer(embed, "Guard Bot  •  Tickets")
        await ctx.send(embed=embed)

    @ticket.command(name="unclaim")
    @commands.has_permissions(manage_channels=True)
    async def ticket_unclaim(self, ctx):
        """Unclaim this ticket."""
        if ctx.channel.id not in self.active:
            return await ctx.send(embed=error_embed("This is not a ticket channel."))
        info = self.active[ctx.channel.id]
        info['claimed_by'] = None
        self._save_settings()
        await ctx.send(embed=success_embed("Ticket unclaimed."))

    @ticket.command(name="transcript")
    @commands.has_permissions(manage_channels=True)
    async def ticket_transcript(self, ctx):
        """Save and DM the transcript of this ticket."""
        if ctx.channel.id not in self.active:
            return await ctx.send(embed=error_embed("This is not a ticket channel."))
        transcript = await self._generate_transcript(ctx.channel)
        try:
            await ctx.author.send(
                embed=discord.Embed(title=f"📄  Transcript — #{ctx.channel.name}", colour=e(BLURPLE)),
                file=transcript
            )
            await ctx.send(embed=success_embed("Transcript sent to your DMs."))
        except discord.Forbidden:
            await ctx.send(embed=error_embed("I couldn't DM you the transcript. Check your DM settings."))


async def setup(bot):
    await bot.add_cog(Tickets(bot))
