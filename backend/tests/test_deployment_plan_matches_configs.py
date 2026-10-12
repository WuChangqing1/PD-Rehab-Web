"""The deployment plan must not drift from the configs it describes.

WHY THIS EXISTS
===============
`docs/server_deployment_plan.md` inlines a copy of `deploy/nginx/pd-rehab.conf` so
a reader can see the config without opening another file. The copy had stopped
matching the file. What it was missing was `location = /index.html` and its
`Cache-Control: no-cache, must-revalidate` header -- the fix for a problem the real
file's own comment says a colleague hit twice, where a redeploy leaves browsers
holding the old entry document and loading old hashed chunks with no visible
change and no error.

Anyone rebuilding the server from the plan would have reinstalled that problem.
Two copies of one config will always diverge; the copies that matter are the ones
nobody diffs.

The plan also documented only the port-18085 entry. The sub-path deployment -- the
URL that is actually shared, and the only entry where the browser permits camera
access because it is a secure context -- appeared zero times: not
`pd-rehab-locations.conf`, not `dist-under-path`, not `ccqspace.site/pd-rehab`.
Following the steps as written would have produced a working server that did not
serve the address people use.

These tests read files, not behaviour. They catch drift in the two places it had
already happened.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / "docs" / "server_deployment_plan.md"
NGINX_CONF = ROOT / "deploy" / "nginx" / "pd-rehab.conf"
NGINX_SNIPPET = ROOT / "deploy" / "nginx" / "pd-rehab-locations.conf"


def _plan_text() -> str:
    return PLAN.read_text(encoding="utf8")


def _inlined_nginx() -> str:
    match = re.search(r"```nginx\n([\s\S]*?)```", _plan_text())
    assert match, "the plan should still show the nginx config inline"
    return match.group(1)


def _directives(text: str) -> set[str]:
    """Config directives, ignoring comments and whitespace.

    Only directives are compared: the plan's copy is allowed to carry fewer
    explanatory comments than the file, but it must not carry fewer rules.
    """
    return {
        re.sub(r"\s+", " ", m.group(1)).strip()
        for m in re.finditer(
            r"^\s*(location[^{]*|listen\s+[^;]+|root\s+[^;]+|alias\s+[^;]+"
            r"|proxy_pass\s+[^;]+|add_header[^;]+|try_files\s+[^;]+|index\s+[^;]+);?",
            text,
            re.M,
        )
    }


def test_the_inlined_nginx_copy_contains_every_directive_of_the_real_file():
    real = _directives(NGINX_CONF.read_text(encoding="utf8"))
    inlined = _directives(_inlined_nginx())

    missing = sorted(real - inlined)
    assert not missing, (
        "the plan's inline copy of pd-rehab.conf is missing directives that the "
        "installed file has, so a reader rebuilding from the document would get a "
        "different nginx. Missing:\n  " + "\n  ".join(missing)
    )


def test_the_inlined_copy_has_not_invented_directives():
    real = _directives(NGINX_CONF.read_text(encoding="utf8"))
    inlined = _directives(_inlined_nginx())

    extra = sorted(inlined - real)
    assert not extra, (
        "the plan shows directives the installed file does not have, which would "
        "mislead a reader into thinking they are in effect:\n  " + "\n  ".join(extra)
    )


def test_the_entry_document_cache_header_is_documented():
    """The specific rule whose absence caused a twice-reported stale-cache bug."""
    inlined = _inlined_nginx()
    assert "location = /index.html" in inlined, (
        "without this rule nginx sends only ETag/Last-Modified, browsers apply "
        "heuristic caching, and a redeploy leaves users on the old entry document"
    )
    assert "no-cache, must-revalidate" in inlined


def test_the_plan_documents_both_deployment_entries():
    """The sub-path entry is the shared URL and the only one that allows a camera."""
    text = _plan_text()
    for needle in ("pd-rehab-locations.conf", "dist-under-path", "ccqspace.site/pd-rehab"):
        assert needle in text, (
            f"the plan does not mention {needle!r}. The port-18085 entry is served "
            "over plain HTTP and is not a secure context, so it cannot use the "
            "camera; the sub-path entry is what users are given."
        )


def test_both_build_outputs_are_documented_with_their_base():
    text = _plan_text()
    assert "VITE_BASE=/" in text
    assert "VITE_BASE=/pd-rehab/" in text
    # The two directories must be named, or the build step is ambiguous.
    assert "/var/www/pd-rehab/dist" in text
    assert "dist-under-path" in text


def test_the_snippet_file_exists_and_carries_the_api_proxy():
    """The plan installs this file; it must be real and must proxy the API."""
    assert NGINX_SNIPPET.is_file()
    snippet = NGINX_SNIPPET.read_text(encoding="utf8")
    assert "location /pd-rehab/api/" in snippet, (
        "the sub-path build calls /pd-rehab/api/... because "
        "API_BASE = BASE_URL + '/api'; without this location those requests fall "
        "through to the SPA fallback and return HTML with status 200"
    )
    assert "proxy_pass" in snippet
