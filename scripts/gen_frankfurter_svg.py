"""Regenerate the Frankfurter signature SVG with the current project metadata.

Extracts the `<svg id="infographic">` block from tmp/frankfurter.html (the design
source) and injects the live VERSION and LICENSE read from pyproject.toml, then
writes the result to .github/assets/charts/svg/frankfurter.svg.

Wired into a pre-commit hook (.githooks/pre-commit) so the committed signature
always reflects the current version and license.

Run manually with:

    python scripts/gen_frankfurter_svg.py
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "tmp" / "frankfurter.html"
OUTPUT = ROOT / ".github" / "assets" / "charts" / "svg" / "frankfurter.svg"
PYPROJECT = ROOT / "pyproject.toml"


def project_meta() -> tuple[str, str]:
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]
    version = str(data["version"])
    license_ = str(data.get("license", "")).replace("-or-later", "").replace("-only", "")
    return version, license_


def extract_svg(html: str) -> str:
    m = re.search(r'<svg id="infographic".*?</svg>', html, re.DOTALL)
    if not m:
        raise SystemExit('Could not find <svg id="infographic"> in the source HTML.')
    return m.group(0)


def inject(svg: str, label: str, value: str) -> str:
    # The value tspan follows the label tspan (e.g. "ERSION </tspan><tspan ...>0.9.1</tspan>").
    pattern = re.compile(
        rf'({label} </tspan>\s*<tspan fill="#64748B" fill-opacity="1\.0" font-size="14\.5">)[^<]*(</tspan>)'
    )
    new_svg, n = pattern.subn(rf"\g<1>{value}\g<2>", svg)
    if n != 1:
        raise SystemExit(f"Expected exactly one {label!r} value tspan, found {n}.")
    return new_svg


def main() -> int:
    if not SOURCE.exists():
        # Design source is local-only (tmp/ is gitignored); skip without failing
        # the commit on machines that don't have it.
        print(f"gen_frankfurter_svg: source {SOURCE} not found, skipping.")
        return 0

    version, license_ = project_meta()
    svg = extract_svg(SOURCE.read_text(encoding="utf-8"))
    # &nbsp; is an HTML entity, undefined in XML/SVG and rejected by GitHub's
    # renderer; use a literal non-breaking space, which is valid XML.
    svg = svg.replace("&nbsp;", " ")
    svg = inject(svg, "ERSION", version)
    svg = inject(svg, "ICENSE", license_)

    if not svg.endswith("\n"):
        svg += "\n"

    previous = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else None
    if svg != previous:
        OUTPUT.write_text(svg, encoding="utf-8")
        print(f"gen_frankfurter_svg: wrote {OUTPUT}  (VERSION {version} · LICENSE {license_})")
    else:
        print(f"gen_frankfurter_svg: up to date  (VERSION {version} · LICENSE {license_})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
