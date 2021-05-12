from __future__ import unicode_literals
import os
import asyncio
import subprocess
import youtube_dl
from Python_ARQ import ARQ
from pytgcalls import GroupCall
from sys import version as pyver
from pyrogram import Client, filters
from misc import HELP_TEXT, START_TEXT, REPO_TEXT
from functions import (
    transcode,
    download_and_transcode_song,
    convert_seconds,
    time_to_seconds,
    generate_cover,
    generate_cover_square,
)

# TODO Make it look less messed up
is_config = os.path.exists("config.py")

from config import (
    API_ID,
    API_HASH,
    SUDO_CHAT_ID,
    SUDOERS,
    SESSION_STRING,
    ARQ_API,
)

queue = []  # This is where the whole song queue is stored
playing = False  # Tells if something is playing or not

# Pyrogram Client

app = Client(SESSION_STRING, api_id=API_ID, api_hash=API_HASH)

# Pytgcalls Client
vc = GroupCall(
    client=app,
    input_filename="input.raw",
    play_on_repeat=True,
    enable_logs_to_console=False,
)

# Arq Client
arq = ARQ(ARQ_API)


async def delete(message):
    await asyncio.sleep(10)
    await message.delete()


@app.on_message(filters.command("start") & filters.chat(SUDO_CHAT_ID))
async def start(_, message):
    await send(START_TEXT)


@app.on_message(filters.command("help") & filters.chat(SUDO_CHAT_ID))
async def help(_, message):
    await send(HELP_TEXT)


@app.on_message(filters.command("repo") & filters.chat(SUDO_CHAT_ID))
async def repo(_, message):
    await send(REPO_TEXT)


@app.on_message(filters.command("joinvc") & filters.user(SUDOERS))
async def joinvc(_, message):
    try:
        if vc.is_connected:
            await send("Bot allaqachon ovozli chatga qo'shilgan.")
            return
        chat_id = message.chat.id
        await vc.start(chat_id)
        await send("Ovozli chatga qo'shildi.")
    except Exception as e:
        print(str(e))
        await send(str(e))


@app.on_message(filters.command("rejoinvc") & filters.user(SUDOERS))
async def joinvc(_, message):
    try:
        if vc.is_connected:
            await send("Bot allaqachon ovozli chatga qo'shilgan.")
            return
        chat_id = message.chat.id
        await vc.reconnect()
        await send("Ovozli chatga qo'shildi.")
    except Exception as e:
        print(str(e))
        await send(str(e))


@app.on_message(filters.command("leavevc") & filters.user(SUDOERS))
async def leavevc(_, message):
    if not vc.is_connected:
        await send("Bot ovozli chatga qo'shilmagan.")
        return
    await vc.leave_current_group_call()
    await vc.stop()
    await send("Ovzoli chatdan chiqdi.")
    os.execvp(
        f"python{str(pyver.split(' ')[0])[:3]}",
        [f"python{str(pyver.split(' ')[0])[:3]}", "main.py"],
    )


@app.on_message(filters.command("update") & filters.user(SUDOERS))
async def update_restart(_, message):
    await send(
        f'```{subprocess.check_output(["git", "pull"]).decode("UTF-8")}```'
    )
    os.execvp(
        f"python{str(pyver.split(' ')[0])[:3]}",
        [f"python{str(pyver.split(' ')[0])[:3]}", "main.py"],
    )


@app.on_message(filters.command("pause") & filters.chat(SUDO_CHAT_ID))
async def pause_song(_, message):
    vc.pause_playout()
    await send("Ijro to'htatildi, davom etish uchun /resume yuboring.")


@app.on_message(filters.command("resume") & filters.chat(SUDO_CHAT_ID))
async def resume_song(_, message):
    vc.resume_playout()
    await send("Ijro davom ettirildi, to'htatish uchun /pause yuboring.")


@app.on_message(filters.command("volume") & filters.chat(SUDO_CHAT_ID))
async def volume_bot(_, message):
    usage = "Ovoz balandligini quyidagicha sozlang:\n\n/volume [1-200]"
    if len(message.command) != 2:
        await send(usage)
        return
    volume = int(message.text.split(None, 1)[1])
    if (volume < 1) or (volume > 200):
        await send(usage)
        return
    try:
        await vc.set_my_volume(volume=volume)
    except ValueError:
        await send(usage)
        return
    await send(f"Ovoz balandligi **{volume}**ga o'zgartirildi.")


