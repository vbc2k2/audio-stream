"""
Windows Audio Streaming Server (WebRTC/UDP)
Streams system audio to connected clients via WebRTC.
"""

import asyncio
import json
import os
import socket
import sys
import fractions
import logging

import numpy as np
import sounddevice as sd
import av
from aiohttp import web

from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.mediastreams import AudioStreamTrack
from aiortc.contrib.media import MediaRelay

logging.basicConfig(level=logging.INFO)

# Helper for PyInstaller bundled files
def resource_path(relative_path):
    """Get absolute path to resource, works for dev and PyInstaller."""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(__file__), relative_path)

# Audio config
SAMPLE_RATE = 48000
CHANNELS = 2
FRAME_SAMPLES = 960  # 20ms at 48kHz (standard for Opus)

# Globals
pcs = set()
relay = MediaRelay()
audio_track = None


class SystemAudioTrack(AudioStreamTrack):
    """Captures system audio and yields frames for WebRTC."""
    
    kind = "audio"

    def __init__(self):
        super().__init__()
        self._queue = asyncio.Queue(maxsize=20)
        self._sample_count = 0
        self._start_time = None
        self._loop = None
        self._stream = None
        
    async def start_capture(self):
        """Start audio capture (must be called from async context)."""
        self._loop = asyncio.get_running_loop()
        
        device = self._find_loopback()
        logging.info(f"Using audio device: {device}")
        
        self._stream = sd.InputStream(
            device=device,
            channels=CHANNELS,
            samplerate=SAMPLE_RATE,
            blocksize=FRAME_SAMPLES,
            dtype='int16',
            callback=self._callback,
            latency='low'
        )
        self._stream.start()
        logging.info("Audio capture started")
        
    def _find_loopback(self):
        """Find loopback/monitor device (Windows: VB-Cable, Linux: PulseAudio monitor)."""
        devices = sd.query_devices()
        
        priority_keywords = [
            'cable output',
            'monitor',
            'stereo mix',
            'loopback',
            'pulse',
            'what u hear',
        ]
        
        for keyword in priority_keywords:
            for i, d in enumerate(devices):
                name = d['name'].lower()
                if d['max_input_channels'] > 0 and keyword in name:
                    print(f"Selected: {d['name']}")
                    return i
        
        print("Using default audio input device")
        return None
        
    def _callback(self, indata, frames, time_info, status):
        """Called by sounddevice in audio thread."""
        if status:
            print(f"Audio status: {status}", file=sys.stderr)
        
        self._sample_count += frames
        if self._sample_count % SAMPLE_RATE < frames:
            rms = np.sqrt(np.mean(indata.astype(np.float32)**2))
            print(f"[Audio] Level: {rms:.4f}")
        
        try:
            self._loop.call_soon_threadsafe(
                self._push_frame, 
                indata.copy()
            )
        except Exception as e:
            print(f"Callback error: {e}", file=sys.stderr)
            
    def _push_frame(self, data):
        """Push audio data to queue (runs on asyncio loop)."""
        if self._queue.full():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
        try:
            self._queue.put_nowait(data)
        except asyncio.QueueFull:
            pass

    async def recv(self):
        """Called by aiortc to get next audio frame."""
        data = await self._queue.get()
        
        packed = data.reshape(1, -1)
        
        frame = av.AudioFrame.from_ndarray(packed, format='s16', layout='stereo')
        frame.sample_rate = SAMPLE_RATE
        frame.pts = self._sample_count
        frame.time_base = fractions.Fraction(1, SAMPLE_RATE)
        
        return frame
    
    def stop(self):
        if self._stream:
            self._stream.stop()
            self._stream.close()
        super().stop()


# HTTP Handlers
async def index(request):
    html_path = resource_path("client.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return web.Response(text=f.read(), content_type="text/html")


async def offer(request):
    params = await request.json()
    offer_desc = RTCSessionDescription(sdp=params["sdp"], type=params["type"])
    
    pc = RTCPeerConnection()
    pcs.add(pc)
    
    track = relay.subscribe(audio_track)
    pc.addTrack(track)
    
    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        logging.info(f"Connection state: {pc.connectionState}")
        if pc.connectionState == "failed":
            await pc.close()
            pcs.discard(pc)
    
    await pc.setRemoteDescription(offer_desc)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)
    
    return web.json_response({
        "sdp": pc.localDescription.sdp,
        "type": pc.localDescription.type
    })


async def on_startup(app):
    global audio_track
    audio_track = SystemAudioTrack()
    await audio_track.start_capture()


async def on_shutdown(app):
    coros = [pc.close() for pc in pcs]
    await asyncio.gather(*coros)
    pcs.clear()
    if audio_track:
        audio_track.stop()


def get_local_ips():
    ips = []
    try:
        hostname = socket.gethostname()
        for ip in socket.gethostbyname_ex(hostname)[2]:
            if not ip.startswith("127."):
                ips.append(ip)
    except:
        pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        if ip not in ips:
            ips.append(ip)
    except:
        pass
    return ips or ["127.0.0.1"]


if __name__ == "__main__":
    app = web.Application()
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    app.router.add_get("/", index)
    app.router.add_post("/offer", offer)
    
    print("=" * 60)
    print("  WebRTC Audio Server")
    print("=" * 60)
    for ip in get_local_ips():
        print(f"  http://{ip}:8080")
    print("=" * 60)
    
    web.run_app(app, host="0.0.0.0", port=8080, print=None)
