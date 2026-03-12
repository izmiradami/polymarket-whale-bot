"""
Polymarket Whale Alert Bot
--------------------------
Büyük alımları tespit edip Telegram'a bildirim gönderir.

KURULUM:
  pip install requests schedule

KULLANIM:
  1. Aşağıdaki CONFIG bölümünü doldurun
  2. python polymarket_whale_bot.py
"""

import requests
import time
import schedule
import logging
from datetime import datetime, timezone

# ─────────────────────────────────────────
#  CONFIG — buraya kendi değerlerini gir
# ─────────────────────────────────────────
TELEGRAM_BOT_TOKEN = "YOUR_BOT_TOKEN"
TELEGRAM_CHAT_ID   = "YOUR_CHAT_ID"

MIN_TRADE_SIZE_USD = 1000
CHECK_INTERVAL_SEC = 30
MAX_MARKETS        = 100
BATCH_SIZE         = 10
TRADES_PER_BATCH   = 50
# ─────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)

# Son kontrolün unix timestamp'i — sadece bundan SONRA gelen trade'leri göster
last_check_time: int = 0

GAMMA_BASE = "https://gamma-api.polymarket.com"
DATA_BASE  = "https://data-api.polymarket.com"


def send_telegram(message: str) -> None:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        r.raise_for_status()
        log.info("Telegram bildirimi gönderildi.")
    except Exception as e:
        log.error(f"Telegram hatası: {e}")


def get_top_markets(limit: int = MAX_MARKETS) -> list:
    try:
        r = requests.get(
            f"{GAMMA_BASE}/markets",
            params={"active": "true", "closed": "false", "limit": limit,
                    "order": "volume24hr", "ascending": "false"},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else data.get("markets", [])
    except Exception as e:
        log.error(f"Market listesi alınamadı: {e}")
        return []


def get_trades_for_markets(condition_ids: list, limit: int = TRADES_PER_BATCH) -> list:
    try:
        r = requests.get(
            f"{DATA_BASE}/trades",
            params={"market": ",".join(condition_ids), "limit": limit},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else []
    except Exception as e:
        log.warning(f"Trade verisi alınamadı: {e}")
        return []


def calc_usd_size(trade: dict) -> float:
    try:
        if trade.get("usdcSize"):
            return float(trade["usdcSize"])
        return float(trade.get("price", 0)) * float(trade.get("size", 0))
    except Exception:
        return 0.0


def format_alert(trade: dict, usd_size: float) -> str:
    question   = trade.get("title", "Bilinmeyen Market")
    outcome    = trade.get("outcome", "?")
    price      = float(trade.get("price", 0)) * 100
    side       = trade.get("side", "?").upper()
    slug       = trade.get("eventSlug", trade.get("slug", ""))
    market_url = f"https://polymarket.com/event/{slug}" if slug else "https://polymarket.com"
    ts_raw     = trade.get("timestamp", 0)
    ts         = datetime.fromtimestamp(int(ts_raw), tz=timezone.utc).strftime("%H:%M:%S UTC") if ts_raw else datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
    emoji      = "🐳" if usd_size >= 5000 else "🦈"
    side_emoji = "🟢" if side == "BUY" else "🔴"
    wallet     = trade.get("proxyWallet", "")
    wallet_short = f"{wallet[:6]}...{wallet[-4:]}" if wallet else "?"
    wallet_url   = f"https://polymarket.com/profile/{wallet}" if wallet else "https://polymarket.com"

    return (
        f"{emoji} <b>WHALE ALERT</b> {emoji}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📋 <b>Market:</b> {question}\n"
        f"{side_emoji} <b>Yön:</b> {side} — <b>{outcome}</b>\n"
        f"💵 <b>Tutar:</b> ${usd_size:,.0f}\n"
        f"📈 <b>Fiyat:</b> %{price:.1f}\n"
        f"👛 <b>Cüzdan:</b> <a href='{wallet_url}'>{wallet_short}</a>\n"
        f"🕐 <b>Saat:</b> {ts}\n"
        f"🔗 <a href='{market_url}'>Markete git</a>"
    )


def check_whales() -> None:
    global last_check_time
    log.info("Marketler kontrol ediliyor...")

    now = int(time.time())

    markets = get_top_markets()
    if not markets:
        log.warning("Market listesi boş geldi.")
        return

    condition_ids = [
        m.get("conditionId") or m.get("condition_id", "")
        for m in markets
        if m.get("conditionId") or m.get("condition_id")
    ]

    found = 0
    for i in range(0, len(condition_ids), BATCH_SIZE):
        batch = condition_ids[i:i + BATCH_SIZE]
        trades = get_trades_for_markets(batch)

        for trade in trades:
            # Trade'in timestamp'ini kontrol et — son kontrolden sonra mı?
            ts = int(trade.get("timestamp", 0))
            if ts <= last_check_time:
                continue  # Eski trade, atla

            usd = calc_usd_size(trade)
            if usd >= MIN_TRADE_SIZE_USD:
                msg = format_alert(trade, usd)
                send_telegram(msg)
                log.info(f"Whale: ${usd:,.0f} — {trade.get('title','?')[:60]}")
                found += 1
                time.sleep(0.5)

        time.sleep(0.3)

    # Polymarket timestamp formatında güncelle
    try:
        r = requests.get("https://data-api.polymarket.com/trades", params={"limit": 1}, timeout=10)
        trades = r.json()
        if trades and isinstance(trades, list):
            last_check_time = int(trades[0].get("timestamp", last_check_time))
    except Exception:
        pass
    log.info(f"Kontrol tamamlandı. {found} whale bulundu.")


def main():
    global last_check_time
    log.info("🐳 Polymarket Whale Bot başlatıldı!")
    log.info(f"   Minimum tutar  : ${MIN_TRADE_SIZE_USD}")
    log.info(f"   Kontrol aralığı: {CHECK_INTERVAL_SEC}s")
    log.info(f"   İzlenen market : {MAX_MARKETS}")

    # Polymarket'in timestamp'ini al (time.time() ile uyuşmuyor)
    try:
        r = requests.get("https://data-api.polymarket.com/trades", params={"limit": 1}, timeout=10)
        trades = r.json()
        if trades and isinstance(trades, list):
            last_check_time = int(trades[0].get("timestamp", 0))
            log.info(f"Başlangıç timestamp: {last_check_time}")
        else:
            last_check_time = 0
    except Exception:
        last_check_time = 0
    log.info("Hazır! Yeni trade'ler izleniyor...")

    schedule.every(CHECK_INTERVAL_SEC).seconds.do(check_whales)

    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    main()
