#!/usr/bin/env python3
"""Install only a SHA256-pinned release wheel; no index/dependency resolution."""

import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit
from urllib.request import build_opener, HTTPRedirectHandler, Request


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Use a direct wheel URL; redirects are refused")


def install():
    url = os.environ.get("CODEGUARD_CLI_WHEEL_URL", "")
    digest = os.environ.get("CODEGUARD_CLI_SHA256", "")
    parsed = urlsplit(url)
    filename = parsed.path.rsplit("/", 1)[-1]
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment or not re.fullmatch(r"[a-zA-Z0-9_.+-]+\.whl", filename)
            or not filename.startswith("codeguard-") or not re.fullmatch(r"[a-fA-F0-9]{64}", digest)):
        raise ValueError("A direct HTTPS CodeGuard wheel URL and SHA256 digest are required")
    with tempfile.TemporaryDirectory(prefix="codeguard-release-") as temp:
        wheel = Path(temp) / filename
        # Cloudflare refuses Python's default User-Agent with 403, so say what this is.
        request = Request(url, headers={"User-Agent": "CodeGuard-Action-Installer/1"})
        with build_opener(NoRedirect()).open(request, timeout=60) as response:
            raw = response.read(16 * 1024 * 1024 + 1)
        if len(raw) > 16 * 1024 * 1024 or hashlib.sha256(raw).hexdigest() != digest.lower():
            raise ValueError("Release wheel checksum mismatch or size limit exceeded")
        wheel.write_bytes(raw)
        # The gate credential is only consumed by the gate process, never pip.
        env = {k: v for k, v in os.environ.items() if k in ("PATH", "HOME", "SYSTEMROOT", "VIRTUAL_ENV")}
        subprocess.run([sys.executable, "-m", "pip", "install", "--no-index", "--no-deps", "--no-compile",
                        "--disable-pip-version-check", str(wheel)], check=True, env=env,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == "__main__":
    try:
        install()
    except Exception:
        print("CodeGuard release installation failed; check the pinned URL, SHA256 and Python environment", file=sys.stderr)
        sys.exit(2)
