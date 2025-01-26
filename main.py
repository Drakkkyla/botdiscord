import asyncio
import disnake
from disnake.ext import commands
from googleapiclient.discovery import build
import os
import yt_dlp
import json
from youtubesearchpython import VideosSearch

intents = disnake.Intents.default()
intents.messages = True
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="/", intents=intents, help_command=None)

allowed_user_id = 
message_sent = False
role_id = 
allowed_role_id = 
music_urls = [
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "https://www.youtube.com/watch?v=3JWTaaS7LdU",
    "https://www.youtube.com/watch?v=kJQP7kiw5Fk",
]
radio_file = "radio_stations.json"


def load_radio_stations():
    try:
        with open(radio_file, "r") as file:
            return json.load(file)
    except FileNotFoundError:
        return {}


def save_radio_stations(radio_stations):
    with open(radio_file, "w") as file:
        json.dump(radio_stations, file)


radio_stations = load_radio_stations()


async def download_audio(url):
    ydl_opts = {'format': 'bestaudio', 'outtmpl': 'video.mp3'}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])


class VerifyModal(disnake.ui.Modal):
    def __init__(self, code):
        self.code = code
        components = [
            disnake.ui.TextInput(label="Введите код", placeholder=self.code, custom_id="code")
        ]
        super().__init__(title="Верификация", components=components, custom_id="verify_modal")

    async def callback(self, interaction: disnake.ModalInteraction) -> None:
        if self.code == int(interaction.text_values["code"]):
            role = interaction.guild.get_role(1220453536689815592)  # ID вашей роли
            await interaction.author.remove_roles(role)
            await interaction.response.send_message("Вы успешно прошли верификацию!", ephemeral=True)
            # Выдача роли после успешной верификации
            verified_role = interaction.guild.get_role(1220453555543081021)  # ID вашей роли
            await interaction.author.add_roles(verified_role)
        else:
            await interaction.response.send_message("Неверный код!", ephemeral=True)


