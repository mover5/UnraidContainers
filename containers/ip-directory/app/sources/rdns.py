import logging
from concurrent.futures import ThreadPoolExecutor

import dns.exception
import dns.resolver
import dns.reversename

logger = logging.getLogger(__name__)


def _ptr(ip):
    try:
        answer = dns.resolver.resolve(dns.reversename.from_address(ip), "PTR", lifetime=3)
        return str(answer[0]).rstrip(".")
    except (dns.exception.DNSException, ValueError):
        return ""


def lookup_many(ips):
    """Reverse-DNS a batch of IPs in parallel. Returns {ip: hostname or ''}."""
    with ThreadPoolExecutor(max_workers=16) as pool:
        return dict(zip(ips, pool.map(_ptr, ips)))
