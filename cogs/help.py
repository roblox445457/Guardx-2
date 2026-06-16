import discord
from discord.ext import commands
from datetime import datetime

class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.remove_command("help")

        self.category_icons = {
            "Admin":        "⚙️",
            "Moderation":   "🔨",
            "Security":     "🔒",
            "AntiNuke":     "🛡️",
            "AntiSpam":     "🚨",
            "AutoRole":     "🎭",
            "Welcome":      "👋",
            "Warnings":     "⚠️",
            "Tickets":      "🎫",
            "Invites":      "📨",
            "Verification": "✅",
            "Starboard":    "⭐",
            "Utility":      "🔧",
            "Logging":      "📝",
            "WordFilter":   "🚫",
            "Help":         "❓",
        }

        self.category_descriptions = {
            "Admin":        "Server management & info commands",
            "Moderation":   "Kick, ban, mute, warn & more",
            "Security":     "AutoMod, raid protection & lockdown",
            "AntiNuke":     "Protection against server nukes",
            "AntiSpam":     "Auto-punish message spammers",
            "AutoRole":     "Auto-assign roles on join",
            "Welcome":      "Welcome & goodbye messages",
            "Warnings":     "Warning auto-punishment thresholds",
            "Tickets":      "Support ticket system",
            "Invites":      "Track who invited who",
            "Verification": "Reaction-based member verification",
            "Starboard":    "Pin popular messages to a channel",
            "Utility":      "Fun & useful utility commands",
            "Logging":      "Audit log & event logging",
            "WordFilter":   "Block unwanted words",
        }

    def _collect_commands(self, cmd, prefix="g!"):
        """Recursively collect all command names, including nested subcommands."""
        results = [f"`{prefix}{cmd.name}`"]
        if isinstance(cmd, commands.Group):
            for sub in cmd.commands:
                if not sub.hidden:
                    results.extend(self._collect_commands(sub, prefix=f"{prefix}{cmd.name} "))
        return results

    @commands.command()
    async def help(self, ctx, command_name=None):
        """Shows all available commands or info about a specific command."""
        if command_name:
            command = self.bot.get_command(command_name)
            if command:
                cog_name = command.cog_name or "Misc"
                icon = self.category_icons.get(cog_name, "📋")

                help_text  = command.help or "No description available."
                description, parameters, examples = help_text, [], []
                if help_text:
                    lines = help_text.split('\n')
                    section, content = 'description', []
                    for line in lines:
                        line = line.strip()
                        if line == "Parameters:":
                            if section == 'description' and content:
                                description = '\n'.join(content).strip()
                            content, section = [], 'parameters'
                        elif line in ("Example:", "Examples:") or line.startswith("Example:"):
                            if section == 'description' and content:
                                description = '\n'.join(content).strip()
                            elif section == 'parameters':
                                parameters = content
                            content, section = [], 'examples'
                        elif line:
                            content.append(line)
                    if content:
                        if section == 'description':  description = '\n'.join(content).strip()
                        elif section == 'parameters': parameters  = content
                        elif section == 'examples':   examples    = content

                embed = discord.Embed(
                    title=f"{icon}  g!{command.name}",
                    description=description,
                    colour=discord.Colour(0x5865F2)
                )
                if command.signature:
                    embed.add_field(name="📖  Usage",      value=f"`g!{command.name} {command.signature}`", inline=False)
                if parameters:
                    embed.add_field(name="📋  Parameters", value='\n'.join(parameters),                     inline=False)
                if examples:
                    embed.add_field(name="💡  Examples",   value='\n'.join(examples),                       inline=False)
                if isinstance(command, commands.Group):
                    # Recursively list all nested subcommands
                    all_subs = []
                    for sub in command.commands:
                        if not sub.hidden:
                            all_subs.extend(self._collect_commands(sub, prefix=f"g!{command.name} "))
                    if all_subs:
                        embed.add_field(name="🔀  Subcommands", value="  ".join(all_subs), inline=False)
                embed.set_footer(text=f"Category: {cog_name}  •  Guard Bot")
                embed.timestamp = datetime.utcnow()
                await ctx.send(embed=embed)
            else:
                embed = discord.Embed(
                    description=f"❌  Command `{command_name}` not found. Use `g!help` for all commands.",
                    colour=discord.Colour(0xED4245)
                )
                embed.set_footer(text="Guard Bot")
                await ctx.send(embed=embed)
            return

        # ── All commands overview ──────────────────────────────────────────────
        embed = discord.Embed(
            title="🛡️  Guard Bot — Commands",
            description="Use `g!help <command>` for detailed info on any command.",
            colour=discord.Colour(0x5865F2)
        )
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)

        for cog_name, cog in sorted(self.bot.cogs.items()):
            if cog_name == "Help":
                continue
            cmds = []
            for cmd in cog.get_commands():
                if not cmd.hidden:
                    # _collect_commands recurses into nested groups
                    cmds.extend(self._collect_commands(cmd))
            if cmds:
                icon  = self.category_icons.get(cog_name, "📋")
                desc  = self.category_descriptions.get(cog_name, "")
                label = f"{icon}  {cog_name}" + (f" — {desc}" if desc else "")
                value = "  ".join(cmds)
                # Discord field value limit is 1024 chars; truncate gracefully
                if len(value) > 1020:
                    value = value[:1017] + "..."
                embed.add_field(name=label, value=value, inline=False)

        total_cmds = sum(1 for _ in self.bot.walk_commands())
        embed.set_footer(text=f"Guard Bot  •  {total_cmds} commands across {len(self.bot.cogs) - 1} categories")
        embed.timestamp = datetime.utcnow()
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Help(bot))
