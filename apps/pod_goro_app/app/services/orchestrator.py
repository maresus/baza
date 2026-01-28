from __future__ import annotations

from typing import Any, Dict

from app.services.intent_helpers import (
    detect_info_intent,
    detect_product_intent,
    is_inquiry_trigger,
    is_reservation_related,
)


def orchestrate_message(message: str, session_id: str, ctx: Dict[str, Any]) -> str:
    # Import znotraj funkcije, da se izognemo circular importu
    from app.services.chat_router import (
        get_reservation_state,
        get_inquiry_state,
        handle_inquiry_flow,
        is_event_inquiry,
        get_info_response,
        get_product_response,
        SHOP_URL,
    )
    from app.services.reservation_flow import handle_reservation_flow
    normalized = message.strip().lower()
    affirmatives = {"ja", "da", "ok", "seveda", "lahko", "yes", "y"}
    last_bot = ""
    for item in reversed(ctx.get("conversation_history", [])):
        if item.get("role") == "assistant":
            last_bot = item.get("content", "")
            break
    reservation_state = get_reservation_state(session_id)
    if reservation_state.get("step") is not None:
        return handle_reservation_flow(message, reservation_state)

    inquiry_state = get_inquiry_state(session_id)
    if inquiry_state.get("step"):
        reply = handle_inquiry_flow(message, inquiry_state, session_id)
        if reply:
            return reply

    if normalized in affirmatives and last_bot:
        if "naročil" in last_bot.lower() or "rezerviram ali pošljem" in last_bot.lower():
            return f"Tukaj je povezava do izdelkov: {SHOP_URL}"

    if is_event_inquiry(message):
        inquiry_state["details"] = message.strip()
        inquiry_state["step"] = "awaiting_deadline"
        return (
            "Za poroke/teambuilding po navadi ne nudimo klasičnega najema prostora, "
            "lahko pa pripravimo posebno ponudbo hrane ali pogostitve.\n\n"
            "Do kdaj bi to potrebovali? (datum/rok ali 'ni pomembno')"
        )

    product_key = detect_product_intent(message)
    if product_key:
        ctx["last_product_query"] = message
        ctx["last_wine_query"] = None
        ctx["last_info_query"] = None
        ctx["last_menu_query"] = False
        reply = get_product_response(product_key)
        return f"{reply}\n\nIzdelke Kmetije Pod Goro najdete tukaj: {SHOP_URL}"

    info_key = detect_info_intent(message)
    if info_key:
        return get_info_response(info_key)

    if is_reservation_related(message):
        return handle_reservation_flow(message, reservation_state)

    if is_inquiry_trigger(message):
        inquiry_state["details"] = message.strip()
        inquiry_state["step"] = "awaiting_deadline"
        return "Super, zabeležim povpraševanje. Do kdaj bi to potrebovali? (datum/rok ali 'ni pomembno')"

    return "Kako vam lahko pomagam? Lahko pomagam z rezervacijo, informacijami ali izdelki."
