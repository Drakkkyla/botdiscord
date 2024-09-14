import asyncio
import disnake
from disnake.ext import commands
import os
import yt_dlp
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import json
from youtubesearchpython import VideosSearch
from yandex_music import ClientAsync


intents = disnake.Intents.default()
intents.all()
bot = commands.Bot(command_prefix="/", intents=intents, help_command=None)
radio_file = "radio_stations.json"
request_messages = {}
radio_playing = False
update_channel_id = 1228484399691989062
current_volume = 1.0


def read_update_file():
    if os.path.exists("update.txt"):
        with open("update.txt", "r") as file:
            return file.read().strip()
    return None


async def monitor_update_file():
    last_update = read_update_file()
    while True:
        current_update = read_update_file()
        if current_update != last_update:
            last_update = current_update
            channel = bot.get_channel(update_channel_id)
            if channel:
                await channel.send(f"📢 Обновление в системе бота:\n{current_update}")
            else:
                print(f"[ERROR] Канал с ID {update_channel_id} не найден.")
        await asyncio.sleep(10)


scheduler = AsyncIOScheduler()
scheduler.start()

YANDEX_MUSIC_TOKEN = "YANDEX_MUSIC_SECRET_KEY"
yandex_client = None


async def initialize_yandex_client():
    global yandex_client
    try:
        print("[DEBUG] Инициализация клиента Яндекс.Музыки...")
        yandex_client = await ClientAsync(YANDEX_MUSIC_TOKEN).init()
        print("[DEBUG] Клиент Яндекс.Музыки успешно инициализирован.")
    except Exception as e:
        print(f"[ERROR] Ошибка при инициализации клиента Яндекс.Музыки: {e}")


class RadioStationDropdown(disnake.ui.StringSelect):
    def __init__(self, radio_stations):
        options = [
            disnake.SelectOption(label=station_name, value=station_url, emoji="🎵")
            for station_name, station_url in radio_stations.items()
        ]

        super().__init__(
            placeholder="Выберите радиостанцию",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, inter: disnake.MessageInteraction):
        global radio_playing
        if not radio_playing:
            voice_channel = inter.author.voice.channel

            if voice_channel:
                voice_client = inter.guild.voice_client

                if voice_client and voice_client.channel != voice_channel:
                    await voice_client.move_to(voice_channel)
                elif not voice_client:
                    await voice_channel.connect()

                station_url = self.values[0]
                await play_radio(inter, station_url)
            else:
                await inter.response.send_message("Вы не находитесь в голосовом канале.", ephemeral=True)
        else:
            await inter.response.send_message("Радиостанция уже играет.", ephemeral=True)


class StartRadioView(disnake.ui.View):
    def __init__(self, radio_stations):
        super().__init__()

        self.add_item(RadioStationDropdown(radio_stations))

    async def on_timeout(self):
        self.clear_items()


def load_radio_stations():
    try:
        with open(radio_file, "r") as file:
            return json.load(file)
    except FileNotFoundError:
        return {}


def save_radio_stations(radio_stations_to_save):
    with open(radio_file, "w") as file:
        json.dump(radio_stations_to_save, file, indent=4)


radio_stations = load_radio_stations()

equalizer_presets = {
    "normal": "-af equalizer=f=0:width_type=h:width=200:g=0",
    "bass_boost": "-af equalizer=f=100:width_type=h:width=200:g=12",
}
current_equalizer = "normal"


def get_server_directory(guild_id):
    directory = f"server_files/{guild_id}"
    if not os.path.exists(directory):
        os.makedirs(directory)
    return directory


