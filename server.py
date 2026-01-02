"""
Windows Audio Streaming Server
Streams system audio to connected clients via WebSocket for playback on iPad/other devices.
"""

import asyncio
import json
import socket
import struct
import sys
from typing import Set

import numpy as np
import sounddevice as sd
from websockets.asyncio.server import serve, ServerConnection

# Audio configuration - optimized for smooth streaming
SAMPLE_RATE = 48000 #44100  # Standard audio rate
CHANNELS = 2  # Stereo
DTYPE = np.float32  # Use float32 for VB-Cable compatibility
BLOCK_SIZE = 4800  # 100ms of audio - larger blocks for smoother streaming
WS_PORT = 8080
HTTP_PORT = 8080  # Same port for simplicity

# Connected clients
clients: Set[ServerConnection] = set()

# Audio buffer for streaming
audio_queue: asyncio.Queue(maxsize=20)


def get_loopback_device():
    """Find the Windows loopback device for system audio capture."""
    devices = sd.query_devices()
    
    # Priority 1: Look for VB-Cable Output (most reliable for system audio)
    for i, device in enumerate(devices):
        name = device['name'].lower()
        if device['max_input_channels'] > 0 and 'cable output' in name:
            print(f"Found VB-Cable device: {device['name']}")
            print("  NOTE: Set VB-Cable as your default Windows output device!")
            return i
    
    # Priority 2: Look for "PC Speaker" loopback device
    for i, device in enumerate(devices):
        name = device['name'].lower()
        if device['max_input_channels'] > 0 and 'pc speaker' in name:
            print(f"Found PC Speaker loopback device: {device['name']}")
            return i
    
    # Priority 3: Look for explicit loopback/stereo mix devices
    for i, device in enumerate(devices):
        name = device['name'].lower()
        if device['max_input_channels'] > 0:
            if 'loopback' in name or 'stereo mix' in name or 'what u hear' in name:
                print(f"Found loopback device: {device['name']}")
                return i
    
    # Fallback to default input
    print("Warning: No loopback device found. Using default input device.")
    return None


# Debug: count samples to show audio level
sample_count = 0

def audio_callback(indata, frames, time, status):
    """Callback for audio capture - puts audio data in queue."""
    global sample_count
    if status:
        print(f"Audio status: {status}", file=sys.stderr)
    
    # Debug: show audio level every ~1 second
    sample_count += 1
    if sample_count % 50 == 0:  # Every 50 blocks (~1 second)
        level = np.abs(indata).max()
        if level > 0.001:
            print(f"Audio level: {level:.4f} (audio detected!)")
        else:
            print(f"Audio level: {level:.4f} (silence)")
    
    
    if audio_queue is not None:
        try:
            # Convert float32 to int16 for transmission
            # Clamp values to [-1, 1] then scale to int16 range
            clamped = np.clip(indata, -1.0, 1.0)
            int16_data = (clamped * 32767).astype(np.int16)
            audio_queue.put_nowait(int16_data.tobytes())
        except asyncio.QueueFull:
            pass  # Drop frames if queue is full (prevents latency buildup)


async def audio_broadcaster():
    """Broadcasts audio data to all connected WebSocket clients."""
    global audio_queue
    audio_queue = asyncio.Queue(maxsize=50)  # Limit queue size to prevent latency
    
    while True:
        try:
            audio_data = await audio_queue.get()
            
            # Copy the set to avoid modification during iteration
            current_clients = clients.copy()
            
            if current_clients:
                # Send to all connected clients
                disconnected = set()
                for client in current_clients:
                    try:
                        await client.send(audio_data)
                    except Exception:
                        disconnected.add(client)
                
                # Remove disconnected clients
                clients.difference_update(disconnected)
                
        except Exception as e:
            print(f"Broadcaster error: {e}")
            await asyncio.sleep(0.1)


