"""Turn a URL or domain typed by a judge into a host for the Sybil graph lookup.

Nothing here touches the network: the host is only matched against the imported sample.
"""

import ipaddress
import re
from urllib.parse import urlsplit

# Hosting platforms where each subdomain belongs to a different owner. A seller's subdomain
# never inherits the platform's own trust.
SUBDOMAIN_PLATFORMS = (
    "myshopify.com",
    "blogspot.com",
    "wordpress.com",
    "wixsite.com",
    "weebly.com",
    "square.site",
    "bigcartel.com",
    "gumroad.com",
    "tumblr.com",
    "substack.com",
    "github.io",
    "gitlab.io",
    "netlify.app",
    "vercel.app",
    "pages.dev",
    "web.app",
    "firebaseapp.com",
    "herokuapp.com",
    "webflow.io",
    "carrd.co",
)
# Marketplaces whose sellers live under a path of the platform's own domain.
PATH_SELLERS = {"etsy.com": ("shop",), "ebay.com": ("str", "usr")}

_LABEL = re.compile(r"^(?!-)[a-z0-9-]{1,63}(?<!-)$")


def parse_host(raw: str) -> tuple[str, tuple[str, ...]]:
    """Return (lower-case ASCII host, path segments). Raises ValueError on anything else."""
    text = raw.strip()
    if "://" not in text:
        text = "https://" + text
    try:
        parts = urlsplit(text)
        host = (parts.hostname or "").rstrip(".")
    except ValueError as error:
        raise ValueError("Enter a website address such as example.com") from error
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValueError("Enter a website domain, not an IP address")
    try:
        host = host.encode("idna").decode("ascii")
    except UnicodeError as error:
        raise ValueError("Enter a website address such as example.com") from error
    labels = host.split(".")
    if len(labels) < 2 or len(host) > 253 or not all(_LABEL.match(v) for v in labels):
        raise ValueError("Enter a website address such as example.com")
    return host, tuple(p for p in parts.path.split("/") if p)


def candidates(host: str) -> tuple[str, ...]:
    """The host, then each parent with at least two labels: shop.example.co.uk ->
    shop.example.co.uk, example.co.uk, co.uk. The longest one in the sample wins."""
    labels = host.split(".")
    return tuple(".".join(labels[i:]) for i in range(len(labels) - 1))


def shared_platform(host: str, path: tuple[str, ...], matched: str | None) -> str | None:
    """The platform name when the query is one seller on a shared platform and the match
    would be the platform's own domain (or nothing)."""
    for platform, prefixes in PATH_SELLERS.items():
        on_platform = host == platform or host == "www." + platform
        if on_platform and len(path) >= 2 and path[0].lower() in prefixes:
            return platform
    site = host.removeprefix("www.")
    for platform in SUBDOMAIN_PLATFORMS:
        if site.endswith("." + platform) and matched in (None, platform):
            return platform
    return None
