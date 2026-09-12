import discord
from discord import app_commands
from discord.ext import commands
import requests
import random
import string
import asyncio
import datetime
import os
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

# Load 4-letter English words
WORD_FILE = os.path.join(os.path.dirname(__file__), "four_letter_words.txt")
try:
    with open(WORD_FILE, "r") as f:
        FOUR_LETTER_WORDS = [line.strip().lower() for line in f if line.strip()]
except FileNotFoundError:
    FOUR_LETTER_WORDS = []

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

@bot.tree.command(name="findwords", description="Find available 4-letter English words on Minecraft")
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

    if not FOUR_LETTER_WORDS:
        await interaction.followup.send("Word list not found!")
        return

    embed_start = discord.Embed(
        title="Searching for available English words...",
        description=f"Checking **{len(FOUR_LETTER_WORDS)}** 4-letter English words against Minecraft...",
        color=0xFFAA00
    )
    await interaction.followup.send(embed=embed_start)

    words_to_check = random.sample(FOUR_LETTER_WORDS, min(100, len(FOUR_LETTER_WORDS)))
    found = []
    checked = 0
    word_index = 0

    while not found and checked < 300:
        if word_index >= len(words_to_check):
            words_to_check = random.sample(FOUR_LETTER_WORDS, min(100, len(FOUR_LETTER_WORDS)))
            word_index = 0

        word = words_to_check[word_index]
        word_index += 1
        checked += 1
        available = check_username(word)

        if available is True:
            found.append(word)
            if len(found) % 5 == 0:
                embed_progress = discord.Embed(
                    title="Searching...",
                    description=f"Found **{len(found)}** available words\nChecked **{checked}** words so far",
                    color=0xFFAA00
                )
                await interaction.edit_original_response(embed=embed_progress)

        if checked % 10 == 0 and not found:
            embed_progress = discord.Embed(
                title="Searching...",
                description=f"Checked **{checked}** words so far, still looking...",
                color=0xFFAA00
            )
            await interaction.edit_original_response(embed=embed_progress)

        await asyncio.sleep(REQUEST_DELAY)

    if found:
        description = "**Available English Words:**\n"
        description += " ".join(f"`{w}`" for w in found) + "\n\n"
        description += f"---\n*Checked {checked} words, found {len(found)} available*"

        embed_result = discord.Embed(
            title=f"Found {len(found)} Available English Words!",
            description=description,
            color=0x00FF00,
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        embed_result.set_footer(text="Words may be taken quickly - claim fast!")

        for word in found[:15]:
            embed_result.add_field(
                name=f"`word`",
                value=f"[NameMC](https://namemc.com/name/{word})",
                inline=True
            )

        await interaction.edit_original_response(embed=embed_result)
    else:
        embed_fail = discord.Embed(
            title="No Available Words Found",
            description=f"Checked **{checked}** words but none were available.\nTry again later!",
            color=0xFF0000
        )
        await interaction.edit_original_response(embed=embed_fail)

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
