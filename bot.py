import discord
from discord.ext import commands
import logging
import os
import time
import asyncio
from collections import defaultdict

logger = logging.getLogger(__name__)

class RateLimiter:
    def __init__(self, max_calls, period):
        self.calls = defaultdict(list)
        self.max_calls = max_calls
        self.period = period
    
    async def is_rate_limited(self, key):
        """Check if the operation is rate limited and sleeps if necessary
        
        Returns:
            bool: True if operation should proceed, False if completely rate limited
        """
        current_time = time.time()
        self.calls[key] = [call_time for call_time in self.calls[key] 
                          if current_time - call_time < self.period]
        
        if len(self.calls[key]) >= self.max_calls:
            oldest_call = min(self.calls[key])
            wait_time = self.period - (current_time - oldest_call)
            
            if wait_time > 5:
                return False
                
            logger.warning(f"Rate limited for {key}. Waiting {wait_time:.2f} seconds")
            await asyncio.sleep(wait_time)
        
        self.calls[key].append(time.time())
        return True

BOT_OWNER_ID = 1230660770749087796

class DiscordBot(commands.Bot):
    def __init__(self):
        logger.info("Configuring bot intents...")
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True

        logger.info("Initializing bot...")
        super().__init__(
            command_prefix='g!',
            intents=intents,
            help_command=commands.DefaultHelpCommand()
        )

        self.audit_limiter = RateLimiter(max_calls=2, period=10)
        self.guild_settings = {}

        # Shared in-memory state accessible across cogs
        self.warnings_data = {}
        self.invite_cache  = {}
        self.afk_data      = {}
        self.snipe_data    = {}

        logger.info("Setting up cogs...")
        self.initial_extensions = [
            'cogs.moderation',
            'cogs.security',
            'cogs.admin',
            'cogs.antinuke',
            'cogs.logging',
            'cogs.wordfilter',
            'cogs.antispam',
            'cogs.autorole',
            'cogs.welcome',
            'cogs.warnings',
            'cogs.tickets',
            'cogs.invites',
            'cogs.verification',
            'cogs.starboard',
            'cogs.utility',
            'cogs.help',
        ]

    async def setup_hook(self):
        logger.info("Loading extensions...")
        for ext in self.initial_extensions:
            try:
                await self.load_extension(ext)
                logger.info(f'Loaded extension: {ext}')
            except Exception as e:
                logger.error(f'Failed to load extension {ext}: {str(e)}', exc_info=True)

    async def on_ready(self):
        logger.info(f'Successfully logged in as {self.user.name} (ID: {self.user.id})')
        logger.info(f'Connected to {len(self.guilds)} guilds')
        await self.change_presence(activity=discord.Game(name="g!help | Guard"))

    async def on_guild_join(self, guild):
        logger.info(f"Joined new guild: {guild.name} (ID: {guild.id})")
        self.guild_settings[guild.id] = {
            'antinuke': {
                'enabled': False,
                'whitelist': [],
                'action': 'ban'
            },
            'logging': {
                'mod_log': None,
                'server_log': None,
                'message_log': None
            },
            'automod': {
                'enabled': True,
                'spam_protection': True,
                'link_filter': True,
                'mention_limit': 5
            }
        }

        try:
            logger.info(f"Creating log channels for guild {guild.id}")
            category    = await guild.create_category('Guard Logs')
            mod_log     = await guild.create_text_channel('mod-logs',     category=category)
            server_log  = await guild.create_text_channel('server-logs',  category=category)
            message_log = await guild.create_text_channel('message-logs', category=category)

            self.guild_settings[guild.id]['logging'].update({
                'mod_log':     mod_log.id,
                'server_log':  server_log.id,
                'message_log': message_log.id
            })

            embed = discord.Embed(
                title="Guard",
                description="Thank you for adding Guard! I've set up the logging channels.\nUse `g!help` to see available commands.",
                color=discord.Color.blue()
            )
            if guild.system_channel:
                await guild.system_channel.send(embed=embed)
        except discord.Forbidden:
            logger.warning(f"Couldn't create log channels in guild {guild.id} - Missing permissions")
        except Exception as e:
            logger.error(f"Error setting up guild {guild.id}: {str(e)}", exc_info=True)

    async def on_command_error(self, ctx, error):
        import discord
        from utils.helpers import error_embed, e

        if isinstance(error, commands.errors.CheckFailure):
            if ctx.author.id == BOT_OWNER_ID:
                await ctx.command.reinvoke(ctx)
                return
            embed = discord.Embed(description="🔒  You don't have permission to use this command.", colour=discord.Colour(0xED4245))
            embed.set_footer(text="Guard Bot")
            await ctx.send(embed=embed)
        elif isinstance(error, commands.errors.MissingRequiredArgument):
            embed = discord.Embed(
                description=f"📋  Missing argument: `{error.param.name}`. Use `g!help {ctx.command}` for usage.",
                colour=discord.Colour(0xFEE75C)
            )
            embed.set_footer(text="Guard Bot")
            await ctx.send(embed=embed)
        elif isinstance(error, commands.errors.MemberNotFound):
            embed = discord.Embed(description=f"👤  Member `{error.argument}` not found.", colour=discord.Colour(0xED4245))
            embed.set_footer(text="Guard Bot")
            await ctx.send(embed=embed)
        elif isinstance(error, commands.errors.RoleNotFound):
            embed = discord.Embed(description=f"🎭  Role `{error.argument}` not found.", colour=discord.Colour(0xED4245))
            embed.set_footer(text="Guard Bot")
            await ctx.send(embed=embed)
        elif isinstance(error, commands.errors.CommandNotFound):
            pass
        else:
            logger.error(f'Command error: {str(error)}', exc_info=True)
            embed = discord.Embed(description="⚙️  Something went wrong. Please try again.", colour=discord.Colour(0xED4245))
            embed.set_footer(text="Guard Bot")
            await ctx.send(embed=embed)
