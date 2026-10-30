import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# app.main builds its database at import time; keep that out of /config.
os.environ.setdefault("CONFIG_PATH", tempfile.mkdtemp(prefix="ip-directory-test-"))
