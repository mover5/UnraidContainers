import os
import threading

from backup.scheduler import scheduler_loop
from backup.web import create_app


def main():
    t = threading.Thread(target=scheduler_loop, daemon=True, name="scheduler")
    t.start()

    port = int(os.environ.get("WEB_PORT", 8008))
    app = create_app()
    app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    main()
