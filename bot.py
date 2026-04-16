import os
import discord
from discord.ext import tasks, commands
from dotenv import load_dotenv
from googleapiclient.discovery import build
import asyncio

# .envファイルから設定を読み込む
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
API_KEY = os.getenv("YOUTUBE_APIKEY")
CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID"))

# 検索条件
OR_KEYWORDS = ["音声作品"]
AND_KEYWORDS = ["ASMR", "Vtuber", "2DLive", "Live2d", "3DLive"]
EXCLUDE_KEYWORDS = [ ]

# 通知済み動画を記録するファイル名
SENT_VIDEOS_FILE = "sent_ids.txt"

# Discord Botの設定
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# YouTube APIのビルド
youtube = build('youtube', 'v3', developerKey=API_KEY)


def load_sent_ids():
    """通知済みの動画IDをファイルから読み込む"""
    if not os.path.exists(SENT_VIDEOS_FILE):
        return set()
    with open(SENT_VIDEOS_FILE, "r") as f:
        return set(line.strip() for line in f)


def save_sent_id(video_id):
    """新しい動画IDをファイルに追記する"""
    with open(SENT_VIDEOS_FILE, "a") as f:
        f.write(f"{video_id}\n")


@bot.event
async def on_ready():
    print(f"ログインしました: {bot.user.name}")
    # 12時間おきのループを開始
    search_loop.start()


@tasks.loop(hours=12)
async def search_loop():
    print("定期検索を開始します……")
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        print("通知先のチャンネルがありません")
        return

    # 検索クエリの作成
    or_query = f"({'|'.join(OR_KEYWORDS)})"
    and_query = f"({'|'.join(AND_KEYWORDS)})"
    exclude_query = f"({' -'.join([''] + EXCLUDE_KEYWORDS)})"  # NOT検索用に修正
    final_q = f"{or_query} {and_query} {exclude_query}"

    try:
        # YouTube検索実行
        request = youtube.search().list(
            part="snippet",
            q=final_q,
            type="video",
            order="date",
            videoDuration="medium",
            maxResults=5
        )
        response = request.execute()

        sent_ids = load_sent_ids()
        seen_channels = set()
        new_notifications = 0

        for item in response.get('items', []):
            video_id = item['id']['videoId']
            channel_id = item['snippet']['channelId']

            # 重複排除: この回の実行で既に出したチャンネル ＆ 過去に通知済みの動画ID
            if channel_id not in seen_channels and video_id not in sent_ids:
                title = item['snippet']['title']
                url = f"https://www.youtube.com/watch?v={video_id}"

                # Discordに送信
                await channel.send(f"【新着ASMR】\nタイトル: {title}\nURL: {url}")

                # 記録を更新
                save_sent_id(video_id)
                seen_channels.add(channel_id)
                new_notifications += 1

                # API負荷軽減のための小さな待機
                await asyncio.sleep(1)

        print(f"検索完了。新しく {new_notifications} 件通知しました。定期検索を終了します……")

    except Exception as e:
        print(f"エラーが発生しちゃった: {e}")


bot.run(DISCORD_TOKEN)