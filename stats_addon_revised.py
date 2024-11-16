import datetime
import sqlite3
import numpy as np
import time
import math
import matplotlib.pyplot as plt
from io import BytesIO
from PIL import Image, ImageFont, ImageDraw
# hai
DAY = 86400
NOW = time.time()
TODAY = NOW-(NOW%86400)
UNIX = datetime.date(1970, 1, 1)

# TODO: MAKE THE CODE NICE IN GENERATE_STATS
# Example: Combine all the for loops, make a function instead of doing the same thing twice

def get_messages_days(c: sqlite3.Cursor, id: int, days: int) -> int:
    NOW = time.time()
    TODAY = NOW-(NOW%86400)
    c.execute("SELECT COUNT(*) FROM messages WHERE author_id = ? AND timestamp > ?", (id, NOW-DAY*days,))
    return c.fetchone()[0]

# This WILL break if someone is actively in vc, please fix
def get_voice_seconds_days(c: sqlite3.Cursor, id: int, days: int) -> float:
    NOW = time.time()
    TODAY = NOW-(NOW%86400)
    c.execute("SELECT voice_start, voice_end FROM voice WHERE author_id = ? AND voice_start > ?", (id, NOW-DAY*days,))
    total = 0
    for r in c.fetchall():
        if r[1] != None and r[0] != None: 
            total += float(r[1]) - float(r[0])
    return round(total, 2)

def generate_stats(user):
    msgdb = sqlite3.connect('RITMessages.db')
    c = msgdb.cursor()
    print("Generating stats report for " + user.display_name)

    # Get all user messages, and counts from each user
    ids = []
    messagecounts = {}
    usermessages = []
    c.execute("SELECT * FROM messages")
    r = c.fetchall()
    for message in r:
        ids.append(message[2])
        if message[2] == str(user.id):
            usermessages.append(message)
        try:
            messagecounts[message[2]] += 1
        except:
            messagecounts[message[2]] = 1
    # Make sure the user id list doesn't have duplicates
    ids = list(set(ids))
    
    # Get the user's place by comparing to every other user
    total = get_messages_days(c, user.id, 2000)
    place = 1
    for u in messagecounts.keys():
        if messagecounts[u] > total:
            place += 1

    # Messages per day for the plot
    days = {}
    dates = []
    for message in usermessages:
        d = math.floor(float(message[-1])/86400)
        try:
            days[d] += 1
        except:
            days[d] = 1
    for day in days.keys():
        dates.append(datetime.timedelta(day) + UNIX)

    # Fun graph shenanigans that didn't take an hour
    fig = plt.figure(figsize=(9.2,2.5))
    ax = fig.add_axes([0, 0.2, 1.0, 0.8])
    ax.spines['left'].set_alpha(0)
    ax.spines['bottom'].set_alpha(0)
    ax.spines['top'].set_alpha(0)
    ax.tick_params(axis='x', colors='white')
    
    max_messages = 1 if max(days.values()) == 0 else max(days.values())
    days_list = [x/max_messages for x in days.values()]
    ax.plot(dates, days_list, color='#d796f8', linewidth=5)

    # Find the most used channel
    channels = {}
    for message in usermessages:
        try:
            channels[message[-2]] += 1
        except:
            channels[message[-2]] = 1
    top_channel_id = max(channels, key=channels.get)

    seven = int(get_messages_days(c, user.id, 7))
    three = int(get_messages_days(c, user.id, 3))
    one = int(get_messages_days(c, user.id, 1))
    rank = int(place)
    channel_id = int(top_channel_id)
    channel_count = int(channels[top_channel_id])
    message_top = TopObject(total, seven, three, one, rank, channel_id, channel_count)

    c.execute("SELECT * FROM voice")
    voice_counts = {}
    ids = []
    voice_entries = []
    for v in c.fetchall():
        if v[2] != None and v[3] != None:
            ids.append(int(v[0]))
            if int(v[0]) == user.id:
                voice_entries.append(v)
            try:
                voice_counts[v[0]] += float(v[3]) - float(v[2])
            except:
                voice_counts[v[0]] = float(v[3]) - float(v[2])
    ids = list(set(ids))

    total = get_voice_seconds_days(c, user.id, 2000)

    place = 1
    for u in voice_counts.keys():
        if voice_counts[u] > total:
            place += 1

    channels = {0: 0}
    for v in voice_entries:
        try:
            channels[v[1]] += float(v[3]) - float(v[2])
        except:
            channels[v[1]] = float(v[3]) - float(v[2])
    try:
        top_channel_id = max(channels, key=channels.get)
    except:
        top_channel_id = 0

    days = {}
    for x in dates:
        x = datetime.datetime(x.year, x.month, x.day)
        x = int((x-datetime.datetime(1970, 1, 1)).total_seconds())/86400
        days[x] = float(0.0)
    for v in voice_entries:
        d = math.floor(float(v[2])/86400)
        try:
            days[d] += float(v[3]) - float(v[2])
        except Exception as e:
            print("This error shouldn't trigger")

    max_voice = 1 if max(days.values()) == 0 else max(days.values())
    days_list = [x/max_voice for x in days.values()]
    ax.plot(dates, days_list, color='#2f227a', linewidth=5)

    seven = get_voice_seconds_days(c, user.id, 7)
    three = get_voice_seconds_days(c, user.id, 3)
    one = get_voice_seconds_days(c, user.id, 1)
    rank = int(place)
    channel_id = int(top_channel_id)
    channel_count = int(channels[top_channel_id])
    voice_top = TopObject(total, seven, three, one, rank, channel_id, channel_count)

    msgdb.close()
    
    buffer = BytesIO()
    fig.savefig(buffer, format='png', facecolor='none', transparent=True)
    buffer.seek(0)
    plot_img = Image.open(buffer)
    plot_img.save("temp_graph.png")
    plt.close('all')
    return [message_top, voice_top]

