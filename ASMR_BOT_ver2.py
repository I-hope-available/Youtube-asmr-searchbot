import os
import discord
from discord.ext import tasks, commands
from dotenv import load_dotenv
from google.protobuf.internal.well_known_types import Duration
from googleapiclient.discovery import build
import asyncio
import datetime
import requests
import openmeteo_requests
from retry_requests import Retry

# ==================================================================================
#APIキー・トークン等
# ==================================================================================

load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_APIKEY")
CHANNEL_ID = os.getenv("CHANNEL_ID")

# ==================================================================================
#検索ワード定義
# ==================================================================================

#コア検索ワード
CORE_KEYWORDS = ["Vtuber", "ASMR"]
SUB_CORE_KEYWORDS = ["Live2D", "3DLive", "音声作品" ]
IGNORE_KEYWORDS = []

#open-meteoで取得した天気を基にした動的なキーワード　天気や気温から自動的に選択
CURRENT_ENV_KEYWORDS = {
    #天気　思いつかなかったので今は雨と曇りをまとめて、晴天時は定義していない
    "gloomy": ["雨音", "しっとり", "オイル"],

    #気温
    "hot": ["炭酸", "氷"],
    "cold": ["焚火", "添い寝"]
}

#==================================================================================
#ユーティリティ関数
#==================================================================================

def get_weather_info():

    try:
        # セットアップ済みのセッションを使用
        cache_session = Retry(total=5, backoff_factor=0.2).session()
        openmeteo = openmeteo_requests.Client(session=cache_session)

        # 東京の座標
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": 35.6895,
            "longitude": 139.6917,
            "current": ["weather_code", "temperature_2m"]
        }
        responses = openmeteo.weather_api(url, params=params)
        current = responses[0].Current()

        weather_code = int(current.Variables(0).Value())
        temp = float(current.Variables(1).Value())
        return weather_code, temp
    except Exception as e:
        print(f"天気取得エラー: {e}")
        return None, None

#===========================================================================
#検索クエリ生成
#===========================================================================

def generate_smart_query(weather_code, temp):
    import random

    #絶対条件
    core_words = " ".join(CORE_KEYWORDS)

    #サブ条件　ランダムに選出
    sub_words = random.choice(SUB_CORE_KEYWORDS)

    #除外条件
    ignore_words = " ".join(IGNORE_KEYWORDS)

    #環境ワード
    spices = []

    # 天気判定 (WMO 1-3: 曇り系, 51-67: 雨系)
    if weather_code is not None and (1 <= weather_code <= 67):
        spices.append(random.choice(CURRENT_ENV_KEYWORDS["gloomy"]))

    # 気温判定
    if temp is not None:
        if temp >= 25:
            spices.append(random.choice(CURRENT_ENV_KEYWORDS["hot"]))
        elif temp <= 15:
            val = random.choice(CURRENT_ENV_KEYWORDS["cold"])
            if val: spices.append(val)  # 空文字でない場合のみ追加


    # 結合してクエリ完成
    spice_str = " ".join(spices)
    return f"{core_words} {sub_words} {spice_str} {ignore_words} ".strip()

# ==================================================================================
# ボットの初期設定
# ==================================================================================

if not YOUTUBE_API_KEY:
    print("CRITICAL ERROR: YOUTUBE_API_KEY が見つからないよ。")
    print(".env の中身が 'YOUTUBE_API_KEY=xxx' になっているか確認してね。")
    exit()

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)

# ==================================================================================
# 定期実行ループ
# ==================================================================================

# 毎日20時に実行 (JST)
JST = datetime.timezone(datetime.timedelta(hours=+9), 'JST')
target_time = datetime.time(hour=22, minute=30, second=0, tzinfo=JST)


@tasks.loop(time=target_time)
async def run_search_task(channel):
    print("検索を開始します……")

    # 天気と気温を取得
    weather_code, temp = get_weather_info()
    # クエリを生成
    query = generate_smart_query(weather_code, temp)
    print(f"生成クエリ: {query}")

    # 1. 天気と気温を取得 (ユーティリティ関数)
    weather_code, temp = get_weather_info()

    # 2. クエリを生成 (ユーティリティ関数)
    query = generate_smart_query(weather_code, temp)
    print(f"生成されたクエリ: {query}")

    try:
        # 3. YouTube API で検索実行
        request = youtube.search().list(
            part="snippet",
            q=query,
            type="video",
            videoDuration="long",
            order="date",
            maxResults=10  # 多めに取ってフィルタリング
        )
        response = request.execute()

        new_videos = []
        for item in response.get('items', []):
            video_id = item['id']['videoId']
            title = item['snippet']['title']

            if "#shorts" in title.lower() or "shorts" in title.lower():
                continue

            url = f"https://www.youtube.com/watch?v={video_id}"
            new_videos.append(f"・{title}\n  {url}")

            if len(new_videos) >= 5:

        # 4. Discord へ送信
        if new_videos:
            msg = f"【寝ろ（検索条件：{query}）】\n\n" + "\n\n".join(new_videos)
            await channel.send(msg)
            print(f"通知完了: {len(new_videos)} 件")
        else:
            print("新しい動画は見つかりませんでした")

    except Exception as e:
        print(f"検索エラーが発生: {e}")

#===================================================================================
#即時実行コマンド
#===================================================================================

@bot.command(name="instant")
async def instant(ctx):
    await ctx.send("即時検索を実行します")

    await run_search_task(ctx.channel)

# ==================================================================================
# 実行開始
# ==================================================================================

@bot.event
async def on_ready():
    print(f"ログイン成功: {bot.user.name}")
    if not run_search_task.is_running():
        run_search_task.start()


bot.run(DISCORD_TOKEN)