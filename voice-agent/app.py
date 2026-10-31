import asyncio
import json
import logging
import os
import time

import httpx
from livekit import rtc
from livekit.agents import Agent, AgentServer, AgentSession, RunContext, TurnHandlingOptions, function_tool
from livekit.plugins import deepgram, openai

API_URL = os.getenv("COMMERCE_API_URL", "http://api:8000")
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper(), format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("harizon.voice")


class HarizonAgent(Agent):
    def __init__(self, assertion: str | None):
        self.assertion = assertion
        super().__init__(instructions=(
            "You are HarizonAI, the concise and warm shopping assistant for HARIZON, a premium Indian electronics store. "
            "Help shoppers discover products and explain product specifications, delivery, returns, and warranty. "
            "Product, catalog, shipping, return, and warranty information is public and may be answered without sign-in. "
            "Use tools for factual answers; do not invent stock, delivery dates, discounts, or order status. "
            "Any order question is private: always call lookup_order_details for an order status request, including when a numeric order number is supplied or mentioned earlier in this conversation. The tool checks ownership. If authorization is absent or expired, ask the shopper to sign in on the website and reconnect voice; never reveal order information. "
            "For an authenticated customer, use their six-digit order number when supplied. If not supplied, use the requested date if they gave one; otherwise ask for an order number or order date. Convert dates into YYYY-MM-DD when possible, and preserve dates such as 26-10/2026 for server-side normalization. Repeat a number in digit groups so it is easy to remember. Use only the order returned by the ownership-checked tool, and do not invent missing order details. "
            "Keep order-status answers to at most two short sentences, then stop speaking. Give the order number, status, and payment status; include date, total, or items only when asked. "
            "Do not create a support ticket in voice. If a shopper wants a human, direct them to the website's support ticket button, which asks for confirmation. "
            "Never ask for passwords, payment card data, or full addresses. Ask one short follow-up when the request is unclear."
        ))

    @function_tool
    async def search_catalog(self, context: RunContext, query: str) -> str:
        """Find store products by name, category, brand, or use case."""
        started = time.monotonic()
        logger.info("tool.started name=search_catalog")
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{API_URL}/api/products", params={"q": query})
                response.raise_for_status()
                products = response.json()[:5]
            logger.info("tool.completed name=search_catalog result_count=%d duration_ms=%d", len(products), int((time.monotonic() - started) * 1000))
            if not products:
                return "No matching products found. Ask what category or feature matters to the shopper."
            return "\n".join(f"{p['name']} — ₹{int(p['price']):,}; {p['tagline']}; specs: {p['specs']}" for p in products)
        except Exception as exc:
            logger.error("tool.failed name=search_catalog error_type=%s", type(exc).__name__)
            raise

    @function_tool
    async def explain_policy(self, context: RunContext, topic: str) -> str:
        """Answer store questions about delivery, returns, or warranty."""
        logger.info("tool.started name=explain_policy")
        normalized = topic.lower()
        if "return" in normalized or "refund" in normalized or "exchange" in normalized:
            answer = "Unused products may be returned within 7 days of delivery in their original packaging. Contact support with your order reference to start a return."
        elif "warranty" in normalized:
            answer = "Products include a 1-year limited manufacturer warranty unless the product page says otherwise."
        else:
            answer = "Orders over ₹5,000 ship free. Standard delivery usually takes 3–6 business days across India. Tracking is sent after dispatch."
        logger.info("tool.completed name=explain_policy")
        return answer

    @function_tool
    async def lookup_order_details(self, context: RunContext, order_reference: str = "", order_date: str = "") -> str:
        """Find a specific order/date belonging only to this verified customer; ask for a reference or date if unclear."""
        started = time.monotonic()
        if not self.assertion:
            logger.info("tool.completed name=lookup_order_details outcome=authentication_required")
            return "Order information is private. Please sign in on the website and reconnect voice, then I can help with your order."
        params = {}
        if order_reference.strip():
            params["order_reference"] = order_reference.strip()
        if order_date.strip():
            params["order_date"] = order_date.strip()
        if not params:
            logger.info("tool.completed name=lookup_order_details outcome=clarification_needed")
            return "Which order reference or order date should I check?"

        logger.info("tool.started name=lookup_order_details")
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{API_URL}/api/voice/orders", params=params,
                                            headers={"X-Voice-Assertion": self.assertion})
                if response.status_code == 401:
                    logger.info("tool.completed name=lookup_order_details outcome=authorization_expired")
                    return "Your sign-in authorization expired. Please sign in again and reconnect voice before I check your order."
                if response.status_code == 422:
                    logger.info("tool.completed name=lookup_order_details outcome=invalid_reference_or_date")
                    return "I couldn't read that order reference or date. Please repeat the order reference or give me the date in day, month, and year."
                response.raise_for_status()
                data = response.json()
            logger.info("tool.completed name=lookup_order_details found=%s needs_clarification=%s duration_ms=%d",
                        bool(data.get("found")), bool(data.get("needs_clarification")),
                        int((time.monotonic() - started) * 1000))
            if data.get("needs_clarification"):
                candidates = data.get("orders", [])
                if candidates:
                    options = "; ".join(f"ending {row['order_reference']} from {row['order_date']}" for row in candidates)
                    return f"I found a few orders in your account: {options}. Which one do you mean?"
                return "Which order reference or order date should I check?"
            if not data.get("found"):
                return data.get("message", "I couldn't find an order with those details in your account.")
            order = data["order"]
            items = ", ".join(f"{item['quantity']} {item['product_name']}" for item in order["items"])
            return (f"Your order ending {order['order_reference']}, placed on {order['order_date']}, is {order['status']}. "
                    f"Payment is {order['payment_status']}. Total: {order['currency']} {order['total']:.2f}. "
                    f"Items: {items or 'no item details available'}.")
        except httpx.TimeoutException:
            logger.warning("tool.failed name=lookup_order_details error_type=timeout")
            return "I couldn't reach the order service just now. Please try again in a moment, or check your orders on the website."
        except httpx.RequestError as exc:
            logger.warning("tool.failed name=lookup_order_details error_type=%s", type(exc).__name__)
            return "I couldn't reach the order service just now. Please try again in a moment, or check your orders on the website."
        except httpx.HTTPStatusError as exc:
            logger.error("tool.failed name=lookup_order_details http_status=%d", exc.response.status_code)
            return "I couldn't retrieve your order right now. Please try again shortly or check your account on the website."
        except Exception as exc:
            logger.error("tool.failed name=lookup_order_details error_type=%s", type(exc).__name__)
            return "I couldn't retrieve your order right now. Please try again shortly or check your account on the website."


