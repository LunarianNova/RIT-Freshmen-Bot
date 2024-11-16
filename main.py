# ---- 
# Hard rewrite of the originals
# ----
# I want to make the code look nicer, but that's something I'll do later

from discord.ext import commands, tasks
from discord.commands import Option
from discord.ui.item import Item
from discord.message import Message
from dotenv import load_dotenv
from io import BytesIO
from pytz import timezone
from stats_addon_revised import generate_profile

import datetime
import discord
import matplotlib.pyplot as plt
import os
import sys
import sqlite3
import time

GUILD_ID = 1190760871719338044
LOG_ID = 1191391556033335306
GENERAL_ID = 1190760872310743165
ACTIVE_ID = 1209635586609250324
SCREENAGER_ID = 1230157768296497262
ACTIVE_MEMBER_MESSAGES = 100
SCREENAGER_MESSAGES = 1500
RIT_START = datetime.date(2024, 8, 18)

load_dotenv()
client = commands.Bot(command_prefix="y|", intents=discord.Intents.all())
db = sqlite3.connect("RITMessages.db")
c = db.cursor()
roles = {}

role_backup = {}
with open('role_backup.txt', 'r') as f:
    h = f.read()
    for user in h.split('\n')[0:-2]:
        role_backup[user.split(":")[0]] = user.split("@everyone, ")[1][0:-2]

def before_shutdown():
    print("Shutdown requested")
    db.close()
    pass

def update_voice(author_id, channel_id, start=None, end=None, ignore_times=0):
    if start:
        c.execute("INSERT INTO voice(author_id, channel_id, voice_start, ignore_times) VALUES(?, ?, ?, ?)", (author_id, channel_id, start, ignore_times,))
    if end:
        c.execute("SELECT * FROM voice WHERE author_id = ? AND channel_id = ? AND voice_end IS NULL ORDER BY voice_start DESC", (author_id, channel_id,))
        latest = c.fetchall()[0][2]
        c.execute("UPDATE voice SET voice_end = ? WHERE author_id = ? AND channel_id = ? AND voice_start = ?", (end, author_id, channel_id, latest,))
    db.commit()


def store_message(message):
    try:
        if len(message.content) > 0:
            c.execute('INSERT INTO messages VALUES (?, ?, ?, ?, ?)', (str(message.id), str(message.content), str(message.author.id), str(message.channel.id), str(message.created_at.timestamp()),))
    except sqlite3.IntegrityError:
        print(str(message.id) + " is already in database")
    db.commit()

@client.event
async def on_ready():
    global role, log_channel, roles
    c.execute("CREATE TABLE IF NOT EXISTS voice(author_id TEXT, channel_id TEXT, voice_start TEXT, voice_end TEXT, ignore_times INTEGER)")
    c.execute("CREATE TABLE IF NOT EXISTS messages(message_id TEXT PRIMARY KEY, content TEXT, author_id TEXT, channel_id TEXT, timestamp TEXT);")
    c.execute("CREATE TABLE IF NOT EXISTS members(member_count, time)")
    c.execute("CREATE TABLE IF NOT EXISTS birthdays(author_id TEXT, date TEXT)")
    c.execute("SELECT COUNT(*) FROM messages")
    db.commit()
    log_channel = client.get_channel(LOG_ID)
    # Beta bot is not in server
    if client.get_guild(GUILD_ID):
        for role in client.get_guild(GUILD_ID).roles:
            roles[str(role.name)] = role
        role = client.get_guild(GUILD_ID).get_role(ACTIVE_ID)
        today = datetime.datetime.now(tz=timezone('US/Eastern')).date()
        await client.change_presence(activity=discord.Activity(type=discord.ActivityType.playing, name=str((RIT_START-today).days) + " Days Until RIT"))
    check_birthdays.start()
    print("Logged in as " + client.user.name)
    print(str(c.fetchone()[0]) + " Messages retrieved")

@client.event
async def on_message(message):
    global role, log_channel
    # We HATE bots
    if message.author.bot:
        return
    store_message(message)
    
    c.execute("SELECT COUNT(*) FROM messages WHERE author_id = ?", (str(message.author.id),))
    result = c.fetchone()
    if result and result[0]:
        if result[0] == ACTIVE_MEMBER_MESSAGES:
            await message.author.add_roles(role)
            print("Gave " + message.author.display_name + " Active Member role")
            embed = discord.Embed(title="Role Assigned", color=0xffffff, description="Active Member role was assigned to " + message.author.display_name + " for reaching " + str(ACTIVE_MEMBER_MESSAGES) + " messages")
            await log_channel.send(embed=embed)
        if result[0] == SCREENAGER_MESSAGES:
            await message.author.add_roles(client.get_guild(GUILD_ID).get_role(SCREENAGER_ID))
            print("Gave " + message.author.display_name + " Screenager role")
    await client.process_commands(message)