def generate_image(user, message_top, voice_top, avatar, client) -> None:
    img = Image.open("template.png")

    av = Image.open(BytesIO(avatar)).resize((100, 100), Image.Resampling.LANCZOS)
    img.paste(av, (50, 20))

    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype("verdana.ttf", 28)
    font_large = ImageFont.truetype("verdana.ttf", 48)

    draw.text((190,40), "Stats for " + user.display_name, (255,255,255), font=font_large)

    draw.text((970,258), str(message_top.one) + " messages", (255,255,255), font=font)
    draw.text((970,340), str(message_top.seven) + " messages", (255,255,255), font=font)
    draw.text((970,427), str(message_top.total) + " messages", (255,255,255), font=font)

    draw.text((1600,258), str(round(float(voice_top.one)/3600, 2)) + " hours", (255,255,255), font=font)
    draw.text((1600,340), str(round(float(voice_top.seven)/3600, 2)) + " hours", (255,255,255), font=font)
    draw.text((1600,427), str(round(float(voice_top.total)/3600, 2)) + " hours", (255,255,255), font=font)

    graph = Image.open("temp_graph.png")
    img.paste(graph, (975, 630), mask=graph.split()[3])

    #TODO: Possibly a boolean so you can run this without client object
    name = client.get_channel(message_top.channel_id).name
    temp_font = ImageFont.truetype("verdana.ttf", 48)
    while temp_font.getbbox(name)[2] > 300:
        temp_font = temp_font.font_variant(size=temp_font.size-1)
    draw.text((80,650), name, (255,255,255), font=temp_font)
    draw.text((450,650), str(message_top.channel_count) + " messages", (255,255,255), font=font_large)
    draw.text((380,266), "#" + str(message_top.rank), (255,255,255), font=font_large)

    if voice_top.channel_id != 0:
        name = client.get_channel(voice_top.channel_id).name
    else:
        name = "None"
    temp_font = ImageFont.truetype("verdana.ttf", 48)
    while temp_font.getbbox(name)[2] > 300:
        temp_font = temp_font.font_variant(size=temp_font.size-1)
    draw.text((80,785), name, (255,255,255), font=temp_font)
    draw.text((450,785), str(round(float(voice_top.channel_count)/3600, 2)) + " hours", (255,255,255), font=font_large)
    draw.text((380,395), "#" + str(voice_top.rank), (255,255,255), font=font_large)
    
    img.save("temp_account.png")

class User:
    def __init__(self, id, display_name):
        self.id = id
        self.display_name = display_name

class TopObject:
    def __init__(self, total, seven, three, one, rank, channel_id, channel_count):
        self.total = total
        self.seven = seven
        self.three = three
        self.one = one
        self.rank = rank
        self.channel_id = channel_id
        self.channel_count = channel_count

user = User(803766890023354438, "Yukiko")
def generate_profile(user, client, avatar):
    stats = generate_stats(user=user)
    generate_image(user, stats[0], stats[1], avatar, client)
