import discord
from discord.ext import commands
import logging
import json
import os
import re
from utils.helpers import error_embed, success_embed, footer, e, BLURPLE, GREEN, RED, YELLOW

class WordFilter(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config_file = "data/wordfilter_settings.json"
        os.makedirs("data", exist_ok=True)
        self.settings = {}
        self._load_settings()

    def _load_settings(self):
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    raw = json.load(f)
                self.settings = {int(k): v for k, v in raw.items()}
                logging.info("Word filter settings loaded from file")
            else:
                logging.info("No existing word filter settings found, using defaults")
        except Exception as ex:
            logging.error(f"Failed to load word filter settings: {ex}")
            self.settings = {}

    def _save_settings(self):
        try:
            with open(self.config_file, 'w') as f:
                json.dump({str(k): v for k, v in self.settings.items()}, f)
        except Exception as ex:
            logging.error(f"Failed to save word filter settings: {ex}")

    def _guild_settings(self, guild_id: int) -> dict:
        if guild_id not in self.settings:
            self.settings[guild_id] = {'enabled': False, 'words': []}
        return self.settings[guild_id]

    def _contains_filtered_word(self, content: str, words: list):
        lowered = content.lower()
        for word in words:
            if re.search(r'\b' + re.escape(word.lower()) + r'\b', lowered):
                return word
        return None

    # ── Listener ───────────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        gs = self._guild_settings(message.guild.id)
        if not gs['enabled'] or not gs['words']:
            return
        if message.author.guild_permissions.manage_messages:
            return

        matched = self._contains_filtered_word(message.content, gs['words'])
        if matched:
            try:
                await message.delete()
            except discord.Forbidden:
                pass

            warn_embed = discord.Embed(
                description=f"🚫  {message.author.mention} That word is not allowed here.",
                colour=e(RED)
            )
            footer(warn_embed, "Guard Bot  •  Word Filter")
            try:
                await message.channel.send(embed=warn_embed, delete_after=5)
            except discord.Forbidden:
                pass

            log_channel = discord.utils.get(message.guild.text_channels, name="mod-logs")
            if log_channel:
                embed = discord.Embed(
                    title="🚫  Word Filter Triggered",
                    colour=e(0xEB459E)
                )
                embed.set_thumbnail(url=message.author.display_avatar.url)
                embed.add_field(name="👤  User",          value=f"{message.author.mention} `{message.author.id}`", inline=True)
                embed.add_field(name="💬  Channel",        value=message.channel.mention,                           inline=True)
                embed.add_field(name="🔤  Matched Word",   value=f"||`{matched}`||",                                inline=True)
                embed.add_field(name="📝  Message",        value=f"||{message.content[:400]}||" if message.content else "*empty*", inline=False)
                footer(embed, "Guard Bot  •  Word Filter")
                await log_channel.send(embed=embed)

    # ── Commands ───────────────────────────────────────────────────────────────

    @commands.group(invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def wordfilter(self, ctx):
        """Manage the word filter for this server."""
        gs     = self._guild_settings(ctx.guild.id)
        status = "✅  Enabled" if gs['enabled'] else "❌  Disabled"
        colour = e(GREEN) if gs['enabled'] else e(RED)

        embed = discord.Embed(
            title="🚫  Word Filter",
            colour=colour
        )
        embed.add_field(name="📊  Status",         value=status,                  inline=True)
        embed.add_field(name="📋  Filtered Words", value=f"`{len(gs['words'])}`", inline=True)
        embed.add_field(
            name="📖  Commands",
            value=(
                "`g!wordfilter enable`  — turn on\n"
                "`g!wordfilter disable` — turn off\n"
                "`g!wordfilter add <word>` — block a word\n"
                "`g!wordfilter remove <word>` — unblock a word\n"
                "`g!wordfilter list` — show all blocked words"
            ),
            inline=False
        )
        footer(embed)
        await ctx.send(embed=embed)

    @wordfilter.command(name="enable")
    @commands.has_permissions(manage_guild=True)
    async def wordfilter_enable(self, ctx):
        """Enable the word filter for this server."""
        gs = self._guild_settings(ctx.guild.id)
        if gs['enabled']:
            return await ctx.send(embed=discord.Embed(
                description="✅  Word filter is **already enabled**.",
                colour=e(GREEN)
            ))
        gs['enabled'] = True
        self._save_settings()
        embed = discord.Embed(
            title="✅  Word Filter Enabled",
            description="Messages containing blocked words will be **automatically deleted**.",
            colour=e(GREEN)
        )
        embed.add_field(name="📋  Blocked Words", value=f"`{len(gs['words'])}`", inline=True)
        footer(embed)
        await ctx.send(embed=embed)

    @wordfilter.command(name="disable")
    @commands.has_permissions(manage_guild=True)
    async def wordfilter_disable(self, ctx):
        """Disable the word filter for this server."""
        gs = self._guild_settings(ctx.guild.id)
        if not gs['enabled']:
            return await ctx.send(embed=discord.Embed(
                description="❌  Word filter is **already disabled**.",
                colour=e(RED)
            ))
        gs['enabled'] = False
        self._save_settings()
        embed = discord.Embed(
            title="❌  Word Filter Disabled",
            description="No messages will be filtered.",
            colour=e(RED)
        )
        footer(embed)
        await ctx.send(embed=embed)

    @wordfilter.command(name="add")
    @commands.has_permissions(manage_guild=True)
    async def wordfilter_add(self, ctx, *, word: str):
        """Add a word to the filter list.

        Parameters:
        word: The word or phrase to block

        Example: g!wordfilter add badword"""
        word = word.strip().lower()
        if not word:
            return await ctx.send(embed=error_embed("Please provide a word to add."))

        gs = self._guild_settings(ctx.guild.id)
        if word in gs['words']:
            return await ctx.send(embed=discord.Embed(
                description=f"⚠️  `{word}` is **already** in the filter list.",
                colour=e(0xFEE75C)
            ))

        gs['words'].append(word)
        self._save_settings()
        embed = discord.Embed(
            title="✅  Word Added",
            description=f"Added `{word}` to the word filter.",
            colour=e(GREEN)
        )
        embed.add_field(name="📋  Total Filtered Words", value=f"`{len(gs['words'])}`", inline=True)
        footer(embed)
        await ctx.send(embed=embed)

    @wordfilter.command(name="remove")
    @commands.has_permissions(manage_guild=True)
    async def wordfilter_remove(self, ctx, *, word: str):
        """Remove a word from the filter list.

        Parameters:
        word: The word or phrase to unblock

        Example: g!wordfilter remove badword"""
        word = word.strip().lower()
        gs   = self._guild_settings(ctx.guild.id)
        if word not in gs['words']:
            return await ctx.send(embed=error_embed(f"`{word}` is not in the filter list."))

        gs['words'].remove(word)
        self._save_settings()
        embed = discord.Embed(
            title="✅  Word Removed",
            description=f"Removed `{word}` from the word filter.",
            colour=e(GREEN)
        )
        embed.add_field(name="📋  Remaining Filtered Words", value=f"`{len(gs['words'])}`", inline=True)
        footer(embed)
        await ctx.send(embed=embed)

    @wordfilter.command(name="list")
    @commands.has_permissions(manage_guild=True)
    async def wordfilter_list(self, ctx):
        """Show all currently filtered words."""
        gs    = self._guild_settings(ctx.guild.id)
        words = gs['words']

        if not words:
            embed = discord.Embed(
                title="📋  Word Filter List",
                description="The list is empty. Add words with `g!wordfilter add <word>`.",
                colour=e(BLURPLE)
            )
            footer(embed)
            return await ctx.send(embed=embed)

        chunks = [words[i:i + 30] for i in range(0, len(words), 30)]
        for idx, chunk in enumerate(chunks):
            embed = discord.Embed(
                title=f"🚫  Filtered Words — {len(words)} total" + (f"  (Page {idx+1}/{len(chunks)})" if len(chunks) > 1 else ""),
                description="\n".join(f"• `{w}`" for w in chunk),
                colour=e(0xEB459E)
            )
            embed.add_field(name="📊  Filter Status", value="✅ Enabled" if gs['enabled'] else "❌ Disabled", inline=True)
            footer(embed)
            await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(WordFilter(bot))
