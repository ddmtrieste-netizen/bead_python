"""Loopback-only browser display for headless camera applications."""

from __future__ import annotations

import argparse
import html
import json
import threading
from collections import deque
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

__all__ = [
    "Action",
    "RangeControl",
    "RemoteEvent",
    "RemoteView",
    "add_display_arguments",
    "compose_grid",
]

LOOPBACK_HOST = "127.0.0.1"
DEFAULT_REMOTE_PORT = 8765


def _port_number(value: str) -> int:
    port = int(value)
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be between 1 and 65535")
    return port


def add_display_arguments(parser: argparse.ArgumentParser) -> None:
    """Add the common local/remote display options to a CLI parser."""
    parser.add_argument(
        "--display",
        choices=("local", "remote"),
        default="local",
        help="Show OpenCV windows locally or serve a browser view over SSH.",
    )
    parser.add_argument(
        "--remote-port",
        type=_port_number,
        default=DEFAULT_REMOTE_PORT,
        help=f"Loopback HTTP port used by --display remote (default: {DEFAULT_REMOTE_PORT}).",
    )


@dataclass(frozen=True, slots=True)
class RangeControl:
    """A numeric slider rendered in the remote browser."""

    name: str
    label: str
    minimum: int | float
    maximum: int | float
    step: int | float
    value: int | float

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("control name cannot be empty")
        if self.minimum > self.maximum:
            raise ValueError(f"{self.name} minimum cannot exceed maximum")
        if self.step <= 0:
            raise ValueError(f"{self.name} step must be positive")
        if not self.minimum <= self.value <= self.maximum:
            raise ValueError(f"{self.name} initial value is outside its range")

    def normalized(self, value: Any) -> int | float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{self.name} must be numeric")
        if not self.minimum <= value <= self.maximum:
            raise ValueError(f"{self.name} is outside its range")
        if all(
            isinstance(item, int)
            for item in (self.minimum, self.maximum, self.step, self.value)
        ):
            return int(round(value))
        return float(value)

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "label": self.label,
            "min": self.minimum,
            "max": self.maximum,
            "step": self.step,
            "value": self.value,
        }


@dataclass(frozen=True, slots=True)
class Action:
    """A browser button and its optional keyboard shortcuts."""

    name: str
    label: str
    keys: tuple[str, ...] = ()
    danger: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "label": self.label,
            "keys": list(self.keys),
            "danger": self.danger,
        }


@dataclass(frozen=True, slots=True)
class RemoteEvent:
    """One validated control change or action sent by the browser."""

    name: str
    value: int | float | None = None


class _RemoteHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class RemoteView:
    """Serve the latest published frame and controls on the loopback interface."""

    def __init__(
        self,
        title: str,
        *,
        port: int = DEFAULT_REMOTE_PORT,
        controls: tuple[RangeControl, ...] = (),
        actions: tuple[Action, ...] = (),
        jpeg_quality: int = 80,
    ) -> None:
        if not 0 <= port <= 65535:
            raise ValueError("port must be between 0 and 65535")
        if not 1 <= jpeg_quality <= 100:
            raise ValueError("jpeg_quality must be between 1 and 100")

        control_names = [control.name for control in controls]
        action_names = [action.name for action in actions]
        if len(control_names) != len(set(control_names)):
            raise ValueError("control names must be unique")
        if len(action_names) != len(set(action_names)):
            raise ValueError("action names must be unique")
        if set(control_names) & set(action_names):
            raise ValueError("control and action names must not overlap")

        self.title = title
        self.requested_port = port
        self.jpeg_quality = jpeg_quality
        self._controls = {control.name: control for control in controls}
        self._actions = {action.name: action for action in actions}
        self._state: dict[str, Any] = {
            control.name: control.value for control in controls
        }
        self._events: deque[RemoteEvent] = deque()
        self._condition = threading.Condition()
        self._raw_frame: NDArray[np.uint8] | None = None
        self._raw_version = 0
        self._jpeg: bytes | None = None
        self._jpeg_version = 0
        self._running = False
        self._server: _RemoteHTTPServer | None = None
        self._server_thread: threading.Thread | None = None
        self._encoder_thread: threading.Thread | None = None

    @property
    def port(self) -> int:
        if self._server is None:
            return self.requested_port
        return int(self._server.server_address[1])

    @property
    def url(self) -> str:
        return f"http://{LOOPBACK_HOST}:{self.port}"

    def start(self) -> None:
        if self._running:
            return
        handler = self._make_handler()
        self._server = _RemoteHTTPServer((LOOPBACK_HOST, self.requested_port), handler)
        self._running = True
        self._encoder_thread = threading.Thread(
            target=self._encode_frames,
            name="remote-view-encoder",
            daemon=True,
        )
        self._server_thread = threading.Thread(
            target=self._server.serve_forever,
            name="remote-view-http",
            daemon=True,
        )
        self._encoder_thread.start()
        self._server_thread.start()

    def publish_frame(self, frame: NDArray[np.uint8]) -> None:
        """Replace the pending frame; older unencoded frames are discarded."""
        if not self._running:
            return
        with self._condition:
            self._raw_frame = np.asarray(frame, dtype=np.uint8).copy()
            self._raw_version += 1
            self._condition.notify_all()

    def update_state(self, **values: Any) -> None:
        with self._condition:
            self._state.update(values)

    def drain_events(self) -> list[RemoteEvent]:
        with self._condition:
            events = list(self._events)
            self._events.clear()
        return events

    def close(self) -> None:
        server = self._server
        if server is None:
            return
        with self._condition:
            self._running = False
            self._condition.notify_all()
        server.shutdown()
        server.server_close()
        if self._server_thread is not None:
            self._server_thread.join(timeout=2)
        if self._encoder_thread is not None:
            self._encoder_thread.join(timeout=2)
        self._server = None

    def _encode_frames(self) -> None:
        encoded_raw_version = 0
        while True:
            with self._condition:
                self._condition.wait_for(
                    lambda: not self._running
                    or self._raw_version > encoded_raw_version
                )
                if not self._running:
                    return
                frame = self._raw_frame
                encoded_raw_version = self._raw_version
            if frame is None:
                continue
            success, encoded = cv2.imencode(
                ".jpg",
                frame,
                [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality],
            )
            if not success:
                continue
            with self._condition:
                self._jpeg = encoded.tobytes()
                self._jpeg_version += 1
                self._condition.notify_all()

    def _html_page(self) -> bytes:
        config = json.dumps(
            {
                "controls": [item.as_dict() for item in self._controls.values()],
                "actions": [item.as_dict() for item in self._actions.values()],
            },
            separators=(",", ":"),
        ).replace("</", "<\\/")
        page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(self.title)}</title>