async def websocket_handler(websocket: ServerConnection):
    """Handle WebSocket connections from audio clients."""
    print(f"Client connected: {websocket.remote_address}")
    clients.add(websocket)
    
    try:
        # Send audio configuration to client
        config = {
            "type": "config",
            "sampleRate": SAMPLE_RATE,
            "channels": CHANNELS,
            "bitsPerSample": 16
        }
        await websocket.send(json.dumps(config))
        
        # Keep connection alive and handle any messages
        async for message in websocket:
            # Handle ping/pong or control messages if needed
            if isinstance(message, str):
                data = json.loads(message)
                if data.get("type") == "ping":
                    await websocket.send(json.dumps({"type": "pong"}))
                    
    except Exception as e:
        print(f"Client error: {e}")
    finally:
        clients.discard(websocket)
        print(f"Client disconnected: {websocket.remote_address}")


def get_local_ip():
    """Get the local IP address of this machine."""
    try:
        # Create a socket to determine the local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


# Simple HTTP server for serving the client HTML
HTML_CONTENT = None

async def http_handler(reader, writer):
    """Simple HTTP handler to serve the client HTML page."""
    global HTML_CONTENT
    
    if HTML_CONTENT is None:
        try:
            with open("client.html", "r", encoding="utf-8") as f:
                HTML_CONTENT = f.read()
        except FileNotFoundError:
            HTML_CONTENT = "<html><body><h1>Error: client.html not found</h1></body></html>"
    
    # Read the request
    request = await reader.read(1024)
    
    # Send HTTP response
    response = f"""HTTP/1.1 200 OK\r
Content-Type: text/html; charset=utf-8\r
Content-Length: {len(HTML_CONTENT.encode('utf-8'))}\r
Connection: close\r
Access-Control-Allow-Origin: *\r
\r
{HTML_CONTENT}"""
    
    writer.write(response.encode('utf-8'))
    await writer.drain()
    writer.close()
    await writer.wait_closed()


async def main():
    """Main entry point."""
    local_ip = get_local_ip()
    
    print("=" * 60)
    print("  Windows Audio Streaming Server")
    print("=" * 60)
    print()
    
    # Find loopback device
    device = get_loopback_device()
    
    print()
    print(f"Audio Settings:")
    print(f"  Sample Rate: {SAMPLE_RATE} Hz")
    print(f"  Channels: {CHANNELS}")
    print(f"  Block Size: {BLOCK_SIZE} samples ({BLOCK_SIZE/SAMPLE_RATE*1000:.1f}ms)")
    print()
    
    # Start the audio stream
    try:
        stream = sd.InputStream(
            device=device,
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype=DTYPE,
            blocksize=BLOCK_SIZE,
            callback=audio_callback,
            latency='low'
        )
        stream.start()
        print("Audio capture started successfully!")
    except Exception as e:
        print(f"Error starting audio capture: {e}")
        print("\nTroubleshooting:")
        print("1. Make sure you have a recording device enabled")
        print("2. Try enabling 'Stereo Mix' in Windows Sound settings")
        print("3. Some audio drivers may not support loopback")
        return
    
    print()
    print("=" * 60)
    print(f"  Server running!")
    print(f"  ")
    print(f"  Open this URL on your iPad:")
    print(f"  http://{local_ip}:{WS_PORT}")
    print("=" * 60)
    print()
    print("Press Ctrl+C to stop the server")
    print()
    
    # Start HTTP server for client page
    http_server = await asyncio.start_server(http_handler, "0.0.0.0", HTTP_PORT)
    
    # Start WebSocket server (on a different port for clarity)
    ws_port = WS_PORT + 1  # WebSocket on 8081
    async with serve(websocket_handler, "0.0.0.0", ws_port):
        # Start the audio broadcaster
        broadcaster_task = asyncio.create_task(audio_broadcaster())
        
        try:
            await asyncio.Future()  # Run forever
        except asyncio.CancelledError:
            pass
        finally:
            stream.stop()
            stream.close()
            broadcaster_task.cancel()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServer stopped.")
