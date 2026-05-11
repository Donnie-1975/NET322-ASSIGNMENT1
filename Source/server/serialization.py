"""Content negotiation for the REST API.

Maps the `Accept` header on a request to a serializer for the response.
Supported media types:
    application/json
    application/xml
    application/yaml   (also accepts text/yaml)

Falls back to JSON when no supported type matches.
"""
from __future__ import annotations

from aiohttp import web

import json
import yaml
from xml.etree.ElementTree import Element, SubElement, tostring


def negotiate(request: web.Request) -> str:
    """Return the chosen response media type for `request`."""
    accept = request.headers.get("Accept", "application/json")
    supported = ["application/json", "application/xml", "application/yaml", "text/yaml"]

    for part in accept.split(","):
        media_type = part.split(";")[0].strip().lower()
        if media_type in supported:
            return media_type

    return "application/json"


def serialize(payload, media_type: str) -> tuple[bytes, str]:
    """Serialize `payload` (a dict or list of dicts) into bytes."""
    if media_type in ("application/yaml", "text/yaml"):
        import yaml
        data = yaml.dump(payload, default_flow_style=False, allow_unicode=True).encode("utf-8")
        return data, "application/yaml"

    if media_type == "application/xml":
        from xml.etree.ElementTree import Element, SubElement, tostring
        if isinstance(payload, list):
            root = Element("items")
            for item in payload:
                child = SubElement(root, "item")
                for key, val in item.items():
                    field = SubElement(child, key)
                    field.text = str(val)
        else:
            root = Element("item")
            for key, val in payload.items():
                field = SubElement(root, key)
                field.text = str(val)
        return tostring(root, encoding="utf-8", xml_declaration=True), "application/xml"

    import json
    data = json.dumps(payload, indent=2).encode("utf-8")
    return data, "application/json"
