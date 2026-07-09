# Minimal viable Telegram bridge

Public-safe notes for a Telegram demo bridge.

- Create a bot with BotFather.
- Store `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in ignored local secrets.
- Restrict accepted chat IDs in runtime code.
- Never commit bot tokens or chat IDs.
