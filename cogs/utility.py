import discord
from discord.ext import commands
import random
import re
import asyncio
from datetime import datetime, timedelta
from utils.helpers import error_embed, success_embed, footer, e, BLURPLE, GREEN, RED, YELLOW, FUCHSIA

EIGHT_BALL_RESPONSES = [
    ("✅ It is certain.",         GREEN),
    ("✅ Without a doubt.",       GREEN),
    ("✅ Yes, definitely.",       GREEN),
    ("✅ You may rely on it.",    GREEN),
    ("✅ As I see it, yes.",      GREEN),
    ("✅ Most likely.",           GREEN),
    ("✅ Signs point to yes.",    GREEN),
    ("🟡 Reply hazy, try again.", YELLOW),
    ("🟡 Ask again later.",       YELLOW),
    ("🟡 Cannot predict now.",   YELLOW),
    ("❌ Don't count on it.",     RED),
    ("❌ My reply is no.",        RED),
    ("❌ My sources say no.",     RED),
    ("❌ Very doubtful.",         RED),
    ("❌ Outlook not so good.",   RED),
]

class Utility(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.author.bot:
            return
        if not hasattr(self.bot, 'snipe_data'):
            self.bot.snipe_data = {}
        self.bot.snipe_data[message.channel.id] = {
            'content': message.content,
            'author':  message.author.id,
            'time':    datetime.utcnow()
        }

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if not hasattr(self.bot, 'afk_data'):
            self.bot.afk_data = {}

        afk_data = self.bot.afk_data

        # Clear AFK if the message author is AFK
        if message.author.id in afk_data:
            del afk_data[message.author.id]
            embed = discord.Embed(
                description=f"👋  Welcome back {message.author.mention}! Your AFK status has been removed.",
                colour=e(GREEN)
            )
            try:
                await message.channel.send(embed=embed, delete_after=5)
            except discord.Forbidden:
                pass

        # Notify if a mentioned user is AFK
        for mentioned in message.mentions:
            if mentioned.id in afk_data:
                info = afk_data[mentioned.id]
                embed = discord.Embed(
                    description=f"💤  {mentioned.mention} is **AFK**: {info.get('reason', 'No reason')} — <t:{int(info['time'].timestamp())}:R>",
                    colour=e(YELLOW)
                )
                try:
                    await message.channel.send(embed=embed, delete_after=8)
                except discord.Forbidden:
                    pass

    @commands.command(name="8ball")
    async def eightball(self, ctx, *, question: str):
        """Ask the magic 8-ball a question.

        Example: g!8ball Will I win?"""
        response, colour = random.choice(EIGHT_BALL_RESPONSES)
        embed = discord.Embed(title="🎱  Magic 8-Ball", colour=e(colour))
        embed.add_field(name="❓  Question", value=question[:300], inline=False)
        embed.add_field(name="🎱  Answer",   value=response,       inline=False)
        embed.set_thumbnail(url="https://cdn.discordapp.com/embed/avatars/3.png")
        footer(embed)
        await ctx.send(embed=embed)

    @commands.command()
    async def roll(self, ctx, dice: str = "1d6"):
        """Roll dice in NdN format.

        Parameters:
        dice: Dice notation (e.g. 2d6, 1d20, 3d8). Default: 1d6

        Example: g!roll 2d6"""
        match = re.fullmatch(r"(\d+)d(\d+)", dice.lower())
        if not match:
            return await ctx.send(embed=error_embed("Use dice notation like `2d6`, `1d20`, `3d8`."))
        n, sides = int(match.group(1)), int(match.group(2))
        if n > 100 or sides > 1000 or n < 1 or sides < 2:
            return await ctx.send(embed=error_embed("Use 1–100 dice with 2–1000 sides."))
        rolls = [random.randint(1, sides) for _ in range(n)]
        total = sum(rolls)
        embed = discord.Embed(title="🎲  Dice Roll", colour=e(BLURPLE))
        embed.add_field(name="🎲  Dice",    value=f"`{dice}`",                                          inline=True)
        embed.add_field(name="🔢  Rolls",   value=", ".join(f"`{r}`" for r in rolls[:20]),               inline=True)
        embed.add_field(name="➕  Total",   value=f"**{total}**",                                        inline=True)
        footer(embed)
        await ctx.send(embed=embed)

    @commands.command()
    async def coinflip(self, ctx):
        """Flip a coin — heads or tails."""
        result = random.choice(["Heads", "Tails"])
        emoji  = "🪙" if result == "Heads" else "🪙"
        embed  = discord.Embed(
            title=f"🪙  Coin Flip — **{result}**!",
            colour=e(YELLOW) if result == "Heads" else e(BLURPLE)
        )
        footer(embed)
        await ctx.send(embed=embed)

    @commands.command()
    async def choose(self, ctx, *, options: str):
        """Choose randomly between options separated by | or commas.

        Example: g!choose pizza | pasta | tacos"""
        choices = [o.strip() for o in re.split(r"[|,]", options) if o.strip()]
        if len(choices) < 2:
            return await ctx.send(embed=error_embed("Provide at least 2 options separated by `|` or `,`."))
        chosen = random.choice(choices)
        embed  = discord.Embed(title="🎯  I choose...", colour=e(FUCHSIA))
        embed.add_field(name="Options",  value="\n".join(f"• {c}" for c in choices[:20]), inline=True)
        embed.add_field(name="🎯  Pick", value=f"**{chosen}**",                            inline=True)
        footer(embed)
        await ctx.send(embed=embed)

    @commands.command()
    async def poll(self, ctx, *, question: str):
        """Create a simple yes/no poll with reactions.

        Example: g!poll Should we add a music bot?"""
        embed = discord.Embed(
            title="📊  Poll",
            description=f"**{question}**",
            colour=e(BLURPLE)
        )
        embed.add_field(name="\u200b", value="👍  Yes   |   👎  No", inline=False)
        embed.set_footer(text=f"Poll by {ctx.author} • React to vote!")
        embed.timestamp = datetime.utcnow()
        msg = await ctx.send(embed=embed)
        await msg.add_reaction("👍")
        await msg.add_reaction("👎")
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass

    @commands.command()
    async def remind(self, ctx, time: str, *, message: str):
        """Set a reminder. Time format: 10s, 5m, 2h, 1d.

        Parameters:
        time: Duration (e.g. 30s, 10m, 2h, 1d)
        message: What to remind you of

        Example: g!remind 30m Check the oven"""
        units = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}
        match = re.fullmatch(r"(\d+)([smhd])", time.lower())
        if not match:
            return await ctx.send(embed=error_embed("Time format: `30s`, `10m`, `2h`, `1d`"))
        seconds = int(match.group(1)) * units[match.group(2)]
        if seconds > 604800:
            return await ctx.send(embed=error_embed("Maximum reminder time is **7 days**."))

        remind_at = datetime.utcnow() + timedelta(seconds=seconds)
        embed = discord.Embed(
            title="⏰  Reminder Set",
            description=f"I'll remind you about: **{message}**",
            colour=e(GREEN)
        )
        embed.add_field(name="⏱️  In",   value=time,                                              inline=True)
        embed.add_field(name="🕐  At",   value=f"<t:{int(remind_at.timestamp())}:T>",              inline=True)
        footer(embed)
        await ctx.send(embed=embed)

        await asyncio.sleep(seconds)
        reminder_embed = discord.Embed(
            title="⏰  Reminder!",
            description=f"{ctx.author.mention}, you asked me to remind you:\n**{message}**",
            colour=e(YELLOW)
        )
        reminder_embed.add_field(name="📍  Set in", value=ctx.channel.mention, inline=True)
        footer(reminder_embed, "Guard Bot  •  Reminder")
        try:
            await ctx.send(content=ctx.author.mention, embed=reminder_embed)
        except Exception:
            pass

    @commands.command()
    async def afk(self, ctx, *, reason: str = "AFK"):
        """Set your AFK status. Bot will notify others who mention you.

        Example: g!afk Eating lunch"""
        if not hasattr(self.bot, 'afk_data'):
            self.bot.afk_data = {}
        self.bot.afk_data[ctx.author.id] = {'reason': reason, 'time': datetime.utcnow()}
        embed = discord.Embed(
            description=f"💤  {ctx.author.mention} is now **AFK**: {reason}",
            colour=e(YELLOW)
        )
        footer(embed)
        await ctx.send(embed=embed)

    @commands.command()
    async def snipe(self, ctx):
        """Show the last deleted message in this channel."""
        if not hasattr(self.bot, 'snipe_data'):
            self.bot.snipe_data = {}
        data = self.bot.snipe_data.get(ctx.channel.id)
        if not data:
            return await ctx.send(embed=discord.Embed(description="💨  Nothing to snipe here.", colour=e(BLURPLE)))
        author = ctx.guild.get_member(data['author'])
        embed  = discord.Embed(
            title="🔍  Sniped Message",
            description=data['content'][:2000] or "*[no text content]*",
            colour=e(FUCHSIA)
        )
        if author:
            embed.set_author(name=str(author), icon_url=author.display_avatar.url)
        embed.add_field(name="🗑️  Deleted", value=f"<t:{int(data['time'].timestamp())}:R>", inline=True)
        footer(embed)
        await ctx.send(embed=embed)

    @commands.command()
    async def timestamp(self, ctx, *, time_str: str = "now"):
        """Generate Discord timestamp formats for a given time.

        Example: g!timestamp now"""
        ts = int(datetime.utcnow().timestamp())
        embed = discord.Embed(title="🕐  Discord Timestamps", colour=e(BLURPLE))
        formats = [
            ("Short Time",     f"<t:{ts}:t>",  f"`<t:{ts}:t>`"),
            ("Long Time",      f"<t:{ts}:T>",  f"`<t:{ts}:T>`"),
            ("Short Date",     f"<t:{ts}:d>",  f"`<t:{ts}:d>`"),
            ("Long Date",      f"<t:{ts}:D>",  f"`<t:{ts}:D>`"),
            ("Short DateTime", f"<t:{ts}:f>",  f"`<t:{ts}:f>`"),
            ("Long DateTime",  f"<t:{ts}:F>",  f"`<t:{ts}:F>`"),
            ("Relative",       f"<t:{ts}:R>",  f"`<t:{ts}:R>`"),
        ]
        for label, rendered, code in formats:
            embed.add_field(name=label, value=f"{rendered}\n{code}", inline=True)
        footer(embed)
        await ctx.send(embed=embed)

    @commands.command()
    async def color(self, ctx, hex_code: str):
        """Show info and a preview for a hex colour.

        Parameters:
        hex_code: Hex colour code (e.g. FF5733 or #FF5733)

        Example: g!color #5865F2"""
        hex_code = hex_code.lstrip("#")
        if not re.fullmatch(r"[0-9a-fA-F]{6}", hex_code):
            return await ctx.send(embed=error_embed("Provide a valid 6-digit hex colour (e.g. `#FF5733`)."))
        int_val = int(hex_code, 16)
        r, g, b = int(hex_code[0:2], 16), int(hex_code[2:4], 16), int(hex_code[4:6], 16)
        embed = discord.Embed(
            title=f"🎨  #{hex_code.upper()}",
            colour=discord.Colour(int_val)
        )
        embed.add_field(name="🔴  Red",   value=str(r), inline=True)
        embed.add_field(name="🟢  Green", value=str(g), inline=True)
        embed.add_field(name="🔵  Blue",  value=str(b), inline=True)
        embed.add_field(name="🔢  Decimal", value=str(int_val),      inline=True)
        embed.add_field(name="🎨  Hex",     value=f"#{hex_code.upper()}", inline=True)
        embed.set_image(url=f"https://singlecolorimage.com/get/{hex_code}/200x100")
        footer(embed)
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Utility(bot))
