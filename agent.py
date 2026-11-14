
import asyncio
import json
import websockets
from dotenv import load_dotenv

from livekit import agents
from livekit.agents import (
    AgentServer,
    AgentSession,
    Agent,
    RunContext,
    function_tool,
)
from livekit.plugins import google

load_dotenv(".env")


# ==========================================
# WEBSOCKET BRIDGE FOR THE ROBOT UI
# ==========================================

clients = set()
bridge_started = False
bridge_server = None


async def _handler(ws):
    clients.add(ws)
    print("✅ Robot UI connected to Pravee")

    try:
        async for message in ws:
            try:
                data = json.loads(message)

                # Browser chat message received
                if data.get("type") == "text":
                    print("💬 UI message:", data.get("message", ""))

            except json.JSONDecodeError:
                print("⚠️ Invalid WebSocket message")

    except websockets.exceptions.ConnectionClosed:
        pass

    finally:
        clients.discard(ws)
        print("ℹ️ Robot UI disconnected")


def send_ui(msg: dict):
    if clients:
        websockets.broadcast(clients, json.dumps(msg))


# ==========================================
# PERSONAL AI ASSISTANT: PRAVEE
# ==========================================

class Assistant(Agent):

    def __init__(self):
        super().__init__(
            instructions="""
You are Pravee, the user's personal AI assistant.
Your name is always Pravee. Never call yourself Vikki.
Introduce yourself as Pravee.

Be friendly, helpful, and concise.
Speak naturally and answer the user's actual questions.
Help with studies, coding, projects, and everyday tasks.

When the user says goodbye or asks to stop,
say a short goodbye and call the end_conversation tool.
"""
        )

    @function_tool
    async def end_conversation(self, context: RunContext):
        """End the conversation when the user requests it."""
        context.session.shutdown(drain=True)
        return "Say a short goodbye to Pravee."


# ==========================================
# LIVEKIT AGENT SERVER
# ==========================================

server = AgentServer()


@server.rtc_session(agent_name="my-agent")
async def my_agent(ctx: agents.JobContext):

    global bridge_started, bridge_server

    print("✅ PRAVEE AGENT STARTED")

    # Start WebSocket bridge once
    if not bridge_started:
        bridge_server = await websockets.serve(
            _handler,
            "localhost",
            8765
        )

        bridge_started = True
        print("✅ UI WebSocket bridge started on port 8765")

    try:

        session = AgentSession(
            llm=google.realtime.RealtimeModel(
                model="gemini-3.8-live",
                voice="Puck",
                temperature=0.8,
            )
        )

        # ==================================
        # AGENT STATE EVENTS
        # ==================================

        @session.on("agent_state_changed")
        def on_state(ev):

            state = str(ev.new_state)

            print("🤖 Agent state:", state)

            send_ui({
                "type": "state",
                "state": state,
            })

            send_ui({
                "type": "speaking",
                "value": "speaking" in state.lower(),
            })

        # ==================================
        # CONVERSATION TEXT / SUBTITLES
        # ==================================

        @session.on("conversation_item_added")
        def on_item(ev):

            item = getattr(ev, "item", None)

            if item is None:
                return

            text_content = getattr(item, "text_content", None)
            role = getattr(item, "role", None)

            if not text_content:
                return

            if not role:
                return

            role = str(role).lower()

            print(f"📝 Conversation [{role}]: {text_content}")

            # Send assistant response to robot subtitles
            if role in ("assistant", "agent"):

                send_ui({
                    "type": "text",
                    "role": role,
                    "text": text_content,
                })

            # Send user transcript to robot UI
            elif role == "user":

                send_ui({
                    "type": "text",
                    "role": role,
                    "text": text_content,
                })

        # ==================================
        # SESSION CLOSED
        # ==================================

        @session.on("close")
        def on_close(_ev):

            print("ℹ️ Pravee session closed")

            send_ui({
                "type": "speaking",
                "value": False,
            })

            ctx.shutdown(reason="Pravee conversation ended")

        # ==================================
        # START SESSION
        # ==================================

        await session.start(
            room=ctx.room,
            agent=Assistant(),
        )

        print("✅ SESSION STARTED")

        # ==================================
        # PRAVEE GREETING
        # ==================================

        await session.generate_reply(
            instructions=(
                "Say hello aloud. Introduce yourself as Pravee, "
                "the user's personal AI assistant, and offer your help."
            )
        )

        print("✅ GREETING REQUEST COMPLETED")

    except Exception as exc:

        print(
            f"❌ PRAVEE AGENT ERROR: "
            f"{type(exc).__name__}: {exc}"
        )

        raise


# ==========================================
# START APPLICATION
# ==========================================

if __name__ == "__main__":
    agents.cli.run_app(server)
