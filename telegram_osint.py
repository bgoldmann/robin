"""
Telegram OSINT module for Robin.

Searches public Telegram posts via Telethon (SearchPostsRequest) and optionally
global search in joined chats (SearchGlobalRequest). Returns results in the same
shape as dark web search so they can be merged and filtered.
"""

import asyncio
from typing import List, Dict, Optional

from utils import logger

# Lazy import Telethon so app works without telegram credentials
_telethon_available = False
try:
    from telethon import TelegramClient
    from telethon.tl.functions.channels import SearchPostsRequest
    from telethon.tl.functions.messages import SearchGlobalRequest
    from telethon.tl.types import InputPeerEmpty, InputMessagesFilterEmpty
    _telethon_available = True
except ImportError:
    pass


def is_telegram_configured() -> bool:
    """Return True if Telegram API credentials and enabled flag are set."""
    if not _telethon_available:
        return False
    from config import (
        TELEGRAM_API_ID,
        TELEGRAM_API_HASH,
        TELEGRAM_ENABLED,
    )
    if not TELEGRAM_ENABLED:
        return False
    try:
        api_id = int(TELEGRAM_API_ID) if TELEGRAM_API_ID else 0
    except (TypeError, ValueError):
        return False
    return bool(api_id and TELEGRAM_API_HASH)


def _get_message_text(msg) -> str:
    """Extract plain text from a Telegram message."""
    if not msg or not getattr(msg, "message", None):
        return ""
    return (msg.message or "").strip()


async def _search_public_posts_async(
    client: TelegramClient,
    query: str,
    limit: int = 50,
) -> List[Dict[str, str]]:
    """Search public posts via SearchPostsRequest. Returns list of {title, link, content}."""
    results: List[Dict[str, str]] = []
    try:
        offset_rate = 0
        offset_peer = InputPeerEmpty()
        offset_id = 0
        collected = 0

        while collected < limit:
            batch_limit = min(50, limit - collected)
            r = await client(
                SearchPostsRequest(
                    offset_rate=offset_rate,
                    offset_peer=offset_peer,
                    offset_id=offset_id,
                    limit=batch_limit,
                    query=query.strip() or None,
                )
            )
            messages = getattr(r, "messages", None) or []
            chats = {c.id: c for c in (getattr(r, "chats", None) or [])}

            for msg in messages:
                if collected >= limit:
                    break
                text = _get_message_text(msg)
                if not text:
                    continue
                msg_id = getattr(msg, "id", 0) or 0
                peer = getattr(msg, "peer_id", None)
                channel_id = None
                if peer:
                    channel_id = getattr(peer, "channel_id", None)
                if channel_id is None:
                    continue
                chat = chats.get(channel_id)
                channel_name = getattr(chat, "title", None) or f"channel_{channel_id}"
                link = f"https://t.me/c/{channel_id}/{msg_id}"
                title = f"{channel_name} | {text[:50]}..." if len(text) > 50 else f"{channel_name} | {text}"
                results.append({
                    "title": title,
                    "link": link,
                    "content": text,
                })
                collected += 1

            if not messages:
                break
            # Pagination
            next_rate = getattr(r, "next_rate", None)
            if next_rate is None:
                break
            offset_rate = next_rate
            if messages:
                last = messages[-1]
                offset_id = getattr(last, "id", 0) or offset_id
                offset_peer = getattr(last, "peer_id", offset_peer)

            await asyncio.sleep(0.5)  # Rate limit

    except Exception as e:
        logger.error(f"Telegram SearchPostsRequest error: {e}", exc_info=True)
    return results


