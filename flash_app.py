from flask import Flask, jsonify, request
from flask_cors import CORS
from rss_fetcher import fetch_account

app = Flask(__name__)
CORS(app)  # Allow GitHub Pages (or any origin) to call this API


@app.route("/")
def index():
    return jsonify({
        "status": "ok",
        "usage": "/api/feed?user=<twitter_username>",
        "optional_param": "nitter=<nitter_instance_url>"
    })


@app.route("/api/feed")
def feed():
    username = request.args.get("user", "").strip()
    if not username:
        return jsonify({"error": "Missing required param: ?user=username"}), 400

    nitter_url = request.args.get("nitter", "https://nitter.net").strip()

    data = fetch_account(username, nitter_url)
    return jsonify(data)


if __name__ == "__main__":
    app.run(debug=True)
