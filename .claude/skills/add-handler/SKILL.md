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
   async def <name>_cmd_handler(message, ...): ...
   ```

3. **Act as a controller:** build the input DTO from the message, call the interactor
   (`interactor.execute(dto)`), map the result to a Telegram response. If the use case
   doesn't exist yet, add it first via `/add-use-case`.

4. **Take dependencies by type**, annotated `FromDishka[...]`:

   ```python
   from dishka import FromDishka

   from ankibot.presentation.identity import TelegramUserId

   @router.message(Command("stats"))
   async def stats_cmd_handler(
       message: Message,
       read_stats: FromDishka[ReadStats],
       user_id: FromDishka[TelegramUserId],
   ) -> None: ...
   ```

   `message`, `state: FSMContext` and `callback_data` stay aiogram's own arguments. The
   interactor must already be listed in `InteractorProvider` (`/add-use-case` step 9).

5. **Register the router** in `ankibot/bootstrap/bot.py`, inside `create_dispatcher` and
   **above** the `setup_dishka(...)` / `inject_router(dp)` pair at the end:

   ```python
   from ankibot.presentation.handlers import <name>
   dp.include_router(<name>.router)
   ```

   Order matters for routing too: a catch-all message handler goes after every
   command-specific router.

6. **Add a test** through the dispatcher — see Testing in AGENTS.md.
