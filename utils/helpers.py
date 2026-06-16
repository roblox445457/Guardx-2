import discord
from datetime import datetime

# ── Brand colours ──────────────────────────────────────────────────────────────
BLURPLE   = 0x5865F2
GREEN     = 0x57F287
RED       = 0xED4245
YELLOW    = 0xFEE75C
FUCHSIA   = 0xEB459E
DARK      = 0x2B2D31

ACTION_COLOURS = {
    "Kick":          FUCHSIA,
    "Ban":           RED,
    "Temporary Ban": RED,
    "Mute":          YELLOW,
    "Unmute":        GREEN,
    "Unban":         GREEN,
}

ACTION_ICONS = {
    "Kick":          "👢",
    "Ban":           "🔨",
    "Temporary Ban": "⏱️",
    "Mute":          "🔇",
    "Unmute":        "🔊",
    "Unban":         "🔓",
}

def e(colour: int) -> discord.Colour:
    return discord.Colour(colour)

def footer(embed: discord.Embed, text: str = "Guard Bot") -> discord.Embed:
    embed.set_footer(text=text, icon_url="https://cdn.discordapp.com/embed/avatars/0.png")
    embed.timestamp = datetime.utcnow()
    return embed

def create_log_embed(action: str, member: discord.Member, moderator: discord.Member, reason: str = None) -> discord.Embed:
    colour = ACTION_COLOURS.get(action, BLURPLE)
    icon   = ACTION_ICONS.get(action, "⚠️")

    embed = discord.Embed(
        title=f"{icon}  {action}",
        colour=colour,
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="👤  User",       value=f"{member.mention}\n`{member.id}`",      inline=True)
    embed.add_field(name="🛡️  Moderator",  value=f"{moderator.mention}\n`{moderator.id}`", inline=True)
    embed.add_field(name="\u200b",         value="\u200b",                                 inline=True)
    if reason:
        embed.add_field(name="📋  Reason", value=reason, inline=False)
    embed.set_footer(text=f"Guard Bot  •  User ID: {member.id}")
    embed.timestamp = datetime.utcnow()
    return embed

def error_embed(description: str) -> discord.Embed:
    embed = discord.Embed(description=f"❌  {description}", colour=e(RED))
    return footer(embed)

def success_embed(description: str) -> discord.Embed:
    embed = discord.Embed(description=f"✅  {description}", colour=e(GREEN))
    return footer(embed)

def warning_embed(title: str, description: str) -> discord.Embed:
    embed = discord.Embed(title=f"⚠️  {title}", description=description, colour=e(YELLOW))
    return footer(embed)

def info_embed(title: str, description: str = "") -> discord.Embed:
    embed = discord.Embed(title=title, description=description, colour=e(BLURPLE))
    return footer(embed)

def check_permissions(ctx, member, action):
    """Checks if the bot has required permissions for an action"""
    permissions = ctx.channel.permissions_for(ctx.guild.me)
    if action == "kick"  and not permissions.kick_members:  return False
    if action == "ban"   and not permissions.ban_members:   return False
    if action == "mute"  and not permissions.manage_roles:  return False
    return True
