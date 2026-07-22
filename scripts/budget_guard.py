import csv
import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG_PATH = ROOT / "logs" / "run_log.csv"

COST_ESTIMATES_USD = {
    "image": 0.039,
    "text": 0.01,
    # gemini-3.1-flash-tts-preview: $20/1M output audio tokens, 25 tokens/sec
    # of audio -> ~$0.0005/sec. Rounded up generously for a ~30s clip.
    "tts": 0.03,
}


class BudgetExceededError(Exception):
    pass


def cumulative_cost() -> float:
    if not LOG_PATH.exists():
        return 0.0
    total = 0.0
    with open(LOG_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total += float(row["estimated_cost_usd"])
    return total


def check_and_record(script: str, call_type: str, settings: dict) -> None:
    """Raises BudgetExceededError and records nothing if the call would exceed budget_limit_usd.
    Otherwise appends a log row and lets the caller proceed with the real API call."""
    cost = COST_ESTIMATES_USD[call_type]
    current = cumulative_cost()
    budget = settings["budget_limit_usd"]
    if current + cost > budget:
        raise BudgetExceededError(
            f"예산 초과: 누적 ${current:.3f} + 이번 호출(예상) ${cost:.3f} > 한도 ${budget:.2f}. "
            f"config/settings.json의 budget_limit_usd를 확인하거나 logs/run_log.csv를 검토하세요."
        )

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    is_new = not LOG_PATH.exists()
    new_total = current + cost
    with open(LOG_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(["timestamp", "script", "call_type", "estimated_cost_usd", "cumulative_cost_usd"])
        writer.writerow([
            datetime.datetime.now().isoformat(timespec="seconds"),
            script,
            call_type,
            f"{cost:.4f}",
            f"{new_total:.4f}",
        ])
