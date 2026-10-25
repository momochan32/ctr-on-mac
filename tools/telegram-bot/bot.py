#!/usr/bin/env python3
"""CTR-Online on Mac community bot for the Telegram group (Python standard library only).

- Welcomes new members (Indonesian + English) with the download, the README and the rules.
- Anti-spam check: a new member is muted until they press "I'm not a bot"; after
  VERIFY_SECONDS without it they are removed (they can join again).
- Commands: /start /help /download /install /rosetta /nickname /update /bug /rules /credits.
- Announces new GitHub releases of the repository (checked every RELEASE_POLL seconds).
- Replies with the rules when someone asks for game files (no link to any game file is ever given).

Configuration (environment):
  BOT_TOKEN       the token from @BotFather (required; never commit it)
  GROUP_CHAT_ID   the group's id (-100...): where releases are announced. Without it, the first
                  group the bot sees is used and saved in the state file.
  STATE_FILE      where the last announced release and the group id are kept (default: state.json)
  REPO            GitHub repository (default momochan32/ctr-on-mac)

Run: BOT_TOKEN=... python3 bot.py   (long polling: no web server or open port needed)
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

TOKEN = os.environ.get("BOT_TOKEN", "")
API = f"https://api.telegram.org/bot{TOKEN}/"
REPO = os.environ.get("REPO", "momochan32/ctr-on-mac")
STATE_FILE = Path(os.environ.get("STATE_FILE", Path(__file__).with_name("state.json")))
VERIFY_SECONDS = 300
RELEASE_POLL = 600

REPO_URL = f"https://github.com/{REPO}"
DMG_URL = f"{REPO_URL}/releases/latest/download/CTR-Online-on-Mac.dmg"
README_ID = f"{REPO_URL}/blob/main/README.id.md"
README_EN = f"{REPO_URL}/blob/main/README.md"
ISSUES = f"{REPO_URL}/issues"
OCTR_URL = "https://github.com/Ryu7w7/OCTR-NitroFueled-PC"

RULES = (
    "📜 <b>Aturan grup / Group rules</b>\n"
    "1. Saling menghormati. / Be respectful.\n"
    "2. <b>Tidak ada file game</b>: jangan minta atau bagikan file game, PKG, firmware, atau kunci. "
    "Pakai dump milik sendiri yang sah. / <b>No game files</b>: do not ask for or share game files, "
    "PKGs, firmware or keys. Use your own legal dump.\n"
    "3. Bug versi Mac → GitHub Issues, bukan ke proyek asal. / Mac bugs → GitHub Issues, not the "
    "upstream projects.\n"
    "4. Server online milik OCTR (RyuNET): ikuti aturan mereka. / The online server is OCTR's (RyuNET): "
    "follow their rules.\n"
    "5. Tanpa spam atau promosi. / No spam or ads."
)
TEXTS = {
    "help": (
        "🏁 <b>CTR-Online on Mac</b> — port macOS tidak resmi dari OCTR / unofficial macOS port of OCTR\n\n"
        "/download — unduh aplikasi / get the app\n"
        "/install — cara pasang / how to install\n"
        "/rosetta — tentang Rosetta 2 / about Rosetta 2\n"
        "/nickname — tentang nickname / about nicknames\n"
        "/update — cara update / how to update\n"
        "/bug — lapor bug / report a bug\n"
        "/rules — aturan grup / group rules\n"
        "/credits — kredit / credits"
    ),
    "download": (
        f"⬇️ <b>Download</b>: <a href=\"{DMG_URL}\">CTR-Online-on-Mac.dmg</a>\n"
        f"📄 README: <a href=\"{README_ID}\">Bahasa Indonesia</a> · <a href=\"{README_EN}\">English</a>\n\n"
        "Butuh Mac Apple Silicon, Rosetta 2, dan dump game milik sendiri (CUSA13795 v1.21). "
        "Tidak ada file game yang disediakan. / Needs an Apple Silicon Mac, Rosetta 2 and your own game dump."
    ),
    "install": (
        "🛠 <b>Cara pasang / Install</b>\n"
        "1. Unduh DMG (/download), buka, seret <b>CTR-Online on Mac</b> ke <b>Applications</b>.\n"
        "2. Pertama kali: klik kanan aplikasi → <b>Open</b> → <b>Open</b>.\n"
        "3. Pengaturan → Game: pilih folder game yang berisi <code>eboot.bin</code>.\n"
        "4. Tekan <b>Main</b>, isi nickname, tunggu persiapan shader (~2 menit, sekali saja).\n\n"
        "1. Download the DMG, drag the app to Applications. 2. First time: right-click → Open. "
        "3. Settings → Game: choose the folder with eboot.bin. 4. Press Play, choose a nickname."
    ),
    "rosetta": (
        "🧩 <b>Rosetta 2</b>\n"
        "Kode game PS4 adalah kode Intel (x86-64), jadi game berjalan lewat Rosetta 2. Pasang sekali:\n"
        "<code>softwareupdate --install-rosetta --agree-to-license</code>\n\n"
        "⚠️ macOS 28 menghapus Rosetta 2. Tetap di macOS 27 atau lebih lama untuk terus bermain.\n"
        "⚠️ macOS 28 removes Rosetta 2: stay on macOS 27 or older to keep playing."
    ),
    "nickname": (
        "🪪 <b>Nickname</b>\n"
        "Saat pertama menekan Main, launcher meminta nickname (3–16 huruf, angka, _ atau -). "
        "Instalasi pertama yang memakainya secara online akan memilikinya. Bisa diganti di Pengaturan → Online.\n\n"
        "The first Play asks for a nickname (3–16 letters, digits, _ or -); the first installation to use it "
        "online keeps it."
    ),
    "update": (
        "🔄 <b>Update</b>\n"
        "Launcher mengecek versi baru saat dibuka; tekan tombol <b>Update</b> di banner. Save dan pengaturan "
        "tetap aman.\n\nThe launcher checks for new versions at start: press <b>Update</b> on the banner."
    ),
    "bug": (
        f"🐞 <b>Lapor bug / Report a bug</b>: <a href=\"{ISSUES}\">GitHub Issues</a>\n"
        "Sertakan: model Mac, versi macOS, langkah untuk mengulang, dan log (Launcher → Log → Ekspor log).\n"
        "Include: Mac model, macOS version, steps, and the log (Launcher → Log → Export log)."
    ),
    "credits": (
        "🙏 <b>Kredit / Credits</b>\n"
        "Port ini berdiri di atas karya komunitas / This port builds on community work:\n"
        f"• <a href=\"{OCTR_URL}\">OCTR</a> — Ryu7w7 dan kontributor (online RyuNET)\n"
        "• SacredFire — T3CHNOLOG1C · CTR-NitroFueled-PC — GetLostIn\n"
        "• shadPS4 · Mesa KosmicKrisp · tcosi · illusion · TroyWarez · Camiloop · AMD FSR\n"
        "Tidak berafiliasi dengan Activision, Beenox, atau Sony. / Not affiliated with Activision, Beenox or Sony."
    ),
}
COMMANDS = {"start": "help", "help": "help", "download": "download", "install": "install",
            "rosetta": "rosetta", "nickname": "nickname", "update": "update", "bug": "bug",
            "rules": "rules", "credits": "credits", "faq": "help"}
GAME_FILE_REQUEST = re.compile(
    r"(minta|bagi|share|kirim|send|need|butuh|cari|link|download|unduh|where).{0,40}"
    r"\b(pkg|iso|rom|dump|game|eboot|firmware|cusa\d*|update ?1\.21)\b", re.I)


def call(method, **params):
    data = json.dumps(params).encode()
    request = urllib.request.Request(API + method, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=70) as reply:
            return json.loads(reply.read()).get("result")
    except urllib.error.HTTPError as error:
        print(f"{method}: HTTP {error.code} {error.read()[:200]!r}", file=sys.stderr)
    except (urllib.error.URLError, TimeoutError, ValueError) as error:
        print(f"{method}: {error}", file=sys.stderr)
    return None


def send(chat_id, text, reply_to=None, markup=None):
    params = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    if reply_to:
        params["reply_parameters"] = {"message_id": reply_to, "allow_sending_without_reply": True}
    if markup:
        params["reply_markup"] = markup
    return call("sendMessage", **params)


def load_state():
    try:
        return json.loads(STATE_FILE.read_text())
    except (OSError, ValueError):
        return {}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2))


def mention(user):
    name = (user.get("first_name") or user.get("username") or "teman").replace("<", "").replace(">", "")
    return f"<a href=\"tg://user?id={user['id']}\">{name}</a>"


MUTED = {"can_send_messages": False, "can_send_audios": False, "can_send_documents": False,
         "can_send_photos": False, "can_send_videos": False, "can_send_video_notes": False,
         "can_send_voice_notes": False, "can_send_polls": False, "can_send_other_messages": False,
         "can_add_web_page_previews": False}
FREE = {key: True for key in MUTED}


def welcome(chat_id, user, pending):
    if user.get("is_bot"):
        return
    call("restrictChatMember", chat_id=chat_id, user_id=user["id"], permissions=MUTED,
         use_independent_chat_permissions=True)
    text = (f"👋 Selamat datang / Welcome, {mention(user)}!\n\n"
            "Tekan tombol di bawah dalam 5 menit untuk mulai mengobrol. / Press the button below within "
            "5 minutes to start chatting.\n\n" + RULES)
    markup = {"inline_keyboard": [[{"text": "✅ Saya bukan bot / I'm not a bot", "callback_data": f"verify:{user['id']}"}],
                                  [{"text": "⬇️ Download", "url": DMG_URL},
                                   {"text": "📄 README", "url": README_ID}]]}
    message = send(chat_id, text, markup=markup)
    pending[(chat_id, user["id"])] = (time.time() + VERIFY_SECONDS, message and message["message_id"])


def verify(callback, pending):
    data, user = callback.get("data", ""), callback["from"]
    message = callback.get("message") or {}
    chat_id = message.get("chat", {}).get("id")
    if not data.startswith("verify:") or chat_id is None:
        return
    if str(user["id"]) != data.split(":", 1)[1]:
        call("answerCallbackQuery", callback_query_id=callback["id"],
             text="Tombol ini untuk anggota baru tersebut. / This button is for that new member.", show_alert=True)
        return
    call("restrictChatMember", chat_id=chat_id, user_id=user["id"], permissions=FREE,
         use_independent_chat_permissions=True)
    pending.pop((chat_id, user["id"]), None)
    call("answerCallbackQuery", callback_query_id=callback["id"], text="Terverifikasi! / Verified!")
    call("editMessageText", chat_id=chat_id, message_id=message["message_id"], parse_mode="HTML",
         disable_web_page_preview=True,
         text=f"👋 Selamat datang / Welcome, {mention(user)}! Ketik /help untuk panduan. / Type /help.\n\n{RULES}")


def expire(pending):
    now = time.time()
    for (chat_id, user_id), (deadline, message_id) in list(pending.items()):
        if now < deadline:
            continue
        pending.pop((chat_id, user_id))
        # Removed, not banned: a short ban then unban lets them join again.
        call("banChatMember", chat_id=chat_id, user_id=user_id, until_date=int(now) + 60)
        call("unbanChatMember", chat_id=chat_id, user_id=user_id, only_if_banned=True)
        if message_id:
            call("deleteMessage", chat_id=chat_id, message_id=message_id)


def latest_release():
    request = urllib.request.Request(f"https://api.github.com/repos/{REPO}/releases/latest",
                                     headers={"Accept": "application/vnd.github+json",
                                              "User-Agent": "ctr-online-telegram-bot"})
    try:
        with urllib.request.urlopen(request, timeout=20) as reply:
            return json.loads(reply.read())
    except (urllib.error.URLError, TimeoutError, ValueError) as error:
        print(f"GitHub: {error}", file=sys.stderr)
        return None


def announce(state):
    chat_id = os.environ.get("GROUP_CHAT_ID") or state.get("group")
    release = latest_release()
    if not chat_id or not release or not release.get("tag_name"):
        return
    tag = release["tag_name"]
    if state.get("announced") is None:
        state["announced"] = tag  # the first start remembers the current release without posting it
        save_state(state)
        return
    if tag == state["announced"]:
        return
    notes = (release.get("body") or "").split("\n---")[0].strip()[:1200]
    notes = notes.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = (f"🏁 <b>{(release.get('name') or tag).replace('<', '&lt;')}</b>\n\n{notes}\n\n"
            f"⬇️ <a href=\"{DMG_URL}\">Download DMG</a> · <a href=\"{release['html_url']}\">Release</a>\n"
            "App yang sudah terpasang bisa update dari launcher (tombol Update). / Installed apps update from "
            "the launcher (Update button).")
    message = send(chat_id, text)
    if message:
        call("pinChatMessage", chat_id=chat_id, message_id=message["message_id"], disable_notification=True)
        state["announced"] = tag
        save_state(state)


def handle(update, state, pending):
    if "callback_query" in update:
        verify(update["callback_query"], pending)
        return
    message = update.get("message")
    if not message:
        return
    chat = message["chat"]
    if chat["type"] in ("group", "supergroup") and not os.environ.get("GROUP_CHAT_ID") and state.get("group") != chat["id"]:
        state["group"] = chat["id"]
        save_state(state)
        print(f"Group: {chat.get('title')} ({chat['id']})")
    for user in message.get("new_chat_members") or []:
        welcome(chat["id"], user, pending)
    text = message.get("text") or message.get("caption") or ""
    if text.startswith("/"):
        command = text[1:].split()[0].split("@")[0].lower() if len(text) > 1 else ""
        if command in COMMANDS:
            key = COMMANDS[command]
            send(chat["id"], RULES if key == "rules" else TEXTS[key], reply_to=message["message_id"])
        return
    if GAME_FILE_REQUEST.search(text):
        send(chat["id"], "ℹ️ Grup ini tidak membagikan file game. Pakai dump milik sendiri yang sah. / "
             "This group does not share game files: use your own legal dump.\n\n" + RULES,
             reply_to=message["message_id"])


def main():
    if not TOKEN:
        sys.exit("Set BOT_TOKEN (from @BotFather).")
    me = call("getMe")
    if not me:
        sys.exit("The token was refused by Telegram.")
    print(f"Running as @{me['username']}")
    call("setMyCommands", commands=[
        {"command": "help", "description": "Panduan / Help"},
        {"command": "download", "description": "Unduh aplikasi / Download"},
        {"command": "install", "description": "Cara pasang / Install"},
        {"command": "rosetta", "description": "Tentang Rosetta 2"},
        {"command": "nickname", "description": "Tentang nickname"},
        {"command": "update", "description": "Cara update"},
        {"command": "bug", "description": "Lapor bug / Report a bug"},
        {"command": "rules", "description": "Aturan grup / Rules"},
        {"command": "credits", "description": "Kredit / Credits"}])
    state, pending, offset, next_release = load_state(), {}, None, 0.0
    while True:
        updates = call("getUpdates", offset=offset, timeout=50,
                       allowed_updates=["message", "callback_query"]) or []
        for update in updates:
            offset = update["update_id"] + 1
            try:
                handle(update, state, pending)
            except Exception as error:  # one bad update must not stop the bot
                print(f"update {update.get('update_id')}: {error!r}", file=sys.stderr)
        expire(pending)
        if time.time() >= next_release:
            announce(state)
            next_release = time.time() + RELEASE_POLL
        if not updates:
            time.sleep(1)


if __name__ == "__main__":
    main()
