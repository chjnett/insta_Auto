import argparse
import asyncio
import os
import shutil
from pathlib import Path

from dotenv import load_dotenv
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

APPROVE, EDIT, REJECT = "approve", "edit", "reject"


def build_keyboard(episode_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ 승인", callback_data=f"{APPROVE}:{episode_id}"),
        InlineKeyboardButton("✏️ 수정", callback_data=f"{EDIT}:{episode_id}"),
        InlineKeyboardButton("❌ 반려", callback_data=f"{REJECT}:{episode_id}"),
    ]])


async def send_for_review(episode_id: str, video_path: Path, caption: str) -> None:
    bot = Bot(token=os.environ["TELEGRAM_BOT_TOKEN"])
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    with open(video_path, "rb") as f:
        await bot.send_video(chat_id=chat_id, video=f, caption=caption, reply_markup=build_keyboard(episode_id))


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    action, episode_id = query.data.split(":", 1)

    if action == APPROVE:
        src = ROOT / "output" / "final" / f"{episode_id}_final.mp4"
        dst_dir = ROOT / "output" / "ready_to_publish"
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst = dst_dir / src.name
        shutil.move(str(src), str(dst))
        await query.edit_message_caption(caption=f"✅ 승인됨 — {dst} 로 이동, 업로드 대기 중")
    elif action == EDIT:
        await query.edit_message_caption(caption="✏️ 수정 요청됨 — 대본/이미지 재검토 필요")
    else:
        await query.edit_message_caption(caption="❌ 반려됨")


async def run_bot_for(seconds: int) -> None:
    app = Application.builder().token(os.environ["TELEGRAM_BOT_TOKEN"]).build()
    app.add_handler(CallbackQueryHandler(on_callback))
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    await asyncio.sleep(seconds)
    await app.updater.stop()
    await app.stop()
    await app.shutdown()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--episode", required=True, nargs="+", help="one or more episode ids to send")
    parser.add_argument("--caption", default="검토 요청",
                         help="caption template; {episode} is substituted if present")
    parser.add_argument("--listen-seconds", type=int, default=300)
    args = parser.parse_args()

    async def flow():
        for episode_id in args.episode:
            video_path = ROOT / "output" / "final" / f"{episode_id}_final.mp4"
            caption = args.caption.format(episode=episode_id) if "{episode}" in args.caption else args.caption
            await send_for_review(episode_id, video_path, caption)
        await run_bot_for(args.listen_seconds)

    asyncio.run(flow())


if __name__ == "__main__":
    main()