async def download_audio(url, guild_id):
    directory = get_server_directory(guild_id)
    file_path = os.path.join(directory, 'audio.mp3')
    ydl_opts = {
        'format': 'bestaudio',
        'outtmpl': file_path,
        'quiet': True
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
    return file_path


async def play_radio(inter, url):
    global radio_playing
    radio_playing = True

    voice_client = inter.guild.voice_client
    if voice_client:
        voice_client.stop()
        source = disnake.FFmpegPCMAudio(url, options="-vn")
        voice_client.play(source, after=lambda e: on_radio_finish(e))

    station_info = radio_stations.get(url)
    if station_info:
        image_url = station_info.get("image_url")
        embed = disnake.Embed(
            title="Воспроизводится радиостанция",
            description=f"**[Ссылка на радиостанцию]({url})**",
            color=0x00ff00
        )
        if image_url:
            embed.set_image(url=image_url)
        await inter.response.send_message(
            embed=embed,
            content=f"**СЕЙЧАС ИГРАЕТ:** {station_info.get('emoji', '🎵')} <3731_vinyl_disc>\n**ВКЛЮЧИЛ РАДИО:** "
                    f"{inter.author.mention}",
            components=[create_music_control_buttons()]
        )
    else:
        await inter.response.send_message(
            content=f"**Радиостанция воспроизводится:** {url}\n**ВКЛЮЧИЛ РАДИО:** {inter.author.mention}",
            components=[create_music_control_buttons()]
        )


def on_radio_finish(e):
    global radio_playing
    radio_playing = False


def cleanup(ctx, server_directory):
    try:
        for file in os.listdir(server_directory):
            file_path = os.path.join(server_directory, file)
            if os.path.isfile(file_path):
                os.remove(file_path)
    except Exception as e:
        print(f"Произошла ошибка при удалении файлов: {e}")


@bot.slash_command(description="Воспроизведите аудио по URL или по запросу на YouTube.")
async def play(ctx, query_or_url: str):
    await play_audio(ctx, query_or_url)


async def play_audio(ctx, query_or_url):
    try:
        if ctx.author.voice is None or ctx.author.voice.channel is None:
            await ctx.send("🎧 Вы должны быть в голосовом канале, чтобы я мог включить музыку. "
                           "Присоединяйтесь к какому-нибудь и попробуйте снова!", ephemeral=True)
            return

        voice_channel = ctx.author.voice.channel
        voice_client = ctx.guild.voice_client

        if voice_client and voice_client.channel != voice_channel:
            await voice_client.move_to(voice_channel)
        elif voice_client is None:
            voice_client = await voice_channel.connect()

        server_directory = get_server_directory(ctx.guild.id)

        if query_or_url in radio_stations.values():
            current_volume = 1.0  # Установите начальную громкость
            source = disnake.FFmpegPCMAudio(query_or_url, options=f"-vn -af 'volume={current_volume}'")
            track_info = "📻 Радиостанция"
        else:
            await ctx.send("🎶 Загружаю вашу музыку... Немного терпения, это займет всего несколько секунд!",
                           ephemeral=False)

            if query_or_url.startswith("http"):
                file_path = await download_audio(query_or_url, ctx.guild.id)
                current_volume = 1.0  # Установите начальную громкость
                source = disnake.FFmpegPCMAudio(file_path, options=f"-vn -af 'volume={current_volume}'")
                video_id = yt_dlp.YoutubeDL().extract_info(query_or_url, download=False)['id']
                youtube_link = f"https://www.youtube.com/watch?v={video_id}"
                track_info = f"🔗 Аудио по URL: [YouTube]({youtube_link})"
            else:
                videos_search = VideosSearch(query_or_url, limit=1)
                result = videos_search.result()
                if result["result"]:
                    video_url = "https://www.youtube.com/watch?v=" + result["result"][0]["id"]
                    file_path = await download_audio(video_url, ctx.guild.id)
                    current_volume = 1.0  # Установите начальную громкость
                    source = disnake.FFmpegPCMAudio(file_path, options=f"-vn -af 'volume={current_volume}'")
                    track_info = f"🔍 Найдено по запросу: {query_or_url}"
                else:
                    await ctx.send("😕 К сожалению, я не смог найти музыку по вашему запросу. Попробуйте что-то другое!",
                                   ephemeral=True)
                    return

        voice_client.play(source, after=lambda event: cleanup(ctx, server_directory))

        embed = disnake.Embed(
            title="🎵 Музыка в эфире!",
            description=f"**Трек:** {track_info}\n**Запросил:** {ctx.author.display_name}",
            color=0x00ff00
        )
        await ctx.send(embed=embed, components=[create_music_control_buttons()])

    except Exception as e:
        print(f"⚠️ Произошла ошибка при загрузке аудио: {e}")
        await ctx.send("😔 Ой! Что-то пошло не так при загрузке музыки. Попробуйте еще раз позже.", ephemeral=True)


@bot.slash_command(description="Начинает воспроизведение радиостанции.")
async def start_radio(inter: disnake.ApplicationCommandInteraction):
    view = StartRadioView(radio_stations)
    await inter.response.send_message("📻 Выберите радиостанцию из списка ниже и наслаждайтесь музыкой:", view=view)

    interactivity = await view.wait()
    view.stop()


@bot.slash_command(description="Останавливает воспроизведение радиостанции.")
async def stop_radio(ctx: disnake.ApplicationCommandInteraction):
    global radio_playing

    voice_client = ctx.guild.voice_client
    if voice_client:
        voice_client.stop()
        radio_playing = False
        await ctx.response.send_message("⏹ Радиостанция остановлена. Надеемся, вам понравилось!", ephemeral=True)
    else:
        await ctx.response.send_message("😕 Бот не находится в голосовом канале.", ephemeral=True)


@bot.slash_command(description="Изменить громкость воспроизведения.")
async def volume(ctx, volume: float):
    global current_volume
    current_volume = volume

    voice_client = ctx.guild.voice_client
    if voice_client and voice_client.is_playing():
        voice_client.pause()
        source = disnake.FFmpegPCMAudio(voice_client.source, options=f"-af 'volume={current_volume}'")
        voice_client.play(source)
        await ctx.send(f"🔊 Громкость установлена на {volume * 100}%")
    else:
        await ctx.send("Ничего не играет в данный момент.")


@bot.slash_command(description="Пропускает текущую композицию.")
async def skip(ctx):
    voice_client = ctx.guild.voice_client
    if voice_client and voice_client.is_playing():
        voice_client.stop()
        await ctx.send("⏭️ Трек пропущен! Как насчет чего-то новенького?", ephemeral=True)
    else:
        await ctx.send("😕 Сейчас ничего не играет, чтобы пропустить.", ephemeral=True)


@bot.slash_command(description="Отключается от голосового канала.")
async def leave(ctx):
    voice_client = ctx.guild.voice_client
    if voice_client and voice_client.is_connected():
        await voice_client.disconnect()
        global radio_playing
        radio_playing = False
        await ctx.send("👋 Бот отключен от голосового канала. До скорых встреч!", ephemeral=True)
    else:
        await ctx.send("😕 Бот не подключен к голосовому каналу.", ephemeral=True)


@bot.slash_command(description="Удаляет определенное количество сообщений из чата.")
async def clear(ctx, amount: int):
    if ctx.author.guild_permissions.manage_messages:
        if amount <= 0:
            await ctx.send("🔢 Количество сообщений должно быть больше нуля. Попробуйте снова.", ephemeral=True)
            return
        await ctx.channel.purge(limit=amount + 1)
        success_message = await ctx.send(f"✅ Успешно удалено {amount} сообщений.", ephemeral=True)
        await asyncio.sleep(5)
        await success_message.delete()
    else:
        await ctx.send("🚫 У вас недостаточно прав для выполнения этой команды.", ephemeral=True)


@bot.slash_command(description="Настройте звук с помощью эквалайзера.")
async def equalizer(ctx, preset: str):
    await ctx.send("🔧 Команда эквалайзера удалена из-за проблем с функциональностью.")


async def search_yandex_track(query):
    search_result = await yandex_client.search(query)
    tracks = search_result.tracks.results if search_result.tracks else []
    return tracks


async def download_yandex_track(track, guild_id):
    directory = get_server_directory(guild_id)
    file_path = os.path.join(directory, 'yandex_audio.mp3')
    await track.download_async(file_path)
    return file_path


@bot.slash_command(description="Ищет и воспроизводит трек с Яндекс.Музыки по запросу.")
async def play_yandex(ctx, *, query: str):
    if ctx.author.voice is None or ctx.author.voice.channel is None:
        await ctx.send("🎧 Вы должны быть в голосовом канале, чтобы я мог включить музыку. "
                       "Присоединяйтесь к какому-нибудь и попробуйте снова!", ephemeral=True)
        return

    voice_channel = ctx.author.voice.channel
    voice_client = ctx.guild.voice_client

    if voice_client:
        if voice_client.channel != voice_channel:
            await voice_client.move_to(voice_channel)
    else:
        try:
            voice_client = await voice_channel.connect()
        except Exception as e:
            print(f"Ошибка при подключении к голосовому каналу: {e}")
            await ctx.send("⚠️ Не удалось подключиться к голосовому каналу. Попробуйте снова позже.", ephemeral=True)
            return

    server_directory = get_server_directory(ctx.guild.id)

    try:
        if yandex_client is None:
            print("[ERROR] Клиент Яндекс.Музыки не инициализирован.")
            await ctx.send("😓 Похоже, у нас проблемы с подключением к Яндекс.Музыке. Попробуйте позже.", ephemeral=True)
            return

        await ctx.send("🎧 Ищем ваш трек на Яндекс.Музыке... Пожалуйста, подождите!", ephemeral=False)
        tracks = await search_yandex_track(query)

        if not tracks:
            await ctx.send("😔 Не удалось найти трек по вашему запросу. Попробуйте другой запрос.", ephemeral=True)
            return

        track = tracks[0]
        file_path = await download_yandex_track(track, ctx.guild.id)
        current_volume = 1.0  # Установите начальную громкость
        source = disnake.FFmpegPCMAudio(file_path, options=f"-vn -af 'volume={current_volume}'")

        voice_client.play(source, after=lambda event: cleanup(ctx, server_directory))

        embed = disnake.Embed(
            title="🎶 Музыка в эфире! Воспроизведение из Яндекс Музыки! ⚡",
            description=f"**Трек:** {track.title}\n**Исполнитель:** {track.artists[0].name}\n**Запросил:** "
                        f"{ctx.author.display_name}",
            color=0x00ff00
        )
        await ctx.send(embed=embed, components=[create_music_control_buttons()])

    except Exception as e:
        print(f"[ERROR] Произошла ошибка при поиске или загрузке трека с Яндекс.Музыки: {e}")
        await ctx.send("😕 Ой! Что-то пошло не так. Попробуйте еще раз позже.", ephemeral=True)


def create_music_control_buttons():
    button_pause = disnake.ui.Button(label="⏸️", style=disnake.ButtonStyle.primary, custom_id="pause")
    button_stop = disnake.ui.Button(label="⏹️", style=disnake.ButtonStyle.danger, custom_id="stop")
    button_skip = disnake.ui.Button(label="⏩", style=disnake.ButtonStyle.secondary, custom_id="skip")
    button_volume_up = disnake.ui.Button(label="-", style=disnake.ButtonStyle.success, custom_id="volume_up")
    button_volume_down = disnake.ui.Button(label="-", style=disnake.ButtonStyle.success, custom_id="volume_down")

    action_row = disnake.ui.ActionRow(button_pause, button_stop, button_skip, button_volume_down, button_volume_up)
    return action_row


@bot.event
async def on_button_click(inter: disnake.MessageInteraction):
    voice_client = inter.guild.voice_client

    if voice_client is None:
        await inter.response.send_message("Бот не подключен к голосовому каналу.", ephemeral=True)
        return

    if inter.component.custom_id == 'pause':
        if voice_client.is_playing():
            voice_client.pause()
            await inter.response.send_message("Музыка приостановлена.", ephemeral=True)
        else:
            await inter.response.send_message("Музыка не воспроизводится.", ephemeral=True)

    elif inter.component.custom_id == 'stop':
        if voice_client.is_playing():
            voice_client.stop()
            await voice_client.disconnect()
            await inter.response.send_message("Музыка остановлена и бот отключен.", ephemeral=True)
        else:
            await inter.response.send_message("Музыка не воспроизводится.", ephemeral=True)

    elif inter.component.custom_id == 'skip':
        if voice_client.is_playing():
            voice_client.stop()
            await inter.response.send_message("Текущий трек пропущен.", ephemeral=True)
        else:
            await inter.response.send_message("Музыка не воспроизводится.", ephemeral=True)


@bot.event
async def on_ready():
    print(f'[INFO] Бот подключился к Discord и находится в сети под именем {bot.user}')
    await initialize_yandex_client()
    await bot.loop.create_task(monitor_update_file())

bot.run('YOUR_BOT_SECRET_KEY')
