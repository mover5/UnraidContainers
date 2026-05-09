from models import GlobalSettings, Route


MARKER = "# managed-by-ui — edits to this file will be overwritten"


def render(g: GlobalSettings, routes: list[Route]) -> str:
    lines: list[str] = [
        MARKER,
        "# Use the web UI on port 9999 to make changes.",
        "",
        "{",
        f"\tacme_dns {g.dns_provider} " "{env." f"{g.dns_token_env}" "}",
    ]
    if g.acme_email:
        lines.append(f"\temail {g.acme_email}")
    lines.append("\tadmin 127.0.0.1:2019")
    lines.append("\tlog {")
    lines.append("\t\toutput file /var/log/caddy/caddy.log")
    lines.append("\t\tformat console")
    lines.append("\t}")
    lines.append("}")
    lines.append("")

    for r in routes:
        if not r.enabled:
            lines.append(f"# DISABLED: {r.subdomain} -> {r.upstream}")
            lines.append("")
            continue
        if r.description:
            lines.append(f"# {r.description}")
        lines.append(f"{r.subdomain} {{")
        lines.append(f"\treverse_proxy {r.upstream}")
        if r.extra_directives.strip():
            for raw in r.extra_directives.strip().splitlines():
                lines.append(f"\t{raw}")
        lines.append("}")
        lines.append("")

    return "\n".join(lines)
