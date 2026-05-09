"""Best-effort Caddyfile importer.

Parses simple `host { reverse_proxy upstream }` blocks plus the global
settings block. Anything more complex falls through silently — the user
can re-add it via the UI's extra_directives field.
"""

import re
import uuid
from models import GlobalSettings, Route


def _strip_comments(text: str) -> str:
    out_lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        out_lines.append(line)
    return "\n".join(out_lines)


def _find_blocks(text: str) -> list[tuple[str, str]]:
    """Return list of (header, body) for each top-level block.

    Header is the text before the opening brace on its line; body is
    the text between matching braces. Brace matching is depth-aware
    so nested blocks (like `log { ... }`) are kept intact.
    """
    blocks: list[tuple[str, str]] = []
    i = 0
    n = len(text)
    while i < n:
        # find opening brace
        brace = text.find("{", i)
        if brace == -1:
            break
        # header is from start-of-line to the brace
        line_start = text.rfind("\n", 0, brace) + 1
        header = text[line_start:brace].strip()
        # find matching close
        depth = 1
        j = brace + 1
        while j < n and depth > 0:
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
            j += 1
        if depth != 0:
            break
        body = text[brace + 1 : j - 1]
        blocks.append((header, body))
        i = j
    return blocks


def parse_caddyfile(content: str) -> tuple[GlobalSettings, list[Route]]:
    g = GlobalSettings()
    routes: list[Route] = []

    text = _strip_comments(content)
    blocks = _find_blocks(text)

    for header, body in blocks:
        if header == "":
            # global block
            m = re.search(r"acme_dns\s+(\S+)\s+\{env\.([^}]+)\}", body)
            if m:
                g.dns_provider = m.group(1)
                g.dns_token_env = m.group(2)
            m = re.search(r"^\s*email\s+(\S+)", body, re.MULTILINE)
            if m:
                g.acme_email = m.group(1)
            continue

        # route block — header should be a hostname (or comma-separated list)
        # take only the first hostname for now; require a dot
        first = header.split(",")[0].strip()
        if "." not in first:
            continue
        if not re.match(r"^[A-Za-z0-9*._-]+$", first):
            continue
        rp = re.search(r"^\s*reverse_proxy\s+(\S+)", body, re.MULTILINE)
        if not rp:
            continue

        # collect extra directives (everything except the reverse_proxy line)
        extras: list[str] = []
        for line in body.splitlines():
            s = line.strip()
            if not s:
                continue
            if s.startswith("reverse_proxy"):
                continue
            extras.append(s)

        routes.append(
            Route(
                id=str(uuid.uuid4()),
                subdomain=first,
                upstream=rp.group(1),
                enabled=True,
                description="",
                extra_directives="\n".join(extras),
            )
        )

    return g, routes