server = AgentServer()


@server.rtc_session(agent_name="harizon-shop-assistant")
async def entry(ctx):
    started = time.monotonic()
    room_name = ctx.room.name
    logger.info("session.connecting room=%s", room_name)
    await ctx.connect()
    logger.info("session.connected room=%s", room_name)
    job_metadata = json.loads(ctx.job.metadata or "{}")
    assertion = job_metadata.get("assertion")
    logger.info("session.identity room=%s customer_authenticated=%s", room_name, bool(assertion))
    session = AgentSession(
        stt=deepgram.STTv2(model="flux-general-en"),
        llm=openai.responses.LLM(model=MODEL),
        tts=openai.TTS(
            model=os.getenv("OPENAI_TTS_MODEL", "gpt-4o-mini-tts"),
            voice=os.getenv("OPENAI_TTS_VOICE", "ash"),
            instructions="Speak warmly and clearly, at a conversational pace, in English (India).",
        ),
        turn_handling=TurnHandlingOptions(
            turn_detection="stt",
            interruption={
                "mode": "vad",
                "min_duration": 0.7,
                "min_words": 1,
                "false_interruption_timeout": 2.0,
                "resume_false_interruption": True,
            },
        ),
    )

    @ctx.room.on("data_received")
    def on_control_packet(packet: rtc.DataPacket):
        # Only accept the narrow stop command on its dedicated topic. Do not log packet contents.
        if packet.topic != "harizon-control" or not packet.participant:
            return
        try:
            command = json.loads(packet.data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return
        if command.get("action") != "stop_reply":
            return

        async def interrupt_reply():
            logger.info("voice.stop_requested room=%s", room_name)
            try:
                await session.interrupt(force=True)
                logger.info("voice.reply_stopped room=%s", room_name)
            except RuntimeError:
                # No active reply, or the session is already shutting down.
                logger.info("voice.stop_no_active_reply room=%s", room_name)

        import asyncio
        asyncio.create_task(interrupt_reply())

    @session.on("user_input_transcribed")
    def on_user_input_transcribed(event):
        # Deliberately log metadata only; never log transcript text.
        logger.info("turn.transcribed room=%s final=%s", room_name, bool(getattr(event, "is_final", False)))

    @session.on("agent_state_changed")
    def on_agent_state_changed(event):
        logger.info("agent.state room=%s state=%s", room_name, getattr(event, "new_state", "unknown"))

    @session.on("user_interruption_detected")
    def on_user_interruption_detected(event):
        probability = getattr(event, "probability", None)
        logger.info("voice.interruption.detected room=%s probability=%s", room_name,
                    f"{probability:.2f}" if isinstance(probability, (int, float)) else "unavailable")

    @session.on("agent_false_interruption")
    def on_agent_false_interruption(*_args):
        logger.info("voice.interruption.false_resumed room=%s", room_name)

    @session.on("user_transcription_timeout")
    def on_transcription_timeout(_event):
        logger.warning("turn.transcription_timeout room=%s", room_name)

    @session.on("close")
    def on_session_close(*_args):
        logger.info("session.closed room=%s", room_name)

    # Do not inherit LiveKit Cloud's room-level recording flag; audio, transcripts,
    # traces, and session data stay unrecorded for this customer support flow.
    await session.start(room=ctx.room, agent=HarizonAgent(assertion), record=False)
    logger.info("session.ready room=%s setup_duration_ms=%d stt=deepgram-flux llm=openai-responses tts=openai", room_name, int((time.monotonic() - started) * 1000))
    await session.say("Hi, I’m HarizonAI. I can help you find the right product or answer a question about our store.")


if __name__ == "__main__":
    from livekit.agents import cli
    cli.run_app(server)
