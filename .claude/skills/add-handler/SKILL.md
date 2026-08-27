---
name: add-handler
description: >-
  Scaffold a new Telegram command or message handler in the presentation layer and wire it into the bot. Use this whenever the user wants to add a new bot command, message handler, or user-facing Telegram interaction, even if they don't say "handler" explicitly — e.g. "add a /stats command", "handle photo messages", "respond to a new button".
---

# Add a new Telegram handler

Presentation rules are in AGENTS.md — follow them; this skill is only the procedure.
A handler is a thin controller: no business logic.

1. **Create** `ankibot/presentation/handlers/<name>.py` (e.g. `create_card.py`).

2. **Define the router** and register handlers with decorators:

   ```python
   from aiogram import Router

   router = Router()

   @router.message(...)  # e.g. CommandStart(), Command("stats"), F.photo
   async def handle_<name>(message, ...): ...
   ```

3. **Act as a controller:** build the input DTO from the message, call the interactor
   (`interactor.execute(dto)`), map the result to a Telegram response. If the use case
   doesn't exist yet, add it first via `/add-use-case`.

4. **Register the router** in `ankibot/bootstrap/bot.py`:

   ```python
   from ankibot.presentation.handlers import <name>
   dp.include_router(<name>.router)
   ```

5. **Add a test** for the handler flow where applicable.