@client.event
async def on_voice_state_update(member, before, after):
    # Member joined a channel (Did not move channels)
    if not before.channel and after.channel:
        update_voice(member.id, after.channel.id, start=time.time())
    # Member left a join channel (Did not move channels)
    if before.channel and not after.channel:
        update_voice(member.id, before.channel.id, end=time.time())
    # If member moves channels
    if before.channel and after.channel:
        update_voice(member.id, before.channel.id, end=time.time())
        update_voice(member.id, after.channel.id, start=time.time())


new_day = datetime.time(hour=4, minute=0)
print(type(new_day))
@tasks.loop(time=new_day)
async def check_birthdays():
    print("NEW DAY!")
    today = datetime.datetime.now(tz=timezone('US/Eastern')).date()
    days_left = (RIT_START-today).days
    await client.change_presence(activity=discord.Activity(type=discord.ActivityType.playing, name=str(days_left) + " Days Until RIT"))
    if days_left <= 30:
        await client.get_channel(GENERAL_ID).send("**Only " + str(days_left) + " days until move in!!**")
    d = datetime.datetime.today().strftime("%m-%d")
    c.execute("SELECT date FROM birthdays WHERE author_id = 0")
    if d != c.fetchone()[0]:
        c.execute("SELECT author_id FROM birthdays WHERE date = ?", (d,))
        r = c.fetchall()
        if len(r) > 0:
            await client.get_guild(GUILD_ID).get_channel(GENERAL_ID).send("Happy birthday to " + ", ".join(["<@!" + x[0] + ">" for x in r]) + "!!")
        else:
            print("No birthdays today")
        c.execute("UPDATE birthdays SET date = ? WHERE author_id = 0", (d,))
        return
    else:
        print("Passed on birthday message.")
        return

# ====================
# Dangerous Commands
# ====================

@client.slash_command()
@commands.is_owner()
async def backup_roles(ctx):
    users = {}
    f = open('role_backup.txt', 'w')
    f.close()
    with open('role_backup.txt', 'w') as f:
        for user in ctx.guild.members:
            users[str(user.id)] = ''
            for role in user.roles:
                users[str(user.id)] = users[str(user.id)] + str(role.name) + ", "
        for user in users:
            f.write(str(user) + ": " + users[user] + "\n")

@client.slash_command()
@commands.is_owner()
async def shutdown(ctx):
    before_shutdown()
    await ctx.respond("Shutting Down.", ephemeral=True)
    exit()

@client.slash_command()
@commands.is_owner()
async def restart(ctx):
    before_shutdown()
    await ctx.respond("Restarting.", ephemeral=True)
    # Works if you change python3 to be the thing you type in terminal (py, python, python3, python -3.11)
    os.execv(sys.executable, ['python3'] + sys.argv)

#TODO: TEST
@client.slash_command()
@commands.is_owner()
async def force_update(ctx, datestr: str):
    await ctx.respond("Force updating database for " + datestr, ephemeral=True)
    async def update(datestr):
        print("Force updating database for date " + datestr)
        channel_count, failed_count, messages = 0, 0, []
        date = datetime.datetime.strptime(datestr, "%Y-%m-%d")
        start = datetime.datetime(date.year, date.month, date.day, 0, 0, 0)
        end = datetime.datetime(date.year, date.month, date.day, 23, 59, 59)
        for channel in ctx.guild.text_channels:
            channel_count += 1
            try:
                async for message in channel.history(limit=None, after=start, before=end):
                    messages.append(message)
            except discord.errors.Forbidden:
                failed_count += 1
                pass
        print("Found " + str(len(messages)) + " messages sent on " + datestr + ". Searched " + str(channel_count-failed_count) + " channels, and couldn't access " + str(failed_count) + " more channels.")
        for message in messages:
            # WE STILL HATE BOTS
            if not message.author.bot:
                store_message(message)
    if datestr == "all":
        delta = datetime.date.today() - datetime.date(2023, 12, 31)
        for i in range(delta.days + 1):
            date = datetime.date(2023, 12, 31) + datetime.timedelta(days=i)
            await update(date.strftime("%Y-%m-%d"))
    else:
        await update(datestr)

