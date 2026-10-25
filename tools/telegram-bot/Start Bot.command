#!/bin/zsh
# Starts the CTR-Online Telegram bot: asks for the token in a hidden dialog (never stored in a
# file), runs the bot in the background and shows its log.
cd "$(dirname "$0")"
pkill -f "telegram-bot/bot.py" 2>/dev/null
token=$(osascript -e 'text returned of (display dialog "Paste the token from @BotFather:" default answer "" with hidden answer with title "CTR-Online bot")') || exit 1
[[ -z $token ]] && { echo "No token entered."; exit 1; }
BOT_TOKEN="$token" nohup /usr/bin/python3 -u "$PWD/bot.py" > bot.log 2>&1 &
sleep 5
cat bot.log
echo
echo "The bot keeps running in the background. Close this window when you like."