@app.on_message(filters.command("play") & filters.chat(SUDO_CHAT_ID))
async def queuer(_, message):
    usage = "Musiqani ijro etish quyidagicha:\n\n/play youtube/saavn/deezer Musiqa_nomi"
    if len(message.command) < 3:
        await send(usage)
        return
    text = message.text.split(None, 2)[1:]
    service = text[0].lower()
    song_name = text[1]
    requested_by = message.from_user.first_name
    services = ["youtube", "deezer", "saavn"]
    if service not in services:
        await send(usage)
        return
    if len(queue) > 0:
        await message.delete()
        await send("Playlistga qo'shildi.")
        queue.append(
            {
                "service": service,
                "song": song_name,
                "requested_by": requested_by,
            }
        )
        await play()
        return
    await message.delete()
    queue.append(
        {
            "service": service,
            "song": song_name,
            "requested_by": requested_by,
        }
    )
    await play()


@app.on_message(
    filters.command("skip") & filters.user(SUDOERS) & ~filters.edited
)
async def skip(_, message):
    global playing
    if len(queue) == 0:
        await send("Playlistda keyingi musiqa topilmadi.")
        return
    playing = False
    await send("O'tkazib yuborildi.")
    await play()


@app.on_message(filters.command("queue") & filters.chat(SUDO_CHAT_ID))
async def queue_list(_, message):
    if len(queue) != 0:
        i = 1
        text = ""
        for song in queue:
            text += f"{i}. Platforma: {song['service']} " \
                     + f"| Musiqa nomi: **{song['song']}\n"
            i += 1
        m = await send(text)
        await delete(message)
        await m.delete()

    else:
        m = await send("Playlistda keyingi musiqa topilmadi.")
        await delete(message)
        await m.delete()


# Queue handler


async def play():
    global queue, playing
    while not playing:
        await asyncio.sleep(2)
        if len(queue) != 0:
            service = queue[0]["service"]
            song = queue[0]["song"]
            requested_by = queue[0]["requested_by"]
            if service == "youtube":
                playing = True
                del queue[0]
                try:
                    await ytplay(requested_by, song)
                except Exception as e:
                    print(str(e))
                    await send(str(e))
                    playing = False
                    pass
            elif service == "saavn":
                playing = True
                del queue[0]
                try:
                    await jiosaavn(requested_by, song)
                except Exception as e:
                    print(str(e))
                    await send(str(e))
                    playing = False
                    pass
            elif service == "deezer":
                playing = True
                del queue[0]
                try:
                    await deezer(requested_by, song)
                except Exception as e:
                    print(str(e))
                    await send(str(e))
                    playing = False
                    pass


# Deezer----------------------------------------------------------------------------------------


async def deezer(requested_by, query):
    global playing
    m = await send(f"Deezer orqali {query} qidirilmoqda.")
    try:
        songs = await arq.deezer(query, 1)
        title = songs[0].title
        duration = convert_seconds(int(songs[0].duration))
        thumbnail = songs[0].thumbnail
        artist = songs[0].artist
        url = songs[0].url
    except Exception:
        await m.edit("Muisqa topilmadi.")
        playing = False
        return
    await m.edit("Albom tayorlanmoqda.")
    await generate_cover_square(
        requested_by, title, artist, duration, thumbnail
    )
    await m.edit("Yuklab olinmoqda.")
    await download_and_transcode_song(url)
    await m.delete()
    caption = f"🏷 Musiqa nomi: [{title[:35]}]({url})\n⏳ Davomiyligi: {duration}\n" \
               + f"🎧 Buyurtmachi: {requested_by}\n📡 Platforma: Deezer"
    m = await app.send_photo(
        chat_id=SUDO_CHAT_ID,
        photo="final.png",
        caption=caption,
    )
    os.remove("final.png")
    await asyncio.sleep(int(songs[0]["duration"]))
    await m.delete()
    playing = False


# Jiosaavn--------------------------------------------------------------------------------------


