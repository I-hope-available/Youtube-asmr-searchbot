import os
from dotenv import load_dotenv
from googleapiclient.discovery import build

#あれこれ

# 検索ワードリスト！
OR_KEYWORDS = ["音声作品",]
AND_KEYWORDS = ["ASMR", "Vtuber", "2DLive", "Live2d", "3DLive"]
EXCLUDE_KEYWORDS = ["咀嚼音", "実写", "カメラ", ]

# APIキー・トークン
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_KEY = os.getenv("YOUTUBE-APIKEY")

#検索クエリ
or_query = f"({'|'.join(OR_KEYWORDS)})"
and_query = f"({'|'.join(AND_KEYWORDS)})"
exclude_query = f"({'|'.join(EXCLUDE_KEYWORDS)})"
final_q = f"{or_query} {and_query} {exclude_query}"

# 以下コード

youtube = build('youtube', 'v3', developerKey=API_KEY)

# 「ASMR」というワードで最新の動画を1件検索
request = youtube.search().list(
    part="snippet",
    q=final_q,
    type="video",
    order="date",
    maxResults=15
)
response = request.execute()

# --- 検索結果の処理部分 ---

seen_channels = set()  # すでに表示したチャンネルIDを保存する箱
unique_videos = []  # 最終的に採用する動画リスト

for item in response.get('items', []):
    channel_id = item['snippet']['channelId']

    # もし、このチャンネルIDが「すでに見た箱」に入っていなければ採用
    if channel_id not in seen_channels:
        unique_videos.append(item)
        seen_channels.add(channel_id)  # 箱にIDをメモしておく

# --- 最終的な結果を表示 ---
print(f"--- 重複を除いた結果 ({len(unique_videos)}件) ---")
for item in unique_videos:
    title = item['snippet']['title']
    video_id = item['id']['videoId']
    print(f"チャンネル名: {item['snippet']['channelTitle']}")
    print(f"タイトル: {title}")
    print(f"URL: https://www.youtube.com/watch?v={video_id}")
    print("-" * 20)