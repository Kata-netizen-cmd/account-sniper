import discord
from discord import app_commands
from discord.ext import commands, tasks
import requests
import random
import string
import asyncio
import datetime
import os
import json
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler

# ============================================================
# CONFIGURATION
# ============================================================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

# Character set: a-z + 0-9
CHARS = string.ascii_lowercase + string.digits

# How many available names to find per command
NAMES_TO_FIND = 30

# Delay between Mojang API requests (avoid rate limits)
REQUEST_DELAY = 0.6

# Watchlist file
WATCHLIST_FILE = os.path.join(os.path.dirname(__file__), "watchlist.json")

def load_watchlist():
    try:
        with open(WATCHLIST_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"names": [], "channel_id": None}

def save_watchlist(data):
    with open(WATCHLIST_FILE, "w") as f:
        json.dump(data, f, indent=2)

# ============================================================

# Simple HTTP server to keep the bot alive on hosting platforms
class KeepAlive(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running!")
    def log_message(self, format, *args):
        pass

def run_server():
    server = HTTPServer(("0.0.0.0", 8080), KeepAlive)
    server.serve_forever()

# ============================================================

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# Track cooldowns per user (last command timestamp)
cooldowns = {}

def check_username(username):
    url = f"https://api.mojang.com/users/profiles/minecraft/{username}"
    try:
        resp = requests.get(url, timeout=8)
        if resp.status_code in (204, 404):
            return True
        elif resp.status_code == 200:
            return False
        else:
            return None
    except requests.RequestException:
        return None

@bot.event
async def on_ready():
    await bot.tree.sync()
    if not monitor_names.is_running():
        monitor_names.start()
    print(f"[OK] Logged in as {bot.user} (ID: {bot.user.id})")
    print(f"[OK] Serving {len(bot.guilds)} server(s)")

@bot.tree.command(name="findaccounts", description="Find 30 available 3/4 letter Minecraft usernames")
async def findaccounts(interaction: discord.Interaction):
    user_id = interaction.user.id
    now = datetime.datetime.now().timestamp()
    if user_id in cooldowns and now - cooldowns[user_id] < 30:
        remaining = int(30 - (now - cooldowns[user_id]))
        await interaction.response.send_message(
            f"Wait {remaining}s before using this again.", ephemeral=True
        )
        return
    cooldowns[user_id] = now

    await interaction.response.defer(thinking=True)

    found = []
    checked = 0
    attempts = 0
    max_attempts = NAMES_TO_FIND * 30

    embed_start = discord.Embed(
        title="Searching for available names...",
        description=f"Checking 3 and 4 letter names (a-z, 0-9)...\nTarget: **{NAMES_TO_FIND}** available names",
        color=0xFFAA00
    )
    await interaction.followup.send(embed=embed_start)

    while len(found) < NAMES_TO_FIND and attempts < max_attempts:
        attempts += 1
        length = random.choice([3, 4])
        name = ''.join(random.choices(CHARS, k=length))

        available = check_username(name)
        checked += 1

        if available is True:
            found.append((name, length))
            if len(found) % 5 == 0:
                embed_progress = discord.Embed(
                    title="Searching...",
                    description=f"Found **{len(found)}/{NAMES_TO_FIND}** available names\nChecked **{checked}** names so far",
                    color=0xFFAA00
                )
                await interaction.edit_original_response(embed=embed_progress)

        await asyncio.sleep(REQUEST_DELAY)

    if found:
        three_letter = [n for n, l in found if l == 3]
        four_letter = [n for n, l in found if l == 4]

        description = ""
        if three_letter:
            description += f"**3-Letter ({len(three_letter)}):**\n"
            description += " ".join(f"`{n}`" for n in three_letter) + "\n\n"
        if four_letter:
            description += f"**4-Letter ({len(four_letter)}):**\n"
            description += " ".join(f"`{n}`" for n in four_letter) + "\n\n"

        description += f"---\n*Checked {checked} names to find {len(found)} available*"

        embed_result = discord.Embed(
            title=f"Found {len(found)} Available Names!",
            description=description,
            color=0x00FF00,
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        embed_result.set_footer(text="Names may be taken quickly - claim fast!")

        if len(found) <= 15:
            for name, length in found:
                embed_result.add_field(
                    name=f"`{name}`",
                    value=f"[NameMC](https://namemc.com/name/{name})",
                    inline=True
                )

        await interaction.edit_original_response(embed=embed_result)
    else:
        embed_fail = discord.Embed(
            title="No Available Names Found",
            description=f"Checked **{checked}** names but couldn't find any available ones.\nTry again later!",
            color=0xFF0000
        )
        await interaction.edit_original_response(embed=embed_fail)

@bot.tree.command(name="findwords", description="Find 30 available 3/4 letter names (letters only, no numbers)")
async def findwords(interaction: discord.Interaction):
    user_id = interaction.user.id
    now = datetime.datetime.now().timestamp()
    if user_id in cooldowns and now - cooldowns[user_id] < 30:
        remaining = int(30 - (now - cooldowns[user_id]))
        await interaction.response.send_message(
            f"Wait {remaining}s before using this again.", ephemeral=True
        )
        return
    cooldowns[user_id] = now

    await interaction.response.defer(thinking=True)

    LETTERS = string.ascii_lowercase
    TARGET = 30

    embed_start = discord.Embed(
        title="Searching for available names...",
        description=f"Generating random 3/4 letter names (letters only)...\nTarget: **{TARGET}** available names",
        color=0xFFAA00
    )
    await interaction.followup.send(embed=embed_start)

    found = []
    checked = 0

    while len(found) < TARGET:
        length = random.choice([3, 4])
        name = ''.join(random.choices(LETTERS, k=length))

        if name in [f[0] for f in found]:
            continue

        checked += 1
        available = check_username(name)

        if available is True:
            found.append((name, length))
            embed_progress = discord.Embed(
                title="Searching...",
                description=f"Found **{len(found)}/{TARGET}** available names\nChecked **{checked}** so far",
                color=0xFFAA00
            )
            await interaction.edit_original_response(embed=embed_progress)

        if checked % 50 == 0:
            embed_progress = discord.Embed(
                title="Searching...",
                description=f"Found **{len(found)}/{TARGET}** available names\nChecked **{checked}** so far, still looking...",
                color=0xFFAA00
            )
            await interaction.edit_original_response(embed=embed_progress)

        await asyncio.sleep(REQUEST_DELAY)

    three_letter = [w for w, l in found if l == 3]
    four_letter = [w for w, l in found if l == 4]

    description = ""
    if three_letter:
        description += f"**3-Letter ({len(three_letter)}):**\n"
        description += " ".join(f"`{w}`" for w in three_letter) + "\n\n"
    if four_letter:
        description += f"**4-Letter ({len(four_letter)}):**\n"
        description += " ".join(f"`{w}`" for w in four_letter) + "\n\n"

    description += f"---\n*Checked {checked} names to find {len(found)} available*"

    embed_result = discord.Embed(
        title=f"Found {len(found)} Available Names!",
        description=description,
        color=0x00FF00,
        timestamp=datetime.datetime.now(datetime.timezone.utc)
    )
    embed_result.set_footer(text="Letters only - claim fast!")

    for word, length in found[:15]:
        embed_result.add_field(
            name=f"`{word}` ({length} letters)",
            value=f"[NameMC](https://namemc.com/name/{word})",
            inline=True
        )

    await interaction.edit_original_response(embed=embed_result)

# ============================================================
# MONITOR SYSTEM - Watch specific names for availability
# ============================================================

@bot.tree.command(name="setchannel", description="Set the channel for name availability alerts")
@app_commands.describe(channel="The channel to send alerts to")
async def setchannel(interaction: discord.Interaction, channel: discord.TextChannel):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You need Administrator permission to use this.", ephemeral=True)
        return

    data = load_watchlist()
    data["channel_id"] = channel.id
    save_watchlist(data)

    embed = discord.Embed(
        title="Alert Channel Set",
        description=f"Alerts will be sent to {channel.mention}",
        color=0x00FF00
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="addname", description="Add a name to the watchlist")
@app_commands.describe(name="The Minecraft username to watch")
async def addname(interaction: discord.Interaction, name: str):
    data = load_watchlist()
    name = name.lower().strip()

    if name in data["names"]:
        await interaction.response.send_message(f"`{name}` is already on the watchlist.", ephemeral=True)
        return

    # Check if name is taken (we watch taken names that might become available)
    status = check_username(name)
    if status is True:
        await interaction.response.send_message(f"`{name}` is already available! Claim it now!", ephemeral=True)
        return

    data["names"].append(name)
    save_watchlist(data)

    embed = discord.Embed(
        title="Name Added to Watchlist",
        description=f"Now watching: `{name}`\nYou'll get an alert when it becomes available.",
        color=0x00FF00
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="removename", description="Remove a name from the watchlist")
@app_commands.describe(name="The username to stop watching")
async def removename(interaction: discord.Interaction, name: str):
    data = load_watchlist()
    name = name.lower().strip()

    if name not in data["names"]:
        await interaction.response.send_message(f"`{name}` isn't on the watchlist.", ephemeral=True)
        return

    data["names"].remove(name)
    save_watchlist(data)

    embed = discord.Embed(
        title="Name Removed",
        description=f"Stopped watching: `{name}`",
        color=0xFFAA00
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="watchlist", description="View all names being watched")
async def watchlist(interaction: discord.Interaction):
    data = load_watchlist()

    if not data["names"]:
        await interaction.response.send_message("Watchlist is empty. Use `/addname` to add names.", ephemeral=True)
        return

    description = "**Currently Watching:**\n"
    for name in data["names"]:
        description += f"• `{name}`\n"
    description += f"\n*{len(data['names'])} name(s) total*"

    if data["channel_id"]:
        channel = bot.get_channel(data["channel_id"])
        description += f"\n**Alert Channel:** {channel.mention if channel else 'Not found'}"
    else:
        description += "\n**Alert Channel:** Not set (use `/setchannel`)"

    embed = discord.Embed(
        title="Watchlist",
        description=description,
        color=0x00FF00
    )
    await interaction.response.send_message(embed=embed)

# Background task: check watched names every 5 minutes
@tasks.loop(minutes=5)
async def monitor_names():
    data = load_watchlist()

    if not data["names"] or not data["channel_id"]:
        return

    channel = bot.get_channel(data["channel_id"])
    if not channel:
        return

    for name in data["names"][:]:
        await asyncio.sleep(REQUEST_DELAY)
        available = check_username(name)

        if available is True:
            embed = discord.Embed(
                title="AVAILABLE NAME FOUND!",
                description=f"`{name}` is now available!",
                color=0x00FF00,
                timestamp=datetime.datetime.now(datetime.timezone.utc)
            )
            embed.add_field(
                name="Claim it now!",
                value=f"[NameMC](https://namemc.com/name/{name})"
            )
            await channel.send(embed=embed)

            # Remove from watchlist after alert
            data["names"].remove(name)
            save_watchlist(data)

@monitor_names.before_loop
async def before_monitor():
    await bot.wait_until_ready()

# ============================================================
# Run the bot
# ============================================================
if __name__ == "__main__":
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("ERROR: Set your BOT_TOKEN!")
    else:
        Thread(target=run_server, daemon=True).start()
        print("Keep-alive server started on port 8080")
        bot.run(BOT_TOKEN)