<style>
:root {{ color-scheme: dark; font-family: system-ui, sans-serif; }}
body {{ margin: 0; background: #111827; color: #e5e7eb; }}
main {{ max-width: 1500px; margin: auto; padding: 1rem; }}
h1 {{ font-size: 1.2rem; margin: 0 0 .75rem; }}
.stream {{ width: 100%; max-height: 75vh; object-fit: contain; background: #030712; border-radius: .5rem; }}
.bar,.controls {{ display: flex; flex-wrap: wrap; gap: .65rem; margin-top: .75rem; align-items: center; }}
.status {{ color: #93c5fd; font-size: .9rem; }}
.control {{ min-width: 250px; flex: 1; padding: .6rem; background: #1f2937; border-radius: .4rem; }}
.control label {{ display: flex; justify-content: space-between; margin-bottom: .35rem; }}
input[type=range] {{ width: 100%; }}
button {{ border: 0; border-radius: .4rem; padding: .65rem .9rem; background: #2563eb; color: white; cursor: pointer; }}
button.danger {{ background: #b91c1c; }}
#connection.offline {{ color: #fca5a5; }}
</style>
</head>
<body><main>
<h1>{html.escape(self.title)}</h1>
<img id="stream" class="stream" src="/stream.mjpg" alt="Live camera stream">
<div class="bar"><span id="connection" class="status">Connecting...</span><span id="state" class="status"></span></div>
<div id="controls" class="controls"></div><div id="actions" class="controls"></div>
</main><script>
const config={config};
const controls=document.getElementById('controls'), actions=document.getElementById('actions');
const inputs={{}}, timers={{}};
const stream=document.getElementById('stream');
stream.addEventListener('error',()=>setTimeout(()=>{{ stream.src='/stream.mjpg?t='+Date.now(); }},1000));
async function post(path, body) {{
  const response=await fetch(path,{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(body)}});
  if(!response.ok) throw new Error(await response.text());
}}
for(const item of config.controls) {{
  const box=document.createElement('div'); box.className='control';
  const label=document.createElement('label'); const text=document.createElement('span'); text.textContent=item.label;
  const value=document.createElement('output'); value.textContent=item.value; label.append(text,value);
  const input=document.createElement('input'); input.type='range'; input.min=item.min; input.max=item.max; input.step=item.step; input.value=item.value;
  input.addEventListener('input',()=>{{ value.textContent=input.value; clearTimeout(timers[item.name]); timers[item.name]=setTimeout(()=>post('/api/control',{{name:item.name,value:Number(input.value)}}),80); }});
  box.append(label,input); controls.append(box); inputs[item.name]={{input,value}};
}}
for(const item of config.actions) {{
  const button=document.createElement('button'); button.textContent=item.label; if(item.danger) button.className='danger';
  button.addEventListener('click',()=>post('/api/action',{{name:item.name}})); actions.append(button);
}}
document.addEventListener('keydown',(event)=>{{
  if(event.target instanceof HTMLInputElement) return;
  for(const item of config.actions) if(item.keys.includes(event.key)) {{ event.preventDefault(); post('/api/action',{{name:item.name}}); return; }}
}});
async function refresh() {{
  const indicator=document.getElementById('connection');
  try {{
    const response=await fetch('/api/state',{{cache:'no-store'}}); const data=await response.json();
    indicator.textContent='Connected to Orin'; indicator.className='status';
    for(const [name,parts] of Object.entries(inputs)) if(data[name]!==undefined && document.activeElement!==parts.input) {{ parts.input.value=data[name]; parts.value.textContent=data[name]; }}
    const hidden=Object.entries(data).filter(([name])=>!inputs[name]).map(([name,value])=>`${{name}}: ${{value}}`);
    document.getElementById('state').textContent=hidden.join(' | ');
  }} catch(error) {{ indicator.textContent='Disconnected - retrying'; indicator.className='status offline'; }}
}}
refresh(); setInterval(refresh,1000);
</script></body></html>"""
        return page.encode("utf-8")

    def _make_handler(self) -> type[BaseHTTPRequestHandler]:
        view = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, _format: str, *args: object) -> None:
                return

            def do_GET(self) -> None:  # noqa: N802
                path = self.path.split("?", 1)[0]
                if path == "/":
                    self._send_bytes("text/html; charset=utf-8", view._html_page())
                elif path == "/api/state":
                    with view._condition:
                        payload = json.dumps(view._state).encode("utf-8")
                    self._send_bytes("application/json", payload)
                elif path == "/stream.mjpg":
                    self._stream_frames()
                else:
                    self.send_error(HTTPStatus.NOT_FOUND)

            def do_POST(self) -> None:  # noqa: N802
                path = self.path.split("?", 1)[0]
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if length <= 0 or length > 4096:
                        raise ValueError("invalid request size")
                    payload = json.loads(self.rfile.read(length))
                    if not isinstance(payload, dict):
                        raise ValueError("request body must be an object")
                    name = payload.get("name")
                    if not isinstance(name, str):
                        raise ValueError("name must be a string")
                    if path == "/api/control":
                        control = view._controls.get(name)
                        if control is None:
                            raise ValueError("unknown control")
                        value = control.normalized(payload.get("value"))
                        with view._condition:
                            view._state[name] = value
                            view._events.append(RemoteEvent(name, value))
                    elif path == "/api/action":
                        if name not in view._actions:
                            raise ValueError("unknown action")
                        with view._condition:
                            view._events.append(RemoteEvent(name))
                    else:
                        self.send_error(HTTPStatus.NOT_FOUND)
                        return
                except (ValueError, TypeError, json.JSONDecodeError) as exc:
                    self.send_error(HTTPStatus.BAD_REQUEST, str(exc))
                    return
                self._send_bytes("application/json", b'{"ok":true}')

            def _send_bytes(self, content_type: str, payload: bytes) -> None:
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(payload)

            def _stream_frames(self) -> None:
                self.send_response(HTTPStatus.OK)
                self.send_header(
                    "Content-Type", "multipart/x-mixed-replace; boundary=frame"
                )
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                version = 0
                try:
                    while True:
                        with view._condition:
                            view._condition.wait_for(
                                lambda: not view._running
                                or view._jpeg_version > version,
                                timeout=5,
                            )
                            if not view._running:
                                return
                            if view._jpeg_version <= version or view._jpeg is None:
                                continue
                            jpeg = view._jpeg
                            version = view._jpeg_version
                        self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\n")
                        self.wfile.write(
                            f"Content-Length: {len(jpeg)}\r\n\r\n".encode("ascii")
                        )
                        self.wfile.write(jpeg)
                        self.wfile.write(b"\r\n")
                        self.wfile.flush()
                except OSError:
                    return

        return Handler


def compose_grid(
    panels: list[tuple[str, NDArray[np.uint8]]],
    *,
    panel_width: int = 480,
    columns: int = 2,
) -> NDArray[np.uint8]:
    """Compose equally sized labelled BGR panels for a single remote stream."""
    if not panels:
        raise ValueError("at least one panel is required")
    if panel_width <= 0 or columns <= 0:
        raise ValueError("panel_width and columns must be positive")

    target_height = max(
        1,
        round(panels[0][1].shape[0] * panel_width / panels[0][1].shape[1]),
    )
    rendered: list[NDArray[np.uint8]] = []
    for title, image in panels:
        if image.ndim == 2:
            image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        panel = cv2.resize(
            image,
            (panel_width, target_height),
            interpolation=cv2.INTER_AREA,
        )
        cv2.rectangle(panel, (0, 0), (panel_width, 32), (20, 20, 20), -1)
        cv2.putText(
            panel,
            title,
            (10, 22),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )
        rendered.append(panel)

    blank = np.zeros_like(rendered[0])
    while len(rendered) % columns:
        rendered.append(blank.copy())
    rows = [
        np.hstack(rendered[index : index + columns])
        for index in range(0, len(rendered), columns)
    ]
    return np.vstack(rows)
