"""REST API for the telemetry server.

Endpoints:
    GET    /sensors                       list registered sensors
    GET    /sensors/{id}/readings         historical readings  (?from=&to=)
    POST   /sensors                       register a new sensor
    DELETE /sensors/{id}                  remove a sensor

Content negotiation:
    Server-driven via the `Accept` header. Supported media types:
      application/json, application/xml, application/yaml.
    Delegates to server.serialization.

Sessions:
    A cookie identifies the client session — set on first response, read
    on subsequent requests.
"""
from __future__ import annotations

from aiohttp import web

from server.serialization import negotiate, serialize


async def list_sensors(request: web.Request) -> web.Response:
    """GET /sensors — list all registered sensors."""
    from server import instance
    sensors = await instance.list_sensors()
    media_type = negotiate(request)
    body, content_type = serialize(list(sensors), media_type)
    return web.Response(body=body, content_type=content_type)


async def get_readings(request: web.Request) -> web.Response:
    """GET /sensors/{id}/readings — historical readings for a sensor."""
    from server import instance
    sensor_id = request.match_info["id"]
    from_ts = request.rel_url.query.get("from")
    to_ts   = request.rel_url.query.get("to")
    readings = await instance.get_readings(
        sensor_id,
        from_ts=float(from_ts) if from_ts else None,
        to_ts=float(to_ts)   if to_ts   else None,
    )
    media_type = negotiate(request)
    body, content_type = serialize(list(readings), media_type)
    return web.Response(body=body, content_type=content_type)


async def register_sensor(request: web.Request) -> web.Response:
    """POST /sensors — register a new sensor."""
    from server import instance
    data = await request.json()
    sensor = {
        "sensor_id":        data["sensor_id"],
        "type":             data["type"],
        "interval_seconds": data.get("interval_seconds", 10),
        "location":         data.get("location", ""),
    }
    await instance.add_sensor(sensor)
    raise web.HTTPCreated(
        headers={"Location": f"/sensors/{sensor['sensor_id']}"}
    )


async def delete_sensor(request: web.Request) -> web.Response:
    """DELETE /sensors/{id} — remove a sensor."""
    from server import instance
    sensor_id = request.match_info["id"]
    await instance.remove_sensor(sensor_id)
    raise web.HTTPNoContent()


@web.middleware
async def session_cookie_middleware(request: web.Request, handler):
    """Set/read the session cookie on every request."""
    import uuid
    session_id = request.cookies.get("session_id")
    new_session = session_id is None
    if new_session:
        session_id = str(uuid.uuid4())
    request["session_id"] = session_id
    response = await handler(request)
    if new_session:
        response.set_cookie("session_id", session_id, httponly=True)
    return response


def build_app() -> web.Application:
    """Construct and return the aiohttp Application for the REST API."""
    app = web.Application(middlewares=[session_cookie_middleware])
    app.router.add_get("/sensors", list_sensors)
    app.router.add_get("/sensors/{id}/readings", get_readings)
    app.router.add_post("/sensors", register_sensor)
    app.router.add_delete("/sensors/{id}", delete_sensor)
    return app
