from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
from pymongo import MongoClient
import json

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# -----------------------------
# Database Setup
# -----------------------------
client = MongoClient("mongodb://localhost:27017/")
db = client["meshtastic_messages"]
active = db["active_responses"]
previous = db["previous_responses"]

# -----------------------------
# Page 1 — Search Page
# -----------------------------
@app.route("/")
def search_page():
    return render_template("search.html")

@app.route("/search", methods=["POST"])
def search():
    query = request.form.get("query", "").strip()

    results = list(active.find({
        "$or": [
            {"id": query},
            {"name": {"$regex": query, "$options": "i"}}
        ]
    }))

    for r in results:
        r["_id"] = str(r["_id"])

    return jsonify(results)

@app.route("/select", methods=["POST"])
def select():
    response_id = request.json.get("id")

    selected = active.find_one({"_id": response_id})
    if not selected:
        return jsonify({"error": "Not found"}), 404

    # Move to previous responses
    previous.insert_one(selected)
    active.delete_one({"_id": response_id})

    selected["_id"] = str(selected["_id"])

    # Broadcast to Page 2
    socketio.emit("new_selection", selected)

    return jsonify({"status": "ok"})

# -----------------------------
# Page 2 — Display Page
# -----------------------------
@app.route("/display")
def display_page():
    return render_template("display.html")

# -----------------------------
# Previous Responses Page
# -----------------------------
@app.route("/previous")
def previous_page():
    return render_template("previous.html")

@app.route("/previous/list")
def previous_list():
    results = list(previous.find())
    for r in results:
        r["_id"] = str(r["_id"])
    return jsonify(results)

@app.route("/previous/deselect", methods=["POST"])
def deselect():
    response_id = request.json.get("id")

    item = previous.find_one({"_id": response_id})
    if not item:
        return jsonify({"error": "Not found"}), 404

    # Move back to active queue
    active.insert_one(item)
    previous.delete_one({"_id": response_id})

    return jsonify({"status": "ok"})

# -----------------------------
# Run Server
# -----------------------------
if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=8081)
