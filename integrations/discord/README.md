# Discord Integration

This folder contains Trading Engine's current direct Discord integration. It is legacy transport and will be replaced by discord-hub HTTP calls in a separate migration.

## Files

- `client.py` - thin wrappers for send/edit/file + bot setup
- `templates.py` - message formatting and parsing helpers

## Usage

```python
from integrations.discord.client import bot, print_discord, send_file_discord

await print_discord("Hello from Trading Engine")
await send_file_discord("storage/images/spy_chart.png")
```

## Templates

Message formatting helpers live in `templates.py`. If you want to change how a
message looks, update the template there instead of editing call sites.
