"""Tool: read_ecg_device.

Consolidates the ESP32 serial-read logic (previously in the untracked
``usb_bridge.py``) into a contract-validated tool, and adds a hardware-free
``replay`` source so workflows can run against a recorded sample batch.

- source=serial  -> read a batch from a COM port (needs pyserial + hardware)
- source=replay  -> read floats from a CSV/text file (no hardware)
"""
from __future__ import annotations

import re
from typing import Literal, Optional

from pydantic import BaseModel, Field

from ..errors import WatError
from ..paths import resolve_repo_path
from ..registry import Tool, register


class ReadEcgInput(BaseModel):
    source: Literal["replay", "serial"] = "replay"
    # replay
    path: Optional[str] = None
    # serial
    port: Optional[str] = None
    baud: int = 115200
    batchSize: int = Field(750, gt=0)
    # common
    sampleRateHz: int = Field(250, gt=0)
    leadOff: bool = False


class ReadEcgOutput(BaseModel):
    samples: list[float]
    sampleRateHz: int
    leadOff: bool
    deviceId: str
    sampleCount: int


@register
class ReadEcgDevice(Tool):
    name = "read_ecg_device"
    Input = ReadEcgInput
    Output = ReadEcgOutput
    kind = "cli"
    idempotent = False            # a serial read consumes a live stream
    retryable = ("transient",)

    def run(self, inp: ReadEcgInput) -> ReadEcgOutput:
        if inp.source == "replay":
            return self._replay(inp)
        return self._serial(inp)

    def _replay(self, inp: ReadEcgInput) -> ReadEcgOutput:
        if not inp.path:
            raise WatError("replay source requires 'path'", category="schema")
        path = resolve_repo_path(inp.path)
        if not path.exists():
            raise WatError(f"replay file not found: {path}", category="dependency")
        text = path.read_text(encoding="utf-8", errors="ignore")
        samples = [float(tok) for tok in re.findall(r"[-+]?\d*\.\d+|[-+]?\d+", text)]
        if not samples:
            raise WatError("no numeric samples found in replay file", category="parsing")
        return ReadEcgOutput(samples=samples, sampleRateHz=inp.sampleRateHz,
                             leadOff=inp.leadOff, deviceId="replay",
                             sampleCount=len(samples))

    def _serial(self, inp: ReadEcgInput) -> ReadEcgOutput:
        if not inp.port:
            raise WatError("serial source requires 'port'", category="schema")
        try:
            import serial  # pyserial
        except ImportError as exc:
            raise WatError("pyserial not installed (needed for serial source)",
                           category="dependency", cause=exc)
        try:
            ser = serial.Serial(inp.port, inp.baud, timeout=1)
        except Exception as exc:  # SerialException etc.
            raise WatError(f"could not open serial port {inp.port}: {exc}",
                           category="transient", cause=exc)
        samples: list[float] = []
        try:
            while len(samples) < inp.batchSize:
                line = ser.readline().decode("utf-8", errors="ignore").strip()
                if not line:
                    continue
                try:
                    samples.append(float(int(line)))
                except ValueError:
                    continue  # status/banner line from the ESP32
        finally:
            ser.close()
        return ReadEcgOutput(samples=samples, sampleRateHz=inp.sampleRateHz,
                             leadOff=inp.leadOff, deviceId="esp32-usb-bridge",
                             sampleCount=len(samples))
