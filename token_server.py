import os
import uuid

from flask import Flask, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from livekit import api

load_dotenv()

app = Flask(__name__)

allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://127.0.0.1:5500,http://localhost:5500"
    ).split(",")
    if origin.strip()
]

CORS(
    app,
    resources={r"/*": {"origins": allowed_origins}},
    methods=["GET", "OPTIONS"],
    allow_headers=["Content-Type"]
)

LIVEKIT_URL = os.getenv("LIVEKIT_URL")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET")


@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "ok",
        "message": "Pravee Token Server is running!",
        "endpoint": "/token"
    })


@app.route("/token", methods=["GET"])
def get_token():
    if not LIVEKIT_URL or not LIVEKIT_API_KEY or not LIVEKIT_API_SECRET:
        return jsonify({
            "error": "Missing LiveKit credentials in .env file"
        }), 500

    try:
        room_name = "pravee-" + uuid.uuid4().hex[:10]

        token = (
            api.AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
            .with_identity("Pravee-Web-User")
            .with_name("Pravee")
            .with_grants(
                api.VideoGrants(
                    room_join=True,
                    room=room_name,
                    can_publish=True,
                    can_subscribe=True
                )
            )
            .with_room_config(
                api.RoomConfiguration(
                    agents=[
                        api.RoomAgentDispatch(agent_name="my-agent")
                    ]
                )
            )
            .to_jwt()
        )

        print("Token generated for room:", room_name)

        return jsonify({
            "url": LIVEKIT_URL,
            "token": token
        })

    except Exception as e:
        print("Token Error:", str(e))
        return jsonify({"error": str(e)}), 500


@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "error": "Endpoint not found",
        "available_endpoints": ["/", "/token"]
    }), 404


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8000)),
        debug=False
    )