class ButtonView(disnake.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @disnake.ui.button(label="Верификация", style=disnake.ButtonStyle.green, custom_id="button1")
    async def button1(self, button: disnake.ui.Button, interaction: disnake.Interaction):
        import random
        code = random.randint(1000, 9999)
        await interaction.response.send_modal(VerifyModal(code))


class Verify(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.persistents_views_added = False

    @bot.slash_command(description="Верификация пользователя на сервере")
    async def verify(self, ctx):
        embed = disnake.Embed(color=0x2F3136)
        embed.set_image(url='https://i.imgur.com/2vWxaNL.png')
        await ctx.send(embed=embed, view=ButtonView())

    @commands.Cog.listener()
    async def on_connect(self):
        if self.persistents_views_added:
            return

        self.bot.add_view(ButtonView(), message_id=...)


@bot.slash_command(description="Отправляет приветственное сообщение новому участнику сервера.")
async def welcome(ctx, member: disnake.Member):
    embed = disnake.Embed(
        title="Добро пожаловать на наш сервер!",
        description=f"Привет, {member.mention}! Рады видеть тебя здесь. Надеемся, что тебе здесь понравится!",
        color=0x00ff00
    )
    await member.send(embed=embed)
    await ctx.send(f"Приветственное сообщение отправлено участнику {member.mention}.")


@bot.slash_command(description="Реклама видео с YouTube.")
async def advert(ctx, url: str, channel: disnake.TextChannel):
    allowed_role = ctx.guild.get_role(allowed_role_id)
    if allowed_role in ctx.author.roles:
        youtube = build('youtube', 'v3', developerKey='AIzaSyCcv4tjl5UmRVnRwGQA5QGG43pL_-Rtm4s')

        video_id = url.split("v=")[-1]
        request = youtube.videos().list(
            part="snippet",
            id=video_id
        )
        response = request.execute()

        if 'items' in response and response['items']:
            video_info = response['items'][0]['snippet']
            video_title = video_info['title']
            video_thumbnail = video_info['thumbnails']['default']['url']

            embed = disnake.Embed(
                title="Новое видео!",
                description=f"У нашего канала вышел новый видео! Лайк и комментарий {ctx.guild.default_role.mention}\n[Ссылка на видео]({url})",
                color=0xFF5733
            )
            embed.add_field(name="Ссылка на видео:", value=f"[{video_title}]({url})", inline=False)
            embed.set_thumbnail(url=video_thumbnail)
            await channel.send(embed=embed)

            members_mention = " ".join([member.mention for member in ctx.guild.members])
            spoiler_text = f'||{members_mention}||'
            await channel.send(content=spoiler_text)

            await ctx.send(f"Рекламное сообщение успешно отправлено в канал {channel.mention}.")
        else:
            await ctx.send("Не удалось получить информацию о видео. Убедитесь, что ссылка корректна и видео доступно.")
    else:
        await ctx.send("У вас нет прав на использование этой команды.")


def cleanup(ctx):
    os.remove("video.mp3")


@bot.slash_command(description="Воспроизводит аудио по указанному URL или поиск на YouTube.")
async def play(ctx, query_or_url: str):
    await play_audio(ctx, query_or_url)


async def check_channel_stream(channel_ids):
    youtube = build('youtube', 'v3', developerKey='AIzaSyCcv4tjl5UmRVnRwGQA5QGG43pL_-Rtm4s')
    for channel_id in channel_ids:
        request = youtube.search().list(
            part='snippet',
            channelId=channel_id,
            type='video',
            eventType='live',
            maxResults=1
        )
        response = request.execute()
        items = response.get('items', [])
        if items:
            stream_title = items[0]['snippet']['title']
            channel = bot.get_channel(1220448854168830084)  # Replace CHANNEL_ID with your channel ID
            await channel.send(f"🔴 **{stream_title}** сейчас в прямом эфире на YouTube!: {channel_id}")


async def play_audio(ctx, query_or_url):
    try:
        if ctx.author.voice is None or ctx.author.voice.channel is None:
            await ctx.send("Вы не находитесь в голосовом канале.")
            return

        voice_channel = ctx.author.voice.channel
        voice_client = ctx.guild.voice_client

        if voice_client and voice_client.channel != voice_channel:
            await voice_client.move_to(voice_channel)
        elif voice_client is None:
            voice_client = await voice_channel.connect()

        if query_or_url in radio_stations.values():
            source = disnake.FFmpegPCMAudio(query_or_url)
            track_info = "Радиостанция"
        else:
            await ctx.send("Подождите, аудио загружается...")

            if query_or_url.startswith("http"):
                await download_audio(query_or_url)
                source = disnake.FFmpegPCMAudio("video.mp3")

                video_id = yt_dlp.YoutubeDL().extract_info(query_or_url, download=False)['id']
                youtube_link = f"https://www.youtube.com/watch?v={video_id}"
                track_info = f"Аудио по URL: [YouTube]({youtube_link})"
            else:
                videosSearch = VideosSearch(query_or_url, limit = 1)
                result = videosSearch.result()
                if result["result"]:
                    video_url = "https://www.youtube.com/watch?v=" + result["result"][0]["id"]
                    await download_audio(video_url)
                    source = disnake.FFmpegPCMAudio("video.mp3")

                    track_info = f"Аудио по запросу: {query_or_url}"
                else:
                    await ctx.send("Не удалось найти видео по вашему запросу.")
                    return

        voice_client.play(source, after=lambda e: cleanup(ctx))

        embed = disnake.Embed(
            title="Воспроизводится музыка",
            description=f"**Трек:** {track_info}\n**Запросил:** {ctx.author.display_name}",
            color=0x00ff00
        )
        await ctx.send(embed=embed)

    except Exception as e:
        print(f"Произошла ошибка при загрузке аудио: {e}")
        await ctx.send("Произошла ошибка при загрузке аудио.")


async def update_radio(ctx, action, station_name=None, station_url=None):
    if action == "add":
        if not station_name:
            await ctx.send("Введите название радиостанции:")
            try:
                response = await bot.wait_for('message', check=lambda m: m.author == ctx.author, timeout=30)
                station_name = response.content
            except asyncio.TimeoutError:
                await ctx.send("Время на ввод названия радиостанции истекло.")
                return

        if not station_url:
            await ctx.send("Введите URL-адрес радиостанции:")
            try:
                response = await bot.wait_for('message', check=lambda m: m.author == ctx.author, timeout=30)
                station_url = response.content
            except asyncio.TimeoutError:
                await ctx.send("Время на ввод URL-адреса радиостанции истекло.")
                return

        radio_stations[station_name] = station_url
        save_radio_stations(radio_stations)
        await ctx.send(f"Радиостанция '{station_name}' успешно добавлена.")

    elif action == "remove":
        if station_name in radio_stations:
            del radio_stations[station_name]
            save_radio_stations(radio_stations)
            await ctx.send(f"Радиостанция '{station_name}' успешно удалена.")
        else:
            await ctx.send(f"Радиостанции с названием '{station_name}' не существует.")


@bot.slash_command(description="Удаляет радиостанцию.")
async def remove_radio(ctx, station_name: str):
    if ctx.author.id != allowed_user_id:
        await ctx.send("У вас нет прав доступа к настройкам.")
        return

    await remove_radio(ctx, station_name)


@bot.slash_command(description="Выполняет операции с настройками.")
async def setting(ctx, action: str, *args):
    if ctx.author.id != allowed_user_id:
        await ctx.send("У вас нет прав доступа к настройкам.")
        return

    if action in ("add_radio", "remove_radio"):
        if len(args) < 1:
            await ctx.send("Необходимо указать название радиостанции.")
            return
        station_name = args[0]
        if action == "add_radio":
            if len(args) < 2:
                await ctx.send("Необходимо указать URL-адрес радиостанции.")
                return
            station_url = args[1]
        else:
            station_url = None
        await update_radio(ctx, action.split("_")[0], station_name, station_url)
    else:
        await ctx.send("Неверное действие. Доступные действия: add_radio, remove_radio и т.д.")


@bot.slash_command(description="Начинает воспроизведение радиостанции.")
async def start_radio(ctx):
    radio_list = "\n".join([f"{index + 1}. {station}" for index, station in enumerate(radio_stations.keys())])
    await ctx.send(f"Выберите радиостанцию:\n{radio_list}")

    def check(message):
        return (message.author == ctx.author and message.content.isdigit() and 1 <= int(message.content)
                <= len(radio_stations))

    try:
        response = await bot.wait_for('message', check=check, timeout=30)
        selected_station = list(radio_stations.keys())[int(response.content) - 1]
        await play(ctx, radio_stations[selected_station])
    except asyncio.TimeoutError:
        await ctx.send("Время на выбор радиостанции истекло.")


@bot.slash_command(description="Пропускает текущую композицию.")
async def skip(ctx):
    voice_client = ctx.guild.voice_client
    if voice_client and voice_client.is_playing():
        voice_client.stop()
        await ctx.send("Песня пропущена.")
    else:
        await ctx.send("Нет песни, которую можно пропустить.")


@bot.slash_command(description="Отключается от голосового канала.")
async def leave(ctx):
    voice_client = ctx.guild.voice_client
    if voice_client and voice_client.is_connected():
        await voice_client.disconnect()
        await ctx.send("Бот отключен от голосового канала.")
    else:
        await ctx.send("Бот не подключен к голосовому каналу.")


@bot.slash_command(description="Удаляет определенное количество сообщений из чата.")
async def clear(ctx, amount: int):
    if ctx.author.guild_permissions.manage_messages:
        if amount <= 0:
            await ctx.send("Количество сообщений должно быть больше нуля.")
            return
        await ctx.channel.purge(limit=amount + 1)
        success_message = await ctx.send(f"Успешно удалено {amount} сообщений.")
        await asyncio.sleep(5)
        await success_message.delete()
    else:
        await ctx.send("У вас недостаточно прав для выполнения этой команды.")


@bot.event
async def on_ready():
    global message_sent
    print(f'Бот подключился к Discord и находится в сети под именем {bot.user}')
    channel_ids = ['UCjBt33cBcZa7hWE8j-0Zk8g', 'UCYkZUQxBEuiw-uZ3f04z0sQ']
    await check_channel_stream(channel_ids)


@bot.event
async def on_raw_reaction_add(payload):
    if payload.message_id == 1220685091408318474:
        guild = bot.get_guild(payload.guild_id)
        role = guild.get_role(role_id)
        if role and payload.emoji.name == '🔵':
            member = guild.get_member(payload.user_id)
            if member:
                await member.add_roles(role)
                print(f"Роль {role.name} выдана пользователю {member.name}")
            else:
                print(f"Пользователь с ID {payload.user_id} не найден на сервере {guild.name}")
        else:
            print("Роль не найдена или используется другая эмодзи.")


@bot.event
async def on_member_join(member):
    guild = member.guild
    role = guild.get_role(1220453536689815592)
    if role is not None:
        await member.add_roles(role)
        print(f"Роль {role.name} успешно выдана участнику {member.display_name}")
    else:
        print("Указанная роль не найдена.")


@bot.event
async def on_member_remove(member):
    print(f'{member} покинул сервер.')


bot.run('YOUR_TOKEN')