# TODO: TEST
@client.slash_command()
@commands.is_owner()
async def update_active_role(ctx):
    global role, log_channel
    await ctx.respond("Updating Active Member Role", ephemeral=True)
    guild = client.get_guild(GUILD_ID)
    for member in guild.members:
        c.execute("SELECT COUNT(*) FROM messages WHERE author_id = ?", (member.id,))
        message_count = c.fetchone()
        if message_count and message_count[0]:
            if message_count[0] >= ACTIVE_MEMBER_MESSAGES:
                if role in member.roles:
                    pass
                else:
                    await member.add_roles(role)
                    print("Gave " + member.display_name + " Active Member role")
                    embed = discord.Embed(title="Role Assigned", color=0xffffff, description="Active Member role was assigned to " + member.display_name + " for reaching " + str(ACTIVE_MEMBER_MESSAGES) + " messages")
                    await log_channel.send(embed=embed)
            if message_count[0] < ACTIVE_MEMBER_MESSAGES:
                if role in member.roles:
                    await member.remove_roles(role)
                    print("Removed Active Role from " + member.display_name)
    print("Done!")

@client.slash_command()
async def set_birthday(ctx, date: Option(str, "Date in MM-DD Format", required=True)):
    try:
        datetime.datetime.strptime(date, "%m-%d")
    except:
        await ctx.respond("Date must be in a MM-DD format!", ephemeral=True)
        return
    try:
        c.execute("SELECT * FROM birthdays WHERE author_id = ?", (ctx.author.id,))
        r = c.fetchone()
        await ctx.respond("You have already set your birthday to " + str(r[1]) + ". If you think this is a mistake, please contact yuki.ko", ephemeral=True)
    except:
        c.execute("INSERT INTO birthdays(author_id, date) VALUES(?, ?)", (str(ctx.author.id), str(date),))
        db.commit()
        await ctx.respond("Set your birthday to " + str(date), ephemeral=True)

# ============================
# Sometimes I still use this
# ============================

@client.slash_command()
async def deprecated_stats(ctx, date: Option(str, "Date in YYYY-MM-DD Format", required = False, default = "Total"), user: discord.User = None): # type: ignore
    embed = discord.Embed(title="Requested Stats", color=0x00ff00)
    def get_total_time(voices):
        total = 0
        for v in voices:
            total += float(v[3]) - float(v[2])
        return total
    if user:
        if date == "Total":
            c.execute("SELECT COUNT(*) FROM messages WHERE author_id = ?", (str(user.id),))
            m = c.fetchone()[0]
            c.execute("SELECT * FROM voice WHERE author_id = ?", (str(user.id)))
            v = get_total_time(c.fetchall())
        else:
            try:
                t = datetime.datetime.strftime(date, "%Y-%m-%d")
                seconds = int((t-datetime.datetime(1970, 1, 1)).total_seconds())
                c.execute("SELECT COUNT(*) FROM messages WHERE author_id = ? AND timestamp > ? AND timestamp < ?", (str(user.id), seconds, seconds+86400,))
                m = c.fetchone()[0]
                c.execute("SELECT * FROM voice WHERE author_id = ? AND voice_start > ? AND voice_end < ?", (str(user.id), seconds, seconds+86400,))
                v = get_total_time(c.fetchall())
            except:
                await ctx.respond("Date should look like YYYY-MM-DD, 2024-02-26", ephemeral=True)
                return
    else:
        if date == "Total":
            c.execute("SELECT COUNT(*) FROM messages")
            m = c.fetchone()[0]
            c.execute("SELECT * FROM voice")
            v = get_total_time(c.fetchall())
        else:
            try:
                t = datetime.datetime.strftime(date, "%Y-%m-%d")
                seconds = int((t-datetime.datetime(1970, 1, 1)).total_seconds())
                c.execute("SELECT COUNT(*) FROM messages WHERE timestamp > ? AND timestamp < ?", (seconds, seconds+86400,))
                m = c.fetchone()[0]
                c.execute("SELECT * FROM voice WHERE voice_start > ? AND voice_end < ?", (seconds, seconds+86400,))
                v = get_total_time(c.fetchall())
            except:
                await ctx.respond("Date should look like YYYY-MM-DD, 2024-02-26", ephemeral=True)
                return
    if len(v) > 0 and len(m) > 0:
        embed.add_field(name="Date", value=str(date))
        embed.add_field(name="Message Count", value=str(m))
        embed.add_field(name="Voice Duration (seconds)", value=str(v))
    else:
        embed.description = "No stats found."
    await ctx.respond(embed=embed, ephemeral=True)

