# iPad as Windows PC Speaker

Stream high-quality audio from your Windows PC to your iPad over WiFi using this simple web-based solution. Uses TCP so latency is high. Make sure silent mode is off in your device. Latency is bad for streaming video audio but can be used for streaming for music only.

## Features

- **Quality Audio**: 48kHz 16-bit stereo (CD quality)
- **No iPad App Required**: Works in Safari browser
- **Simple Setup**: One-click server launch

## Quick Start

### 1. Install & Run

**Option A: Double-click**
- Simply double-click `start_server.bat`

**Option B: Command line**
```powershell
cd <$PATH>\audio_stream
pip install -r requirements.txt
python server.py
```

### 2. Connect from iPad

1. Make sure iPad and PC are on the **same WiFi network**
2. Open Safari on your iPad
3. Go to the URL shown in the server window (e.g., `http://192.X.Y.Z:8080`)
4. Tap **"Start Audio"** button
5. Play audio on your Windows PC - it will stream to your iPad!

## Troubleshooting

### No audio is being captured

1. **Enable Stereo Mix** (Windows):
   - Right-click the speaker icon in taskbar → "Sounds"
   - Go to "Recording" tab
   - Right-click empty area → "Show Disabled Devices"
   - Right-click "Stereo Mix" → Enable
   - Set as default device

2. **Check audio drivers**: Some audio drivers don't support loopback capture. Try updating your audio drivers.

### Cannot connect from iPad

1. **Check WiFi**: Both devices must be on the same network
2. **Firewall**: Allow Python through Windows Firewall when prompted
3. **Correct URL**: Make sure you're using the IP address shown by the server

### Audio is choppy or has gaps

1. **Network**: Move closer to your WiFi router
2. **CPU**: Close unnecessary applications on your PC
3. **Buffer**: The system will automatically adjust, give it a few seconds

### Safari shows security warning

For Safari on iOS, you may need HTTPS. For home use, you can:
1. Accept the warning (if shown)
2. Use Chrome on iPad instead (more permissive)

## Technical Details

| Setting | Value |
|---------|-------|
| Sample Rate | 48000 Hz |
| Bit Depth | 16-bit |
| Channels | Stereo |
| Audio Format | PCM (uncompressed) |
| Protocol | WebSocket |
| Ports | HTTP: 8080, WebSocket: 8081 |

## Requirements

- Windows 10/11
- Python 3.8+
- iPad with Safari (iOS 13+)
- Same WiFi network for both devices

## Dependencies

- `websockets` - WebSocket server
- `sounddevice` - Audio capture
- `numpy` - Audio processing


