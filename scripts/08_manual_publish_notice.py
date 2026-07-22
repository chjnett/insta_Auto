import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from telegram import Bot

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


async def notify_ready_to_publish() -> int:
    ready_dir = ROOT / "output" / "ready_to_publish"
    videos = list(ready_dir.glob("*.mp4")) if ready_dir.exists() else []
    if not videos:
        print("[skip] no videos ready to publish")
        return 0

    bot = Bot(token=os.environ["TELEGRAM_BOT_TOKEN"])
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    await bot.send_message(
        chat_id=chat_id,
        text=f"이번 주 업로드할 {len(videos)}개 영상이 준비됐어요:\n" + "\n".join(v.name for v in videos),
    )
    return len(videos)


def main():
    count = asyncio.run(notify_ready_to_publish())
    print(f"[ok] notified for {count} videos")


if __name__ == "__main__":
    main()
