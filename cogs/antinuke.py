import discord
from discord.ext import commands
import logging
from datetime import datetime, timedelta
import asyncio
import aiohttp
from utils.helpers import error_embed, success_embed, footer, e, BLURPLE, GREEN, RED, YELLOW

class AntiNuke(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.enabled_guilds = set()
        self.whitelisted_users = {}
        self.config_file = "data/antinuke_settings.json"
        self.recently_deleted_channels = {}  # Store info about deleted channels
        
        # Create data directory if it doesn't exist
        import os
        os.makedirs("data", exist_ok=True)
        
        # Initialize action responses before loading settings
        self.action_responses = {
            'role_create': 'ban',
            'role_delete': 'ban',
            'role_update': 'ban',
            'channel_create': 'ban',
            'channel_delete': 'ban',
            'channel_update': 'ban',
            'ban': 'ban',
            'kick': 'ban',
            'webhook': 'ban',
            'bot_add': 'ban',
            'server_update': 'ban',
            'ping_everyone': 'ban',
            'emoji_delete': 'ban',
            'emoji_create': 'ban',
            'emoji_update': 'ban',
            'member_role_update': 'ban',
            'vanity_update': 'ban'
        }

        # Action types that can be whitelisted - must be initialized before _load_settings()
        self.action_types = {
            'role_create': True,
            'role_delete': True,
            'role_update': True,
            'channel_create': True,
            'channel_delete': True,
            'channel_update': True,
            'ban': True,
            'kick': True,
            'webhook': True,
            'bot_add': True,
            'server_update': True,
            'ping_everyone': True,
            'emoji_delete': True,
            'emoji_create': True,
            'emoji_update': True,
            'member_role_update': True,
            'vanity_update': True
        }

        # Load settings from file
        self._load_settings()

    def _is_trusted_user(self, member, action_type: str = None, guild_id=None) -> bool:
        """Check if a user is trusted for a specific action
        
        Users must be explicitly whitelisted to be trusted, regardless of permissions.
        Only server owners and explicitly whitelisted users are trusted.
        
        Args:
            member: A discord.Member or discord.User object
            action_type: The type of action being performed
            guild_id: The ID of the guild (required when member is a User not Member)
        """
        # Handle both Member and User objects
        if isinstance(member, discord.Member):
            # If it's a Member, we can access the guild directly
            guild_id = member.guild.id
            # Owner is always trusted (to prevent lockout)
            if member.id == member.guild.owner_id:
                return True
        elif not guild_id:
            # If we have a User but no guild_id, we can't check permissions
            return False
            
        # Check whitelist only - no automatic trust for administrators
        guild_whitelist = self.whitelisted_users.get(guild_id, {})
        user_permissions = guild_whitelist.get(member.id, set())

        # If action_type is specified, check if user is whitelisted for that action
        if action_type and action_type in user_permissions:
            return True

        # If action_type is None, check if user has 'all' permission
        if 'all' in user_permissions:
            return True
            
        # Not trusted if not explicitly whitelisted
        return False

    async def _handle_unauthorized_action(self, guild: discord.Guild, user, action_type: str, reason: str, revert_func=None):
        """Handle any unauthorized action with consistent protection"""
        # Check if antinuke is enabled for this guild
        if not guild.id in self.enabled_guilds:
            logging.info(f"Antinuke not enabled for guild {guild.id}")
            return False
            
        # Check if this specific action type is enabled
        if action_type in self.action_types and not self.action_types[action_type]:
            logging.info(f"Protection for {action_type} is disabled in guild {guild.id}")
            return False

        # Check if user is trusted for this specific action
        if user.id == self.bot.user.id or self._is_trusted_user(user, action_type, guild_id=guild.id):
            logging.info(f"Trusted user {user.id} performed {action_type} in guild {guild.id}")
            return False

        logging.info(f"Unauthorized {action_type} detected from user {user.id} in guild {guild.id}")
        action = self.action_responses[action_type]
        await self._take_action(guild, user, reason, action)

        if revert_func:
            try:
                await revert_func()
                logging.info(f"Successfully reverted {action_type} action in guild {guild.id}")
            except discord.Forbidden:
                logging.error(f"Failed to revert {action_type} - Missing permissions")
            except Exception as e:
                logging.error(f"Error reverting {action_type}: {str(e)}")

        return True

    async def _take_action(self, guild: discord.Guild, user: discord.Member, reason: str, action: str):
        """Take action against a user violating anti-nuke rules"""
        try:
            logging.info(f"Taking {action} action against user {user.id} in guild {guild.id} for: {reason}")

            if action == 'ban':
                await user.ban(reason=f"Anti-Nuke: {reason}")
                action_taken = "Banned"
            elif action == 'kick':
                await user.kick(reason=f"Anti-Nuke: {reason}")
                action_taken = "Kicked"
            elif action == 'removeroles':
                roles_to_remove = [r for r in user.roles if r.name != "@everyone"]
                if roles_to_remove:
                    await user.remove_roles(*roles_to_remove, reason=f"Anti-Nuke: {reason}")
                action_taken = "Removed roles from"

            # Log the action
            log_channel = discord.utils.get(guild.text_channels, name="mod-logs")
            if log_channel:
                embed = discord.Embed(
                    title="🛡️ Anti-Nuke Action",
                    description=f"{action_taken} {user.mention}\nReason: {reason}",
                    color=discord.Color.red()
                )
                await log_channel.send(embed=embed)

            logging.info(f"Successfully took action: {action_taken} user {user.id}")
        except discord.Forbidden:
            logging.error(f"Failed to take action against user {user.id} - Missing permissions")
        except Exception as e:
            logging.error(f"Error taking action against user {user.id}: {str(e)}")

    @commands.group(invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def antinuke(self, ctx):
        """Shows antinuke status and settings
        
        This command displays the current state of the anti-nuke protection system,
        including which actions are protected and how the system will respond
        to unauthorized actions. It also shows whitelisted users if any are configured."""
        enabled = ctx.guild.id in self.enabled_guilds
        embed = discord.Embed(
            title="🛡️ Anti-Nuke System",
            color=discord.Color.blue() if enabled else discord.Color.red()
        )

        # Show status and protected actions
        embed.add_field(name="Status", value="✅ Enabled" if enabled else "❌ Disabled")
        
        # Display all protections and their status
        protection_status = []
        for action, is_enabled in self.action_types.items():
            response = self.action_responses.get(action, 'ban')
            status_emoji = "✅" if enabled and is_enabled else "❌"
            protection_status.append(f"{status_emoji} {action.replace('_', ' ').title()} -> {response.title()}")
        
        embed.add_field(name="Protected Actions", value="\n".join(protection_status), inline=False)

        # Show whitelisted users if any
        guild_whitelist = self.whitelisted_users.get(ctx.guild.id, {})
        if guild_whitelist:
            # Organize users by their permissions
            whitelisted_by_perms = {}
            whitelisted_roles = {}
            
            # Group users with the same permissions
            for user_id, permissions in guild_whitelist.items():
                user = ctx.guild.get_member(user_id)
                if not user:
                    continue  # Skip users who are no longer in the server
                    
                perms_key = 'all' if 'all' in permissions else ','.join(sorted(permissions))
                if perms_key not in whitelisted_by_perms:
                    whitelisted_by_perms[perms_key] = []
                whitelisted_by_perms[perms_key].append(user)
                
                # Check if this user has a special role we should highlight
                for role in user.roles:
                    if role.id != ctx.guild.default_role.id:  # Skip @everyone role
                        role_key = str(role.id)
                        if role_key not in whitelisted_roles:
                            whitelisted_roles[role_key] = {'role': role, 'count': 0}
                        whitelisted_roles[role_key]['count'] += 1
            
            # Add whitelisted users section
            if whitelisted_by_perms:
                whitelist_text = []
                for perms_key, users in whitelisted_by_perms.items():
                    if perms_key == 'all':
                        perms_display = 'All Events'
                    else:
                        perms_list = perms_key.split(',')
                        perms_display = ', '.join(p.replace('_', ' ').title() for p in perms_list)
                    
                    # Limit to first 10 users to avoid overflow
                    display_users = users[:10]
                    mentions = ' '.join(user.mention for user in display_users)
                    
                    if len(users) > 10:
                        mentions += f" and {len(users) - 10} more..."
                        
                    whitelist_text.append(f"**{perms_display}**: {mentions}")
                
                embed.add_field(name="Whitelisted Users", value="\n".join(whitelist_text), inline=False)
            
            # Add whitelisted roles section if we have identified any 
            if whitelisted_roles:
                # Get roles with at least 3 whitelisted users to highlight common patterns
                common_roles = sorted(
                    [info for info in whitelisted_roles.values() if info['count'] >= 3],
                    key=lambda x: x['count'], 
                    reverse=True
                )[:5]  # Top 5 most common roles
                
                if common_roles:
                    role_text = []
                    for role_info in common_roles:
                        role = role_info['role']
                        count = role_info['count']
                        role_text.append(f"{role.mention}: {count} whitelisted members")
                    
                    # Add note about role whitelisting
                    role_text.append("\n*Use `g!antinuke whitelist role_add` to whitelist a role directly*")
                    
                    embed.add_field(name="Common Roles", value="\n".join(role_text), inline=False)

        await ctx.send(embed=embed)

    @antinuke.group(name="whitelist")
    @commands.has_permissions(manage_guild=True)
    async def whitelist(self, ctx):
        """Manage whitelisted users and roles for anti-nuke protection
        
        This command lets you add users or roles to the whitelist, allowing them
        to perform actions that would normally trigger anti-nuke protection.
        
        Subcommands:
        - add: Add a user to the whitelist
        - remove: Remove a user from the whitelist
        - role_add: Add a role to the whitelist (all members with this role will be trusted)
        - role_remove: Remove a role from the whitelist
        """
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(
                title="📋  Whitelist Management",
                description="Manage trusted users who bypass Anti-Nuke protection.",
                colour=e(BLURPLE)
            )
            embed.add_field(name="Subcommands", value=(
                "`g!antinuke whitelist add @user` — whitelist a user\n"
                "`g!antinuke whitelist remove @user` — remove a user\n"
                "`g!antinuke whitelist role_remove @role` — remove a role"
            ), inline=False)
            footer(embed)
            await ctx.send(embed=embed)

    @whitelist.command(name="add")
    @commands.has_permissions(manage_guild=True)
    async def whitelist_add(self, ctx, member: discord.Member):
        """Whitelist a user or bot to bypass anti-nuke protections
        
        This command lets you add a user or bot to the whitelist for specific events
        like role creation, channel deletion, etc. Whitelisted users can perform
        these actions without triggering the anti-nuke protection.
        
        Parameters:
        member: The member to whitelist (can be a user or bot)"""
        if member.bot:
            embed = discord.Embed(description=f"⚠️  You are whitelisting a **bot account** ({member.mention}). Proceed with caution.", colour=e(YELLOW))
            footer(embed)
            await ctx.send(embed=embed)

        # Initialize guild's whitelist if it doesn't exist
        if ctx.guild.id not in self.whitelisted_users:
            self.whitelisted_users[ctx.guild.id] = {}

        # Create event selection message
        events_list = "\n".join([
            f"{idx + 1}. {event.replace('_', ' ').title()}"
            for idx, event in enumerate(['all'] + list(self.action_types.keys()))
        ])

        sel_embed = discord.Embed(
            title="📋  Event Selection",
            description=(
                f"Select events to whitelist for {member.mention}\n"
                "Reply with the event numbers (comma-separated) or `all` for all events.\n\n"
                f"{events_list}"
            ),
            colour=e(BLURPLE)
        )
        footer(sel_embed)
        await ctx.send(embed=sel_embed)

        try:
            response = await self.bot.wait_for(
                'message',
                timeout=30.0,
                check=lambda m: m.author == ctx.author and m.channel == ctx.channel
            )

            selected_events = set()
            if response.content.lower() == 'all':
                selected_events.add('all')
            else:
                try:
                    indices = [int(i.strip()) - 1 for i in response.content.split(',')]
                    events = ['all'] + list(self.action_types.keys())
                    for idx in indices:
                        if 0 <= idx < len(events):
                            selected_events.add(events[idx])
                except ValueError:
                    return await ctx.send(embed=error_embed("Invalid input! Please use numbers or `all`."))

            self.whitelisted_users[ctx.guild.id][member.id] = selected_events
            self._save_settings()

            events_str = 'All Events' if 'all' in selected_events else ', '.join(ev.replace('_', ' ').title() for ev in selected_events)
            conf = discord.Embed(
                title="✅  User Whitelisted",
                colour=e(GREEN)
            )
            conf.set_thumbnail(url=member.display_avatar.url)
            conf.add_field(name="👤  User",         value=f"{member.mention} `{member.id}`", inline=True)
            conf.add_field(name="📋  Whitelisted For", value=events_str,                     inline=True)
            footer(conf)
            await ctx.send(embed=conf)
            logging.info(f"Whitelisted user {member.id} for events {events_str} in guild {ctx.guild.id}")

        except asyncio.TimeoutError:
            await ctx.send(embed=error_embed("Event selection timed out!"))
            
    @whitelist.command(name="remove")
    @commands.has_permissions(manage_guild=True)
    async def whitelist_remove(self, ctx, member: discord.Member):
        """Remove a user from the anti-nuke whitelist
        
        This command removes a user from the whitelist, making them subject
        to all anti-nuke protection rules. After removal, the user will no longer
        be able to perform protected actions without triggering anti-nuke responses.
        
        Parameters:
        member: The member to remove from the whitelist
        
        Example: g!antinuke whitelist remove @username"""
        if ctx.guild.id not in self.whitelisted_users or member.id not in self.whitelisted_users.get(ctx.guild.id, {}):
            return await ctx.send(embed=error_embed(f"{member.mention} is not on the whitelist!"))

        if member.id == ctx.guild.owner_id:
            embed = discord.Embed(description="⚠️  The server owner is **always trusted** by default and cannot be removed from the whitelist.", colour=e(YELLOW))
            footer(embed)
            return await ctx.send(embed=embed)

        del self.whitelisted_users[ctx.guild.id][member.id]
        self._save_settings()

        conf = discord.Embed(title="✅  User Removed from Whitelist", colour=e(GREEN))
        conf.set_thumbnail(url=member.display_avatar.url)
        conf.add_field(name="👤  User", value=f"{member.mention} `{member.id}`", inline=True)
        footer(conf)
        await ctx.send(embed=conf)
        logging.info(f"Removed user {member.id} from whitelist in guild {ctx.guild.id}")
    
    @whitelist.command(name="role_add")
    @commands.has_permissions(manage_guild=True)
    async def whitelist_role_add(self, ctx, *, role: str):
        """Whitelist a role to bypass anti-nuke protections
        
        Parameters:
        role: The role name or ID to whitelist
        """
        # Try to find the role
        try:
            # First try to convert from mention or ID
            role_id = int(''.join(filter(str.isdigit, role)))
            found_role = ctx.guild.get_role(role_id)
        except (ValueError, TypeError):
            # If that fails, try to find by name
            found_role = discord.utils.get(ctx.guild.roles, name=role)
            
        if not found_role:
            return await ctx.send(embed=error_embed(f"Could not find role `{role}`. Use the role name, ID, or mention."))
            
        role = found_role
        # Initialize guild's whitelist if it doesn't exist
        if ctx.guild.id not in self.whitelisted_users:
            self.whitelisted_users[ctx.guild.id] = {}
            
        # Create event selection message
        events_list = "\n".join([
            f"{idx + 1}. {event.replace('_', ' ').title()}"
            for idx, event in enumerate(['all'] + list(self.action_types.keys()))
        ])

        sel_embed2 = discord.Embed(
            title="📋  Event Selection",
            description=(
                f"Select events to whitelist for role {role.mention}\n"
                "Reply with the event numbers (comma-separated) or `all` for all events.\n\n"
                f"{events_list}"
            ),
            colour=e(BLURPLE)
        )
        footer(sel_embed2)
        await ctx.send(embed=sel_embed2)

        try:
            response = await self.bot.wait_for(
                'message',
                timeout=30.0,
                check=lambda m: m.author == ctx.author and m.channel == ctx.channel
            )

            selected_events = set()
            if response.content.lower() == 'all':
                selected_events.add('all')
            else:
                try:
                    indices = [int(i.strip()) - 1 for i in response.content.split(',')]
                    events = ['all'] + list(self.action_types.keys())
                    for idx in indices:
                        if 0 <= idx < len(events):
                            selected_events.add(events[idx])
                except ValueError:
                    return await ctx.send(embed=error_embed("Invalid input! Please use numbers or `all`."))

            members_added = 0
            for member in ctx.guild.members:
                if role in member.roles:
                    self.whitelisted_users[ctx.guild.id][member.id] = selected_events
                    members_added += 1

            self._save_settings()

            events_str = 'All Events' if 'all' in selected_events else ', '.join(ev.replace('_', ' ').title() for ev in selected_events)
            conf = discord.Embed(title="✅  Role Whitelisted", colour=e(GREEN))
            conf.add_field(name="🎭  Role",            value=role.mention,         inline=True)
            conf.add_field(name="👥  Members Added",   value=f"`{members_added}`", inline=True)
            conf.add_field(name="📋  Whitelisted For", value=events_str,           inline=False)
            footer(conf)
            await ctx.send(embed=conf)
            logging.info(f"Whitelisted role {role.id} with {members_added} members for events {events_str} in guild {ctx.guild.id}")

        except asyncio.TimeoutError:
            await ctx.send(embed=error_embed("Event selection timed out!"))
            
    @whitelist.command(name="role_remove")
    @commands.has_permissions(manage_guild=True)
    async def whitelist_role_remove(self, ctx, role: discord.Role):
        """Remove a role from the anti-nuke whitelist
        
        This command removes a role from the whitelist. Members with this role
        will no longer be automatically trusted unless they are individually
        whitelisted or have another whitelisted role.
        
        Parameters:
        role: The role to remove from the whitelist
        
        Example: g!antinuke whitelist role_remove @Trusted
        """
        if ctx.guild.id not in self.whitelisted_users:
            return await ctx.send(embed=error_embed("No roles are whitelisted in this server!"))

        members_removed = 0
        for member in ctx.guild.members:
            if role in member.roles and member.id in self.whitelisted_users[ctx.guild.id]:
                del self.whitelisted_users[ctx.guild.id][member.id]
                members_removed += 1

        self._save_settings()

        if members_removed > 0:
            conf = discord.Embed(title="✅  Role Removed from Whitelist", colour=e(GREEN))
            conf.add_field(name="🎭  Role",             value=role.mention,           inline=True)
            conf.add_field(name="👥  Members Removed",  value=f"`{members_removed}`", inline=True)
            footer(conf)
            await ctx.send(embed=conf)
        else:
            embed = discord.Embed(description=f"⚠️  No members with role {role.mention} were on the whitelist.", colour=e(YELLOW))
            footer(embed)
            await ctx.send(embed=embed)


    @antinuke.command()
    @commands.has_permissions(administrator=True)
    async def action(self, ctx, action_response: str = None):
        """Configure anti-nuke actions and responses
        
        This command lets you set what action will be taken when unauthorized
        server changes are detected. You can choose between kick, ban, or
        removing roles from the user who performed the action.
        
        Parameters:
        action_response: The response action (kick, ban, or removeroles) for all events
        
        Example: g!antinuke action ban  (bans users who trigger anti-nuke protection)
        """
        if not action_response:
            current_actions = set(self.action_responses.values())
            embed = discord.Embed(title="⚖️  Anti-Nuke Action Setting", colour=e(BLURPLE))
            if len(current_actions) == 1:
                action = next(iter(current_actions))
                embed.description = f"All protections currently use: **{action}**"
            else:
                embed.description = "Actions vary by protection type. Use `g!antinuke action <kick|ban|removeroles>` to set one for all."
            footer(embed)
            return await ctx.send(embed=embed)

        action_response = action_response.lower()
        if action_response not in ['kick', 'ban', 'removeroles']:
            return await ctx.send(embed=error_embed("Invalid action. Use `kick`, `ban`, or `removeroles`."))

        if action_response == 'ban' and not ctx.author.guild_permissions.ban_members:
            return await ctx.send(embed=error_embed("You need the **Ban Members** permission to set ban as the action!"))
        elif action_response == 'kick' and not ctx.author.guild_permissions.kick_members:
            return await ctx.send(embed=error_embed("You need the **Kick Members** permission to set kick as the action!"))
        elif action_response == 'removeroles' and not ctx.author.guild_permissions.manage_roles:
            return await ctx.send(embed=error_embed("You need the **Manage Roles** permission to set removeroles as the action!"))

        for action_type in self.action_types.keys():
            self.action_responses[action_type] = action_response
        self._save_settings()

        action_icons = {'ban': '🔨', 'kick': '👢', 'removeroles': '🎭'}
        embed = discord.Embed(
            title=f"{action_icons.get(action_response, '⚖️')}  Anti-Nuke Action Updated",
            description=f"All protections will now **{action_response}** any unauthorized user.",
            colour=e(GREEN)
        )
        footer(embed)
        await ctx.send(embed=embed)
        logging.info(f"Updated all action responses to {action_response} in guild {ctx.guild.id}")

    def _save_settings(self):
        """Save all settings to file"""
        import json
        try:
            settings = {
                'enabled_guilds': list(self.enabled_guilds),
                'whitelisted_users': {str(k): {str(uk): list(uv) for uk, uv in v.items()} 
                                     for k, v in self.whitelisted_users.items()},
                'action_responses': self.action_responses,
                'action_types': self.action_types
            }
            with open(self.config_file, 'w') as f:
                json.dump(settings, f)
            logging.info("Anti-Nuke settings saved to file")
        except Exception as e:
            logging.error(f"Failed to save Anti-Nuke settings: {str(e)}")
            
    def _load_settings(self):
        """Load settings from file"""
        import json
        import os
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    settings = json.load(f)
                
                self.enabled_guilds = set(settings.get('enabled_guilds', []))
                
                # Load action types (which protections are enabled)
                if 'action_types' in settings:
                    for key, value in settings['action_types'].items():
                        if key in self.action_types:
                            self.action_types[key] = value
                
                # Convert string keys back to integers for guild IDs and user IDs
                self.whitelisted_users = {
                    int(k): {int(uk): set(uv) for uk, uv in v.items()}
                    for k, v in settings.get('whitelisted_users', {}).items()
                }
                
                self.action_responses = settings.get('action_responses', self.action_responses)
                logging.info("Anti-Nuke settings loaded from file")
            else:
                # Initialize with empty settings if file doesn't exist
                self.enabled_guilds = set()
                self.whitelisted_users = {}
                logging.info("No existing Anti-Nuke settings found, using defaults")
        except Exception as e:
            logging.error(f"Failed to load Anti-Nuke settings: {str(e)}")
            self.enabled_guilds = set()
            self.whitelisted_users = {}

    @antinuke.command()
    @commands.has_permissions(administrator=True)
    async def enable(self, ctx):
        """Enable the anti-nuke protection system
        
        This command enables the anti-nuke system for the current server.
        When enabled, all server actions will be monitored for potential nuke attempts
        and the bot will automatically respond to unauthorized actions according to
        your configured settings.
        
        IMPORTANT: Users must be explicitly whitelisted to perform administrative actions.
        Even server administrators will be affected by Anti-Nuke unless they are whitelisted.
        
        Example: g!antinuke enable"""
        # Check for highest required permission based on current action
        current_action = next(iter(set(self.action_responses.values())), 'ban')
        if current_action == 'ban' and not ctx.author.guild_permissions.ban_members:
            return await ctx.send(embed=error_embed("You need the **Ban Members** permission to enable Anti-Nuke with ban action!"))
        elif current_action == 'kick' and not ctx.author.guild_permissions.kick_members:
            return await ctx.send(embed=error_embed("You need the **Kick Members** permission to enable Anti-Nuke with kick action!"))
        elif current_action == 'removeroles' and not ctx.author.guild_permissions.manage_roles:
            return await ctx.send(embed=error_embed("You need the **Manage Roles** permission to enable Anti-Nuke with removeroles action!"))

        if ctx.guild.id in self.enabled_guilds:
            embed = discord.Embed(description="✅  Anti-Nuke system is **already enabled**. Use `g!antinuke disable` to manage protections.", colour=e(GREEN))
            footer(embed)
            return await ctx.send(embed=embed)
            
        # When enabling, check if there are any whitelisted users
        guild_whitelist = self.whitelisted_users.get(ctx.guild.id, {})
        if not guild_whitelist and ctx.author.id != ctx.guild.owner_id:
            warning_embed = discord.Embed(
                title="⚠️ Strict Whitelist Warning",
                description=(
                    "You are about to enable Anti-Nuke with no whitelisted users!\n\n"
                    "**IMPORTANT**: Only the server owner and explicitly whitelisted users will be able to "
                    "make changes to the server. Even administrators will trigger Anti-Nuke protection "
                    "unless they are whitelisted.\n\n"
                    "It's recommended to whitelist yourself and other trusted admins first."
                ),
                color=discord.Color.gold()
            )
            warning_embed.add_field(
                name="Whitelist Command", 
                value=f"Use `g!antinuke whitelist add @user` to whitelist trusted administrators."
            )
            
            # Add a button to acknowledge and proceed
            await ctx.send(embed=warning_embed)
            conf_embed = discord.Embed(description="Type `confirm` to enable Anti-Nuke or `cancel` to abort.", colour=e(YELLOW))
            footer(conf_embed)
            await ctx.send(embed=conf_embed)

            try:
                response = await self.bot.wait_for(
                    'message',
                    timeout=30.0,
                    check=lambda m: m.author == ctx.author and m.channel == ctx.channel and m.content.lower() in ['confirm', 'cancel']
                )
                if response.content.lower() != 'confirm':
                    return await ctx.send(embed=error_embed("Activation cancelled. Use `g!antinuke whitelist add` to whitelist trusted users first."))
            except asyncio.TimeoutError:
                return await ctx.send(embed=error_embed("Operation timed out. Anti-Nuke has **not** been enabled."))
        
        # Make sure all protections are enabled
        for key in self.action_types:
            self.action_types[key] = True
            
        # Enabling the system
        self.enabled_guilds.add(ctx.guild.id)
        logging.info(f"Anti-Nuke enabled for guild {ctx.guild.id}")
        
        # Whitelist the server owner if not already whitelisted
        if ctx.guild.owner_id and ctx.guild.id in self.whitelisted_users and ctx.guild.owner_id not in self.whitelisted_users[ctx.guild.id]:
            logging.info(f"Automatically whitelisting server owner {ctx.guild.owner_id} in guild {ctx.guild.id}")
        
        # Save settings after changing enabled state
        self._save_settings()
        
        embed = discord.Embed(
            title="🛡️  Anti-Nuke Enabled",
            description=(
                "All server actions are now being monitored.\n\n"
                "⚠️  Only **whitelisted users** and the **server owner** can perform admin actions without triggering protection."
            ),
            colour=e(GREEN)
        )
        embed.add_field(name="⚖️  Action",  value=f"`{current_action}`",                    inline=True)
        embed.add_field(name="👥  Whitelist", value=f"`{len(self.whitelisted_users.get(ctx.guild.id, {}))}` users", inline=True)
        footer(embed, "Guard Bot  •  Anti-Nuke")
        await ctx.send(embed=embed)
        
    @antinuke.command()
    @commands.has_permissions(administrator=True)
    async def disable(self, ctx):
        """Disable specific anti-nuke protections
        
        This command lets you disable the entire anti-nuke system or specific protections.
        You can choose which events should no longer be monitored and protected.
        
        Example: g!antinuke disable"""
        
        if ctx.guild.id not in self.enabled_guilds:
            embed = discord.Embed(description="❌  Anti-Nuke is **already disabled** for this server.", colour=e(RED))
            footer(embed)
            return await ctx.send(embed=embed)

        options_embed = discord.Embed(
            title="🛡️  Disable Anti-Nuke Protection",
            description="What would you like to disable?",
            colour=e(BLURPLE)
        )
        options_embed.add_field(name="1️⃣  Disable Everything",       value="Completely turn off all anti-nuke protection", inline=False)
        options_embed.add_field(name="2️⃣  Disable Specific Events",  value="Choose individual events to stop monitoring",  inline=False)
        footer(options_embed)
        await ctx.send(embed=options_embed)

        try:
            response = await self.bot.wait_for(
                'message',
                timeout=30.0,
                check=lambda m: m.author == ctx.author and m.channel == ctx.channel and m.content in ['1', '2']
            )

            if response.content == '1':
                self.enabled_guilds.remove(ctx.guild.id)
                self._save_settings()
                logging.info(f"Anti-Nuke disabled for guild {ctx.guild.id}")
                embed = discord.Embed(
                    title="❌  Anti-Nuke Disabled",
                    description="All server protections have been turned off.",
                    colour=e(RED)
                )
                footer(embed, "Guard Bot  •  Anti-Nuke")
                await ctx.send(embed=embed)

            elif response.content == '2':
                events_list = "\n".join([
                    f"{idx + 1}. {event.replace('_', ' ').title()}"
                    for idx, event in enumerate(self.action_types.keys())
                ])
                events_embed = discord.Embed(
                    title="📋  Select Events to Disable",
                    description=(
                        "Reply with the event numbers (comma-separated) you want to stop monitoring.\n\n"
                        f"{events_list}"
                    ),
                    colour=e(BLURPLE)
                )
                footer(events_embed)
                await ctx.send(embed=events_embed)

                try:
                    event_response = await self.bot.wait_for(
                        'message',
                        timeout=60.0,
                        check=lambda m: m.author == ctx.author and m.channel == ctx.channel
                    )
                    try:
                        indices = [int(i.strip()) - 1 for i in event_response.content.split(',')]
                        events = list(self.action_types.keys())
                        disabled_events = []
                        for idx in indices:
                            if 0 <= idx < len(events):
                                self.action_types[events[idx]] = False
                                disabled_events.append(events[idx].replace('_', ' ').title())

                        if disabled_events:
                            self._save_settings()
                            embed = discord.Embed(
                                title="✅  Protections Disabled",
                                description="\n".join(f"• {ev}" for ev in disabled_events),
                                colour=e(YELLOW)
                            )
                            footer(embed, "Guard Bot  •  Anti-Nuke")
                            await ctx.send(embed=embed)
                        else:
                            await ctx.send(embed=error_embed("No valid events selected!"))
                    except ValueError:
                        await ctx.send(embed=error_embed("Invalid input! Use numbers separated by commas."))
                except asyncio.TimeoutError:
                    await ctx.send(embed=error_embed("Event selection timed out!"))

        except asyncio.TimeoutError:
            await ctx.send(embed=error_embed("Selection timed out!"))

    # Event Listeners
    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        """Handles role creation events"""
        async for entry in role.guild.audit_logs(action=discord.AuditLogAction.role_create, limit=1):
            await self._handle_unauthorized_action(
                role.guild, entry.user, 'role_create',
                "Unauthorized role creation",
                lambda: role.delete(reason="Anti-Nuke: Unauthorized role creation")
            )

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        # Store role properties before processing
        role_name = role.name
        role_color = role.color
        role_permissions = role.permissions
        role_hoist = role.hoist
        role_mentionable = role.mentionable
        role_position = role.position
        
        async for entry in role.guild.audit_logs(action=discord.AuditLogAction.role_delete, limit=1):
            action_taken = await self._handle_unauthorized_action(
                role.guild, entry.user, 'role_delete',
                "Unauthorized role deletion"
            )
            
            # If action was taken against the user, recreate the role
            if action_taken:
                try:
                    # Recreate the role with the same properties
                    new_role = await role.guild.create_role(
                        name=role_name,
                        permissions=role_permissions,
                        color=role_color,
                        hoist=role_hoist,
                        mentionable=role_mentionable,
                        reason="Anti-Nuke: Recreating deleted role"
                    )
                    
                    # Try to restore position (might not work exactly due to role hierarchy)
                    try:
                        await new_role.edit(position=role_position)
                    except:
                        pass
                        
                    # Log the action
                    log_channel = discord.utils.get(role.guild.text_channels, name="mod-logs")
                    if log_channel:
                        embed = discord.Embed(
                            title="🛡️ Role Recreated",
                            description=f"Role '{role_name}' has been recreated after unauthorized deletion",
                            color=discord.Color.green()
                        )
                        await log_channel.send(embed=embed)
                        
                    logging.info(f"Successfully recreated role {role_name} in guild {role.guild.id}")
                except Exception as e:
                    logging.error(f"Failed to recreate role {role_name}: {str(e)}")
                    
                    # Attempt to notify in mod-logs
                    log_channel = discord.utils.get(role.guild.text_channels, name="mod-logs")
                    if log_channel:
                        embed = discord.Embed(
                            title="⚠️ Role Recreation Failed",
                            description=f"Failed to recreate role '{role_name}' after unauthorized deletion.\nError: {str(e)}",
                            color=discord.Color.red()
                        )
                        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        async for entry in channel.guild.audit_logs(action=discord.AuditLogAction.channel_create, limit=1):
            await self._handle_unauthorized_action(
                channel.guild, entry.user, 'channel_create',
                "Unauthorized channel creation",
                lambda: channel.delete(reason="Anti-Nuke: Unauthorized channel creation")
            )

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        # Store channel properties before processing
        channel_name = channel.name
        channel_type = channel.type
        channel_topic = getattr(channel, 'topic', None)
        channel_position = channel.position
        channel_nsfw = getattr(channel, 'nsfw', False)
        channel_category = channel.category
        channel_slowmode = getattr(channel, 'slowmode_delay', 0)
        channel_permissions = channel.overwrites
        
        # If it's a category, store its channels for recreation later
        category_channels = []
        if channel_type == discord.ChannelType.category:
            for ch in channel.guild.channels:
                if ch.category_id == channel.id:
                    # Store all properties of child channels
                    child_props = {
                        'name': ch.name,
                        'type': ch.type,
                        'position': ch.position,
                        'permissions': ch.overwrites
                    }
                    
                    # Add channel type specific properties
                    if ch.type == discord.ChannelType.text or ch.type == discord.ChannelType.news:
                        child_props['topic'] = getattr(ch, 'topic', None)
                        child_props['nsfw'] = getattr(ch, 'nsfw', False)
                        child_props['slowmode'] = getattr(ch, 'slowmode_delay', 0)
                    
                    category_channels.append(child_props)
        
        # Use rate limiter to prevent hitting Discord API limits
        guild_id = str(channel.guild.id)
        can_proceed = await self.bot.audit_limiter.is_rate_limited(f"audit_{guild_id}")
        if not can_proceed:
            logging.warning(f"Skipping audit log check for channel deletion in guild {guild_id} due to rate limits")
            # Even if rate limited, we should still try to recreate the channel
            # Store channel info so we don't lose it while waiting for rate limit to reset
            self.recently_deleted_channels[channel.guild.id] = self.recently_deleted_channels.get(channel.guild.id, []) + [{
                'name': channel_name,
                'type': channel_type,
                'topic': channel_topic,
                'position': channel_position,
                'nsfw': channel_nsfw,
                'category': channel_category,
                'slowmode': channel_slowmode,
                'permissions': channel_permissions,
                'timestamp': datetime.now()
            }]
            # We'll continue with the recreation logic even if rate limited

        # Process audit logs to check for unauthorized deletions
        action_taken = False
        entry = None
        try:
            async for log_entry in channel.guild.audit_logs(action=discord.AuditLogAction.channel_delete, limit=1):
                entry = log_entry
                action_taken = await self._handle_unauthorized_action(
                    channel.guild, entry.user, 'channel_delete',
                    "Unauthorized channel deletion"
                )
        except Exception as e:
            logging.error(f"Error checking audit logs for channel deletion: {str(e)}")
            return
        
        # If action was taken against the user, recreate the channel
        if action_taken:
            try:
                new_channel = None
                # Recreate the channel with the same properties
                if channel_type == discord.ChannelType.text:
                    new_channel = await channel.guild.create_text_channel(
                        name=channel_name,
                        topic=channel_topic,
                        position=channel_position,
                        nsfw=channel_nsfw,
                        category=channel_category,
                        slowmode_delay=channel_slowmode,
                        overwrites=channel_permissions,
                        reason="Anti-Nuke: Recreating deleted channel"
                    )
                elif channel_type == discord.ChannelType.voice:
                    new_channel = await channel.guild.create_voice_channel(
                        name=channel_name,
                        position=channel_position,
                        category=channel_category,
                        overwrites=channel_permissions,
                        reason="Anti-Nuke: Recreating deleted channel"
                    )
                elif channel_type == discord.ChannelType.category:
                    new_channel = await channel.guild.create_category(
                        name=channel_name,
                        position=channel_position,
                        overwrites=channel_permissions,
                        reason="Anti-Nuke: Recreating deleted category"
                    )
                    
                    # If it was a category, recreate all its channels
                    for ch_props in category_channels:
                        try:
                            if ch_props['type'] == discord.ChannelType.text:
                                await channel.guild.create_text_channel(
                                    name=ch_props['name'],
                                    topic=ch_props.get('topic'),
                                    position=ch_props['position'],
                                    nsfw=ch_props.get('nsfw', False),
                                    category=new_channel,  # Place in the newly created category
                                    slowmode_delay=ch_props.get('slowmode', 0),
                                    overwrites=ch_props['permissions'],
                                    reason="Anti-Nuke: Recreating deleted category channel"
                                )
                            elif ch_props['type'] == discord.ChannelType.voice:
                                await channel.guild.create_voice_channel(
                                    name=ch_props['name'],
                                    position=ch_props['position'],
                                    category=new_channel,  # Place in the newly created category
                                    overwrites=ch_props['permissions'],
                                    reason="Anti-Nuke: Recreating deleted category channel"
                                )
                            elif ch_props['type'] == discord.ChannelType.news:
                                await channel.guild.create_text_channel(
                                    name=ch_props['name'],
                                    topic=ch_props.get('topic'),
                                    position=ch_props['position'],
                                    nsfw=ch_props.get('nsfw', False),
                                    category=new_channel,  # Place in the newly created category
                                    overwrites=ch_props['permissions'],
                                    reason="Anti-Nuke: Recreating deleted news channel"
                                )
                        except Exception as e:
                            logging.error(f"Error recreating child channel {ch_props['name']}: {str(e)}")
                            
                elif channel_type == discord.ChannelType.news:
                    new_channel = await channel.guild.create_text_channel(
                        name=channel_name,
                        topic=channel_topic,
                        position=channel_position,
                        nsfw=channel_nsfw,
                        category=channel_category,
                        overwrites=channel_permissions,
                        reason="Anti-Nuke: Recreating deleted news channel"
                    )
                
                # Log the action
                log_channel = discord.utils.get(channel.guild.text_channels, name="mod-logs")
                if log_channel:
                    if channel_type == discord.ChannelType.category:
                        # Special log message for categories
                        embed = discord.Embed(
                            title="🛡️ Category Recreated",
                            description=f"Recreated deleted category `{channel_name}` with all its channels",
                            color=discord.Color.green()
                        )
                        # Add information about how many channels were recreated
                        if category_channels:
                            channels_info = f"Recreated {len(category_channels)} channel(s) inside this category"
                            embed.add_field(name="Child Channels", value=channels_info)
                    else:
                        # Standard log message for other channels
                        embed = discord.Embed(
                            title="🛡️ Channel Recreated",
                            description=f"Recreated deleted channel `{channel_name}`",
                            color=discord.Color.green()
                        )
                    
                    embed.add_field(name="Channel Type", value=str(channel_type).replace("ChannelType.", ""))
                    embed.add_field(name="Deleted By", value=f"{entry.user.mention} ({entry.user.id})")
                    embed.set_footer(text=f"Anti-Nuke Protection | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                    await log_channel.send(embed=embed)
            
            except Exception as e:
                # Log any errors that occur during recreation
                logging.error(f"Error recreating channel {channel_name}: {str(e)}")
                log_channel = discord.utils.get(channel.guild.text_channels, name="mod-logs")
                if log_channel:
                    embed = discord.Embed(
                        title="⚠️ Channel Recreation Failed",
                        description=f"Failed to recreate channel `{channel_name}`",
                        color=discord.Color.red()
                    )
                    embed.add_field(name="Error", value=str(e))
                    embed.set_footer(text=f"Anti-Nuke Protection | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                    await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before, after):
        # Use rate limiter to prevent hitting Discord API limits
        guild_id = str(after.guild.id)
        can_proceed = await self.bot.audit_limiter.is_rate_limited(f"audit_{guild_id}")
        if not can_proceed:
            logging.warning(f"Skipping audit log check for channel update in guild {guild_id} due to rate limits")
            # We'll continue and try to perform action even if rate limited
            
        try:
            async for entry in after.guild.audit_logs(action=discord.AuditLogAction.channel_update, limit=1):
                await self._handle_unauthorized_action(
                    after.guild, entry.user, 'channel_update',
                    "Unauthorized channel update"
                )
        except Exception as e:
            logging.error(f"Error checking audit logs for channel update: {str(e)}")

    @commands.Cog.listener()
    async def on_guild_update(self, before, after):
        # Use rate limiter to prevent hitting Discord API limits
        guild_id = str(after.id)
        can_proceed = await self.bot.audit_limiter.is_rate_limited(f"audit_{guild_id}")
        if not can_proceed:
            logging.warning(f"Skipping audit log check for guild update in guild {guild_id} due to rate limits")
            # We'll continue and try to perform action even if rate limited
            
        try:
            async for entry in after.audit_logs(action=discord.AuditLogAction.guild_update, limit=1):
                await self._handle_unauthorized_action(
                    after, entry.user, 'server_update',
                    "Unauthorized server update",
                    lambda: after.edit(
                        name=before.name,
                        verification_level=before.verification_level,
                        explicit_content_filter=before.explicit_content_filter,
                        afk_channel=before.afk_channel,
                        afk_timeout=before.afk_timeout,
                        default_notifications=before.default_notifications,
                        reason="Anti-Nuke: Reverting unauthorized changes"
                    )
                )
        except Exception as e:
            logging.error(f"Error checking audit logs for guild update: {str(e)}")

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if before.roles != after.roles:
            async for entry in after.guild.audit_logs(action=discord.AuditLogAction.member_role_update, limit=1):
                await self._handle_unauthorized_action(
                    after.guild, entry.user, 'member_role_update',
                    "Unauthorized role updates",
                    lambda: after.edit(roles=before.roles, reason="Anti-Nuke: Reverting unauthorized role changes")
                )

    @commands.Cog.listener()
    async def on_webhooks_update(self, channel):
        async for entry in channel.guild.audit_logs(action=discord.AuditLogAction.webhook_create, limit=1):
            await self._handle_unauthorized_action(
                channel.guild, entry.user, 'webhook',
                "Unauthorized webhook creation",
                lambda: entry.target.delete(reason="Anti-Nuke: Unauthorized webhook creation") if entry.target else None
            )

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        async for entry in guild.audit_logs(action=discord.AuditLogAction.ban, limit=1):
            if await self._handle_unauthorized_action(
                guild, entry.user, 'ban',
                "Unauthorized ban"
            ):
                await guild.unban(user, reason="Anti-Nuke: Reverting unauthorized ban")

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        async for entry in member.guild.audit_logs(action=discord.AuditLogAction.kick, limit=1):
            if entry.target.id == member.id:
                await self._handle_unauthorized_action(
                    member.guild, entry.user, 'kick',
                    "Unauthorized kick"
                )

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if member.bot:
            # Verified Discord bots (blue checkmark) are automatically whitelisted
            if member.public_flags.verified_bot:
                guild_id = member.guild.id
                if guild_id not in self.whitelisted_users:
                    self.whitelisted_users[guild_id] = {}
                # Whitelist for all action types
                self.whitelisted_users[guild_id][member.id] = set(self.action_types.keys())
                self._save_settings()
                logging.info(f"Auto-whitelisted verified bot {member.id} ({member.name}) in guild {guild_id}")

                # Post a notice to system channel if available
                system_channel = member.guild.system_channel
                if system_channel:
                    embed = discord.Embed(
                        title="✅  Verified Bot Auto-Whitelisted",
                        description=f"{member.mention} is a **Discord-verified bot** and has been automatically trusted by Anti-Nuke.",
                        colour=discord.Colour(0x57F287)
                    )
                    embed.set_thumbnail(url=member.display_avatar.url)
                    embed.set_footer(text="Guard Bot  •  Anti-Nuke")
                    import datetime
                    embed.timestamp = datetime.datetime.utcnow()
                    try:
                        await system_channel.send(embed=embed)
                    except discord.Forbidden:
                        pass
                return  # Skip anti-nuke check for verified bots

            # Unverified bots — run the normal anti-nuke check
            async for entry in member.guild.audit_logs(action=discord.AuditLogAction.bot_add, limit=1):
                await self._handle_unauthorized_action(
                    member.guild, entry.user, 'bot_add',
                    "Unauthorized bot addition",
                    lambda: member.kick(reason="Anti-Nuke: Unauthorized bot addition")
                )

    @commands.Cog.listener()
    async def on_guild_emojis_update(self, guild, before, after):
        # Use rate limiter to prevent hitting Discord API limits
        guild_id = str(guild.id)
        can_proceed = await self.bot.audit_limiter.is_rate_limited(f"audit_{guild_id}")
        if not can_proceed:
            logging.warning(f"Skipping audit log check for emoji update in guild {guild_id} due to rate limits")
            # We'll continue and try to perform action even if rate limited
            
        # Find emojis that were deleted (exist in before but not in after)
        deleted_emojis = [emoji for emoji in before if emoji not in after]
        
        # Find emojis that were added (exist in after but not in before)
        added_emojis = [emoji for emoji in after if emoji not in before]
        
        # Handle emoji deletion
        if deleted_emojis:
            async for entry in guild.audit_logs(action=discord.AuditLogAction.emoji_delete, limit=1):
                if entry.user.id == self.bot.user.id or self._is_trusted_user(entry.user):
                    continue
                
                # Find which emoji was deleted
                deleted_emoji = None
                for emoji in deleted_emojis:
                    if entry.target and entry.target.id == emoji.id:
                        deleted_emoji = emoji
                        break
                
                if deleted_emoji:
                    action_taken = await self._handle_unauthorized_action(
                        guild, entry.user, 'emoji_delete', 
                        "Unauthorized emoji deletion"
                    )
                    
                    # If action was taken against the user, recreate the emoji immediately
                    if action_taken:
                        try:
                            # Get emoji image
                            emoji_url = deleted_emoji.url
                            async with aiohttp.ClientSession() as session:
                                async with session.get(str(emoji_url)) as resp:
                                    if resp.status == 200:
                                        emoji_bytes = await resp.read()
                                        # Recreate the emoji
                                        new_emoji = await guild.create_custom_emoji(
                                            name=deleted_emoji.name,
                                            image=emoji_bytes,
                                            reason="Anti-Nuke: Recreating deleted emoji"
                                        )
                                        
                                        # Log the recreation
                                        log_channel = discord.utils.get(guild.text_channels, name="mod-logs")
                                        if log_channel:
                                            embed = discord.Embed(
                                                title="🛡️ Emoji Recreated",
                                                description=f"Recreated deleted emoji `{deleted_emoji.name}`",
                                                color=discord.Color.green()
                                            )
                                            embed.add_field(name="Deleted By", value=f"{entry.user.mention} ({entry.user.id})")
                                            embed.set_footer(text=f"Anti-Nuke Protection | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                                            embed.set_thumbnail(url=new_emoji.url)
                                            await log_channel.send(embed=embed)
                        except Exception as e:
                            logging.error(f"Error recreating emoji {deleted_emoji.name}: {str(e)}")
                            log_channel = discord.utils.get(guild.text_channels, name="mod-logs")
                            if log_channel:
                                embed = discord.Embed(
                                    title="⚠️ Emoji Recreation Failed",
                                    description=f"Failed to recreate emoji `{deleted_emoji.name}`",
                                    color=discord.Color.red()
                                )
                                embed.add_field(name="Error", value=str(e))
                                embed.set_footer(text=f"Anti-Nuke Protection | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                                await log_channel.send(embed=embed)
        
        # Handle emoji creation
        if added_emojis:
            async for entry in guild.audit_logs(action=discord.AuditLogAction.emoji_create, limit=1):
                if entry.user.id == self.bot.user.id or self._is_trusted_user(entry.user):
                    continue
                    
                action_taken = await self._handle_unauthorized_action(
                    guild, entry.user, 'emoji_create', 
                    "Unauthorized emoji creation"
                )
                
                # If action was taken, delete the newly created emoji immediately
                if action_taken and entry.target:
                    try:
                        await entry.target.delete(reason="Anti-Nuke: Unauthorized emoji creation")
                    except Exception as e:
                        logging.error(f"Error deleting unauthorized emoji: {str(e)}")
        
        # Handle emoji updates
        async for entry in guild.audit_logs(action=discord.AuditLogAction.emoji_update, limit=1):
            if entry.user.id == self.bot.user.id or self._is_trusted_user(entry.user):
                continue
                
            await self._handle_unauthorized_action(
                guild, entry.user, 'emoji_update', 
                "Unauthorized emoji update"
            )

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.mention_everyone:
            await self._handle_unauthorized_action(message.guild, message.author, 'ping_everyone', "Unauthorized everyone mention", lambda: message.delete())

    @commands.Cog.listener()
    async def on_guild_vanity_url_update(self, guild, before, after):
        async for entry in guild.audit_logs(action=discord.AuditLogAction.guild_update, limit=1):
            await self._handle_unauthorized_action(
                guild, entry.user, 'vanity_update', "Unauthorized vanity URL change",
                lambda: guild.edit(vanity_code=before.code)
            )

async def setup(bot):
    await bot.add_cog(AntiNuke(bot))