import paramiko
import asyncio
import discord
import os
from discord.ext import commands

# ---- CONFIG ----
SFTP_HOST = os.getenv("SFTP_HOST")
SFTP_PORT = int(os.getenv("SFTP_PORT", "22"))
SFTP_USER = os.getenv("SFTP_USER")
SFTP_PASS = os.getenv("SFTP_PASS")

LOG_PATH = os.getenv("LOG_PATH")
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

TARGET_CHANNEL_NAME = "colporteur"

# ---- DISCORD ----
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

players_online = set()

# ---- SFTP ----
def get_last_lines():
    try:
        client = paramiko.Transport((SFTP_HOST, SFTP_PORT))
        client.connect(username=SFTP_USER, password=SFTP_PASS)
        sftp = paramiko.SFTPClient.from_transport(client)

        with sftp.file(LOG_PATH, "r") as f:
            lines = f.readlines()
            return lines[-30:]
    except Exception as e:
        print(f"[ERREUR SFTP] {e}")
        return []

# ---- Commande !pop ----
@bot.command()
async def pop(ctx):
    lines = get_last_lines()
    players = set()
    for line in lines:
        if "[Event]" in line and "joins." in line:
            name = line.split("[Event]")[1].split("joins.")[0].strip().split()[0]
            players.add(name)
    if players:
        await ctx.send(f"🎮 Joueurs connectés : {', '.join(players)}")
    else:
        await ctx.send("😴 Aucun joueur connecté actuellement.")

# Lancement du bot
@bot.event
async def on_ready():
    print(f"✅ Connecté en tant que {bot.user}")
    await monitor_log()

# Surveillance du fichier
async def monitor_log():
    await bot.wait_until_ready()
    channel = discord.utils.get(bot.get_all_channels(),
                                name=TARGET_CHANNEL_NAME)
    if channel is None:
        print(f"[ERREUR] Channel #{TARGET_CHANNEL_NAME} introuvable.")
        return

    while True:
        lines = get_last_lines()
        for line in lines:
            if "[Event]" in line and "joins." in line:
                name = line.split("[Event]")[1].split("joins.")[0].strip().split()[0]
                if name not in players_online:
                    players_online.add(name)
                    await channel.send(f"✅ **{name}** s'est connecté au serveur !")
            elif "[Event]" in line and "est parti." in line:
                name = line.split("Le Joueur")[1].split("est parti.")[0].strip()
                if name in players_online:
                    players_online.remove(name)
                    await channel.send(f"❌ **{name}** s'est déconnecté.")

        await asyncio.sleep(30)

bot.run(DISCORD_BOT_TOKEN)