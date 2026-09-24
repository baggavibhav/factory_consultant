"""Render a single-file HTML viewer with the glTF model embedded.

The file works offline: three.js (MIT licence, see vendor/THREE_LICENSE.txt)
and the model are inlined, so it can be opened by double-clicking or emailed.
"""

from __future__ import annotations

import base64
import json
from importlib.resources import files

_PKG = files("fca.viewer")


def _read(name: str) -> str:
    return (_PKG / name).read_text(encoding="utf-8")


def _inline_js(code: str) -> str:
    return code.replace("</script", "<\\/script")


def render_viewer(glb: bytes, facts: dict, labels: list[dict]) -> str:
    data = {
        "glb": base64.b64encode(glb).decode("ascii"),
        "facts": facts,
        "labels": labels,
    }
    html = _read("template.html")
    return (
        html.replace("/*__THREE__*/", _inline_js(_read("vendor/three.min.js")))
        .replace("/*__ORBIT__*/", _inline_js(_read("vendor/OrbitControls.js")))
        .replace("/*__GLTF__*/", _inline_js(_read("vendor/GLTFLoader.js")))
        .replace("/*__DATA__*/null", json.dumps(data, separators=(",", ":")).replace("</", "<\\/"))
    )
