from __future__ import annotations

from typing import Any, Dict, Optional

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
    # Pravilo 1: če je aktivna rezervacija, jo nadaljuj
    reservation_state = get_reservation_state(session_id)
    if reservation_state.get("step") is not None:
        return handle_reservation_flow(message, reservation_state)

    # Pravilo 2: če je aktivno povpraševanje, nadaljuj
    inquiry_state = get_inquiry_state(session_id)
    if inquiry_state.get("step"):
        reply = handle_inquiry_flow(message, inquiry_state, session_id)
        if reply:
            return reply

    # Pravilo 3: dogodki (poroka, teambuilding) -> povpraševanje
    if is_event_inquiry(message):
        inquiry_state["details"] = message.strip()
        inquiry_state["step"] = "awaiting_deadline"
        return (
            "Za poroke/teambuilding po navadi ne nudimo klasičnega najema prostora, "
            "lahko pa pripravimo posebno ponudbo hrane ali pogostitve.\n\n"
            "Do kdaj bi to potrebovali? (datum/rok ali 'ni pomembno')"
        )

    # Pravilo 4: produkti -> odgovor + link
    product_key = detect_product_intent(message)
    if product_key:
        reply = get_product_response(product_key)
        return f"{reply}\n\nIzdelke Domačije Kovačnik najdete tukaj: {SHOP_URL}"

    # Pravilo 5: info intent
    info_key = detect_info_intent(message)
    if info_key:
        return get_info_response(info_key)

    # Pravilo 6: če uporabnik išče rezervacijo, začni flow
    if is_reservation_related(message):
        return handle_reservation_flow(message, reservation_state)

    # Pravilo 7: inquiry trigger (catering, ponudba, ...)
    if is_inquiry_trigger(message):
        inquiry_state["details"] = message.strip()
        inquiry_state["step"] = "awaiting_deadline"
        return "Super, zabeležim povpraševanje. Do kdaj bi to potrebovali? (datum/rok ali 'ni pomembno')"

    return "Kako vam lahko pomagam? Lahko pomagam z rezervacijo, informacijami ali izdelki."