"""@client.slash_command()
async def double_deprecated_stats(ctx, date: Option(str, "Date in YYYY-MM-DD Format", required = False, default = "Total"), user: discord.User = None): # type: ignore
    embed = discord.Embed(title="Requested Stats", color=0x00ff00)
    if user:
        if date == "Total":
            c.execute("SELECT SUM(message_count), SUM(voice_duration) FROM user_stats WHERE id = ?", (str(user.id),))
        else:
            try:
                date = datetime.date(int(date[0:4]), int(date[5:7]), int(date[8:10]))
                c.execute("SELECT message_count, voice_duration FROM user_stats WHERE id = ? AND date = ?", (str(user.id), str(date),))
            except ValueError as e:
                await ctx.respond("Date should look like YYYY-MM-DD, 2024-02-26", ephemeral=True)
                return
    else:
        if date == "Total":
            c.execute("SELECT SUM(message_count), SUM(voice_duration) FROM server_stats")
        else:
            try:
                date = datetime.date(int(date[0:4]), int(date[5:7]), int(date[8:10]))
                c.execute("SELECT message_count, voice_duration FROM server_stats WHERE date = ?", (str(date),))
            except ValueError as e:
                await ctx.respond("Date should look like YYYY-MM-DD, 2024-02-26", ephemeral=True)
                return
    result = c.fetchone()
    if result:
        embed.add_field(name="Date", value=str(date))
        embed.add_field(name="Message Count", value=result[0])
        embed.add_field(name="Voice Duration (seconds)", value=result[1])
    else:
        embed.description = "No stats found."
    await ctx.respond(embed=embed, ephemeral=True)"""

# ============================
# Stored in an external file  
# ============================  

@client.slash_command()
async def stats(ctx, user: discord.User=None):
    if not user:
        user = ctx.author
    await ctx.defer(ephemeral=True)
    av = await user.display_avatar.read()
    generate_profile(user, client, av)
    with open('temp_account.png', 'rb') as file:
        im = discord.File(file)
        await ctx.respond(file=im, ephemeral=True)


# ========================
# I need to learn Modals
# ========================

class MyModal(discord.ui.Modal): #mymodal my beloved - mae
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.add_item(discord.ui.InputText(label="Title"))

    async def callback(self, interaction: discord.Interaction):
        embed = discord.Embed(title="Poll Submission")
        embed.add_field(name="Movie", value=self.children[0].value)
        embed.add_field(name="Recommender", value=interaction.user.display_name)
        embed.set_footer(text=interaction.message.id)
        channel = client.get_guild(GUILD_ID).get_channel(LOG_ID)
        await interaction.response.defer()
        await channel.send(embed=embed)

class PollView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Add Entry", style=discord.ButtonStyle.primary, emoji="➕")
    async def button_callback(self, button, interaction):
        await interaction.response.send_modal(MyModal(title="Suggest a Movie"))

# TODO: Allow any staff/event coordinator to cast this spell
@client.slash_command()
@commands.is_owner()
async def movie_night(ctx: discord.ApplicationContext, time):
    embed=discord.Embed(title="Movie Night Suggestions 📷", description="We're hosting a movie night in the foreseeable future.\nUse the button below to submit a request", color=0x714b91)
    embed.add_field(name="Rules", value="1. Steer clear of rated R films please. Family-friendly only\n2. Anime films and live action films are both fine\n3. There is no guarantee we will watch the movie you suggest", inline=False)
    await ctx.respond(f"Ends <t:{str(time)}:R>", embed=embed, view=PollView())


# ==========================================
# Member updates, I need to change to unix
# ==========================================
@client.event
async def on_member_join(member):
    global role_backup, roles
    # Beta bot is not in this server
    if member.guild.id == GUILD_ID:
        if str(member.id) in role_backup.keys:
            role_list = []
            for role in role_backup[str(member.id)].split(", "):
                role_list.append(roles[role])
            member.add_roles(role_list)
        c.execute("INSERT INTO members (member_count, time) VALUES (?, ?)", (member.guild.member_count, time.time(),))
        db.commit()

@client.event
async def on_member_leave(member):
    if member.guild.id == GUILD_ID:
        member_count = member.guild.member_count
        c.execute("INSERT INTO members (member_count, time) VALUES (?, ?)", (member_count, time.time(),))
        db.commit()

if __name__ == '__main__':
    client.run(os.getenv('TOKEN'))