async def jiosaavn(requested_by, query):
    global playing
    m = await send(f"JioSaavn orqali {query} qidirilmoqda.")
    try:
        songs = await arq.saavn(query)
        sname = songs[0].song
        slink = songs[0].media_url
        ssingers = songs[0].singers
        sthumb = songs[0].image
        sduration = songs[0].duration
        sduration_converted = convert_seconds(int(sduration))
    except Exception as e:
        await m.edit("Muisqa topilmadi.")
        print(str(e))
        playing = False
        return
    await m.edit("Albom tayorlanmoqda.")
    await generate_cover_square(
        requested_by, sname, ssingers, sduration_converted, sthumb
    )
    await m.edit("Yuklab olinmoqda.")
    await download_and_transcode_song(slink)
    await m.delete()
    caption = f"🏷 Musiqa nomi: {sname[:35]}\n⏳ Davomiyligi: {sduration_converted}\n" \
               + f"🎧 Buyurtmachi: {requested_by}\n📡 Platforma: JioSaavn"
    m = await app.send_photo(
        chat_id=SUDO_CHAT_ID,
        caption=caption,
        photo="final.png",
    )
    os.remove("final.png")
    await asyncio.sleep(int(sduration))
    await m.delete()
    playing = False


# Youtube Play-----------------------------------------------------


async def ytplay(requested_by, query):
    global playing
    ydl_opts = {"format": "bestaudio"}
    m = await send(f"YouTube orqali {query} qidirilmoqda.")
    try:
        results = await arq.youtube(query)
        link = f"https://youtube.com{results[0].url_suffix}"
        title = results[0].title
        thumbnail = results[0].thumbnails[0]
        duration = results[0].duration
        views = results[0].views
        if time_to_seconds(duration) >= 1800:
            await m.edit("Kechirasiz musiqa davomiyligi 30 daqiqadan oshmasligi kerak.")
            playing = False
            return
    except Exception as e:
        await m.edit("Muisqa topilmadi.")
        playing = False
        print(str(e))
        return
    await m.edit("Albom tayorlanmoqda.")
    await generate_cover(requested_by, title, views, duration, thumbnail)
    await m.edit("Yuklab olinmoqda.")
    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(link, download=False)
        audio_file = ydl.prepare_filename(info_dict)
        ydl.process_info(info_dict)
    await m.edit("Saqlandi.")
    os.rename(audio_file, "audio.webm")
    transcode("audio.webm")
    await m.delete()
    m = await app.update_profile(bio = f"{title[:35]} ijro etilmoqda.")
    caption = f"🏷 Musiqa nomi: [{title[:35]}]({link})\n⏳ Davomiyligi {duration}\n" \
               + f"🎧 Buyurtmachi: {requested_by}\n📡 Platforma: YouTube"
    m = await app.send_photo(
        chat_id=SUDO_CHAT_ID,
        caption=caption,
        photo="final.png",
    )
    os.remove("final.png")
    await asyncio.sleep(int(time_to_seconds(duration)))
    playing = False
    await m.delete()    


# Telegram Audio------------------------------------


@app.on_message(
    filters.command("telegram") & filters.chat(SUDO_CHAT_ID) & ~filters.edited
)
async def tgplay(_, message):
    global playing
    if len(queue) != 0:
        await send("You Can Only Play Telegram Files After The Queue Gets "
                   + "Finished.")
        return
    if not message.reply_to_message:
        await send("Musiqa faylini ko'rsating.")
        return
    if message.reply_to_message.audio:
        if int(message.reply_to_message.audio.file_size) >= 104857600:
            await send("Musiqa hajmi 100 megabaytdan oshmasligi kerak.")
            playing = False
            return
        duration = message.reply_to_message.audio.duration
        if not duration:
            await send("Musiqani ijro etib bo'lmadi.")
            return
        m = await send("Yuklab olinmoqda.")
        song = await message.reply_to_message.download()
        await m.edit("Saqlandi.")
        transcode(song)
        await m.edit(f"Tayyor: {message.reply_to_message.link}")
        await asyncio.sleep(duration)
        playing = False
        return
    await send("Bu faylni ijro etib bo'lmaydi.")


async def send(text):
    m = await app.send_message(
        SUDO_CHAT_ID, text=text, disable_web_page_preview=True
    )
    return m


print(
    "\nBot ishlamoqda...\nhttps://github.com/izzatbekk/Telegram-vc-bot\n"
)


app.run()
