import logging
from typing import Optional, List, Dict, Any
import httpx

logger = logging.getLogger("whatsapp_service")


class WhatsAppService:
    """
    Handles communication with Meta WhatsApp Cloud API (Graph API).
    Each tenant has their own Phone Number ID and System User Access Token.
    """

    GRAPH_API_VERSION = "v19.0"

    @classmethod
    def get_api_url(cls, phone_number_id: str) -> str:
        return f"https://graph.facebook.com/{cls.GRAPH_API_VERSION}/{phone_number_id}/messages"

    @classmethod
    async def send_text_message(
        cls,
        phone_number_id: str,
        access_token: str,
        recipient_phone: str,
        text: str,
    ) -> bool:
        """Sends a plain text WhatsApp message."""
        if not phone_number_id or not access_token:
            logger.warning("WhatsApp credentials not configured; skipping dispatch.")
            return False

        url = cls.get_api_url(phone_number_id)
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient_phone.replace("+", "").strip(),
            "type": "text",
            "text": {"preview_url": False, "body": text},
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(url, headers=headers, json=payload)
                if res.status_code in (200, 201):
                    return True
                logger.error(f"WhatsApp API Error {res.status_code}: {res.text}")
                return False
        except Exception as e:
            logger.error(f"Exception sending WhatsApp message: {e}")
            return False

    @classmethod
    async def send_interactive_buttons(
        cls,
        phone_number_id: str,
        access_token: str,
        recipient_phone: str,
        body_text: str,
        buttons: List[Dict[str, str]],  # [{"id": "delivery", "title": "Delivery"}]
    ) -> bool:
        """Sends WhatsApp interactive quick reply buttons (max 3 buttons)."""
        if not phone_number_id or not access_token:
            return False

        url = cls.get_api_url(phone_number_id)
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        btn_elements = [
            {
                "type": "reply",
                "reply": {"id": b["id"], "title": b["title"][:20]},
            }
            for b in buttons[:3]
        ]

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient_phone.replace("+", "").strip(),
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": body_text},
                "action": {"buttons": btn_elements},
            },
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(url, headers=headers, json=payload)
                return res.status_code in (200, 201)
        except Exception as e:
            logger.error(f"Exception sending interactive buttons: {e}")
            return False
