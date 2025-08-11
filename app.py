from flask import Flask, request, jsonify
from flask_cors import CORS

import secrets
FLASK_SECRET_KEY = secrets.token_hex(16)
# example output, secret_key = 000d88cd9d90036ebdd237eb6b0db000


from agent import RateLimitedSmartFanSoVAgent
from config import Config

app = Flask(__name__)
#app.config["SECRET_KEY"] = Config.FLASK_SECRET_KEY
app.config['SECRET_KEY'] = FLASK_SECRET_KEY
CORS(app)

agent = RateLimitedSmartFanSoVAgent()

# -------------------------------------------------------------- #
@app.route("/")
def root():
    return {
        "service": "Atomberg SoV analysis (free-tier-optimised)",
        "gemini_remaining": Config.GEMINI_RATE_LIMITER.rpd - Config.GEMINI_RATE_LIMITER._day,
        "tavily_remaining": Config.TAVILY_RATE_LIMITER.rpd - Config.TAVILY_RATE_LIMITER._day,
    }

# -------------------------------------------------------------- #
@app.route("/analyze", methods=["POST"])
def analyze():
    data = request.get_json(silent=True) or {}
    query = data.get("query", "smart fan").strip()

    # global free-tier guards
    if not Config.GEMINI_RATE_LIMITER.can_make_request():
        return jsonify({"error": "Gemini daily quota exhausted"}), 429
    if not Config.TAVILY_RATE_LIMITER.can_make_request():
        return jsonify({"error": "Tavily daily quota exhausted"}), 429

    result = agent.run(query)

    return jsonify({
        "query": query,
        "metrics": result["sov_analysis"],
        "insights": result["insights"],
        "docs_processed": len(result["processed_results"]),
        "exec_time_sec": result["execution_sec"]
    })


if __name__ == "__main__":
    print(" ▶ Starting backend on http://localhost:5000")
    app.run(debug=True, host="0.0.0.0", port=5000)