async def _search_global_async(
    client: TelegramClient,
    query: str,
    limit: int = 30,
) -> List[Dict[str, str]]:
    """Search in joined chats via SearchGlobalRequest (user-only). Returns list of {title, link, content}."""
    results: List[Dict[str, str]] = []
    try:
        offset_rate = 0
        offset_peer = InputPeerEmpty()
        offset_id = 0
        collected = 0

        while collected < limit:
            batch_limit = min(50, limit - collected)
            r = await client(
                SearchGlobalRequest(
                    q=query.strip(),
                    filter=InputMessagesFilterEmpty(),
                    offset_rate=offset_rate,
                    offset_peer=offset_peer,
                    offset_id=offset_id,
                    limit=batch_limit,
                )
            )
            messages = getattr(r, "messages", None) or []
            chats = {c.id: c for c in (getattr(r, "chats", None) or [])}
            users = {u.id: u for u in (getattr(r, "users", None) or [])}

            for msg in messages:
                if collected >= limit:
                    break
                text = _get_message_text(msg)
                if not text:
                    continue
                msg_id = getattr(msg, "id", 0) or 0
                peer = getattr(msg, "peer_id", None)
                if not peer:
                    continue
                peer_id = getattr(peer, "channel_id", None) or getattr(peer, "chat_id", None) or getattr(peer, "user_id", None)
                if peer_id is None:
                    continue
                name = ""
                if getattr(peer, "channel_id", None) or getattr(peer, "chat_id", None):
                    chat = chats.get(peer_id)
                    name = getattr(chat, "title", None) or f"chat_{peer_id}"
                else:
                    user = users.get(peer_id)
                    name = getattr(user, "username", None) or getattr(user, "first_name", None) or f"user_{peer_id}"
                link = f"telegram://chat/{peer_id}/msg/{msg_id}"
                title = f"{name} | {text[:50]}..." if len(text) > 50 else f"{name} | {text}"
                results.append({
                    "title": title,
                    "link": link,
                    "content": text,
                })
                collected += 1

            if not messages:
                break
            next_rate = getattr(r, "next_rate", None)
            if next_rate is None:
                break
            offset_rate = next_rate
            if messages:
                last = messages[-1]
                offset_id = getattr(last, "id", 0) or offset_id
                offset_peer = getattr(last, "peer_id", offset_peer)

            await asyncio.sleep(0.5)

    except Exception as e:
        logger.error(f"Telegram SearchGlobalRequest error: {e}", exc_info=True)
    return results


async def _get_telegram_results_async(
    query: str,
    limit: int = 50,
    include_global: bool = True,
) -> List[Dict[str, str]]:
    """Async: run Telegram client and return merged public + optional global results."""
    if not _telethon_available:
        logger.debug("Telethon not installed; skipping Telegram OSINT")
        return []
    if not is_telegram_configured():
        logger.debug("Telegram not configured or disabled; skipping Telegram OSINT")
        return []

    from config import TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_SESSION_PATH

    api_id = int(TELEGRAM_API_ID)
    api_hash = TELEGRAM_API_HASH
    session_path = TELEGRAM_SESSION_PATH or "robin_telegram.session"

    seen_links: set = set()
    merged: List[Dict[str, str]] = []

    try:
        client = TelegramClient(session_path, api_id, api_hash)
        await client.connect()
        if not await client.is_user_authorized():
            logger.warning("Telegram session not authorized; run first-time login (e.g. robin telegram-login)")
            await client.disconnect()
            return []

        # Public posts first (SearchPostsRequest)
        public = await _search_public_posts_async(client, query, limit=limit)
        for item in public:
            link = item.get("link")
            if link and link not in seen_links:
                seen_links.add(link)
                merged.append(item)

        # Optionally add global search in joined chats
        if include_global and len(merged) < limit:
            global_limit = min(30, limit - len(merged))
            global_results = await _search_global_async(client, query, limit=global_limit)
            for item in global_results:
                link = item.get("link")
                if link and link not in seen_links:
                    seen_links.add(link)
                    merged.append(item)

        await client.disconnect()
        logger.info(f"Telegram OSINT: {len(merged)} results")
    except Exception as e:
        logger.error(f"Telegram OSINT failed: {e}", exc_info=True)
        return []

    return merged


def get_telegram_results(
    query: str,
    limit: int = 50,
    include_global: bool = True,
) -> List[Dict[str, str]]:
    """
    Synchronous wrapper: search Telegram (public posts + optional joined chats).

    Returns list of dicts with keys: title, link, content.
    Same shape as dark web search results; content is pre-filled so scrape step skips HTTP.
    """
    if not _telethon_available or not is_telegram_configured():
        return []
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                _get_telegram_results_async(query, limit=limit, include_global=include_global)
            )
        finally:
            loop.close()
    except Exception as e:
        logger.error(f"Telegram OSINT sync wrapper failed: {e}", exc_info=True)
        return []
