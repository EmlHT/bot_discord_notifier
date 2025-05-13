import paramiko
import asyncio
import discord
import os
import json
import socket
from datetime import datetime, timedelta
from discord.ext import commands

# ---- CONFIG ----
SFTP_HOST = os.getenv("SFTP_HOST")
SFTP_PORT = int(os.getenv("SFTP_PORT"))
SFTP_USER = os.getenv("SFTP_USER")
SFTP_PASS = os.getenv("SFTP_PASS")

LOG_PATH = os.getenv("LOG_PATH")
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

TARGET_CHANNEL_NAME = "colporteur"

STATS_FILE = "daily_stats.json"

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

# ---- Stats du jour ----
def log_connection(name):
    if not name or not name.isalnum():
        return

    today = datetime.now().strftime("%Y-%m-%d")
    try:
        with open(STATS_FILE, "r") as f:
            stats = json.load(f)
    except FileNotFoundError:
        stats = {}

    # Supprimer les dates plus vieilles que 30 jours
    cutoff_date = datetime.now() - timedelta(days=30)
    stats = {
        date: players
        for date, players in stats.items()
        if datetime.strptime(date, "%Y-%m-%d") >= cutoff_date
    }

    # Ajouter la connexion du jour
    stats.setdefault(today, [])
    stats[today].append(name)

    # Sauvegarder avec indentation pour lisibilité
    with open(STATS_FILE, "w") as f:
        json.dump(stats, f, indent=2)

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
        player_list = "\n".join(f"- {name}" for name in sorted(players))
        await ctx.send(f"🎮 ({len(players)} en ligne)\nVillageois connectés :\n{player_list}")
    else:
        await ctx.send(f"😴  Les villageois se reposent ({len(players)} en ligne)")

# ---- Commande !ping ----
@bot.command()
async def ping(ctx):
    try:
        ip = socket.gethostbyname(SFTP_HOST)
        with socket.create_connection((ip, SFTP_PORT), timeout=5) as sock:
            sock.settimeout(3)
            banner = sock.recv(1024).decode(errors="ignore").strip()
            if banner.startswith("SSH-"):
                await ctx.send(f"✅ Serveur en ligne : `{banner}`")
            else:
                await ctx.send(f"⚠️ Port ouvert mais pas de réponse SSH. Bizarre... ➜ `{banner}`")
    except socket.timeout:
        await ctx.send("❌ Délai dépassé : le serveur ne répond pas.")
    except socket.gaierror:
        await ctx.send("❌ Impossible de résoudre le nom d'hôte (DNS invalide ?)")
    except ConnectionRefusedError:
        await ctx.send("❌ Connexion refusée : serveur probablement éteint.")
    except Exception as e:
        await ctx.send(f"❌ Serveur injoignable. Erreur : {e}")

# ---- Commande !stats ----
@bot.command()
async def stats(ctx):
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        with open(STATS_FILE, "r") as f:
            stats = json.load(f)

    except FileNotFoundError:
        stats = {}

    today_stats = stats.get(today, [])
    if today_stats:
        count = len(today_stats)
        top = max(set(today_stats), key=today_stats.count)
        await ctx.send(f"📊 **Statistiques du {today}**\n- Connexions : {count}\n- Villageois le plus actif : {top}")
    else:
        await ctx.send(f"📊 Aucune donnée pour aujourd'hui ({today}).")

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
                    log_connection(name)
                    await channel.send(f"✅ **{name}** est de retour parmi nous ! ({len(players_online)} en ligne)")
            elif "[Event]" in line and "est parti." in line:
                name = line.split("Le Joueur")[1].split("est parti.")[0].strip()
                if name in players_online:
                    players_online.remove(name)
                    await channel.send(f"❌ **{name}** s'en est allé. ({len(players_online)} en ligne)")

        await asyncio.sleep(30)

bot.run(DISCORD_BOT_TOKEN)