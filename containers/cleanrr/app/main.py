import os
import logging

from flask import Flask, render_template, jsonify, request

from app.config import Config
from app.database import Database
from app.deluge import DelugeClient
from app.scheduler import TorrentScheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

config = Config()
os.makedirs(config.config_path, exist_ok=True)

db = Database(config.config_path)

deluge = DelugeClient(
    config.deluge_host, config.deluge_port, config.deluge_password
)
scheduler = TorrentScheduler(config, db, deluge)

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/torrents")
def get_torrents():
    show_removed = request.args.get("show_removed", "false").lower() == "true"
    if show_removed:
        torrents = db.get_all_torrents()
    else:
        torrents = db.get_active_torrents()
    return jsonify(torrents)


@app.route("/api/settings", methods=["GET"])
def get_settings():
    return jsonify(db.get_settings())


@app.route("/api/settings", methods=["PUT"])
def update_settings():
    data = request.json
    for key, value in data.items():
        db.update_setting(key, value)
    if "seed_time_days" in data:
        db.recalculate_removal_dates(float(data["seed_time_days"]))
    if "check_interval_minutes" in data:
        scheduler.reschedule()
    return jsonify({"status": "ok"})


@app.route("/api/torrents/<torrent_hash>/protect", methods=["POST"])
def protect_torrent(torrent_hash):
    db.set_protected(torrent_hash, True)
    return jsonify({"status": "ok"})


@app.route("/api/torrents/<torrent_hash>/unprotect", methods=["POST"])
def unprotect_torrent(torrent_hash):
    db.set_protected(torrent_hash, False)
    return jsonify({"status": "ok"})


@app.route("/api/torrents/<torrent_hash>", methods=["DELETE"])
def remove_torrent(torrent_hash):
    success = scheduler.remove_torrent_now(torrent_hash)
    if success:
        return jsonify({"status": "ok"})
    return jsonify({"status": "error", "message": "Failed to remove torrent"}), 500


@app.route("/api/status")
def status():
    return jsonify(scheduler.get_status())


@app.route("/api/check", methods=["POST"])
def trigger_check():
    scheduler.check_torrents()
    return jsonify({"status": "ok"})


def start():
    scheduler.start()
    app.run(host="0.0.0.0", port=9494, debug=False)
