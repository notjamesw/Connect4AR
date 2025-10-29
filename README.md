# Connect4AR
**Connect 4 in AR with OpenCV**

Real-time video processing backend for Connect4AR - an augmented reality Connect 4 game controlled by hand gestures. 
The FastAPI server handles WebRTC video streams, processes hand tracking using MediaPipe, and renders game state overlays in real-time with OpenCV.
There is a simple React app in the [frontend folder](https://github.com/notjamesw/Connect4AR/tree/main/src/frontend) bootstrapped with create-react-app.

## 🎮 Features

- **WebRTC Video Streaming**: Receives video streams from browser clients using aiortc
- **Real-Time Hand Tracking**: MediaPipe integration for precise hand landmark detection
- **Gesture Recognition**: Custom pinch detection algorithm with temporal 5-frame smoothing
- **Game Logic**: Complete Connect 4 implementation with win condition validation
- **AR Overlay Rendering**: OpenCV-based game board and chip rendering on live video
- **Low Latency**: Optimized for <100ms end-to-end latency at 720p/1080p
- **Adaptive Resolution Handling**: Automatically scales incoming frames to 1280×720 using OpenCV when the browser sends lower resolutions during initial connection or bandwidth fluctuations

## 🏗️ Architecture

```
Client Browser (WebRTC) 
    ↓ Video Stream (1280×720@20fps)
FastAPI Backend (aiortc)
    ↓ Frame Processing
MediaPipe Hand Tracking
    ↓ Landmark Detection
Game Logic & OpenCV Rendering
    ↓ Processed Video
Client Browser (WebRTC)
```

## 🛠️ Tech Stack

- **FastAPI**: Async web framework for REST API endpoints
- **aiortc**: WebRTC implementation for Python
- **MediaPipe**: Google's hand tracking solution
- **OpenCV**: Computer vision and image processing
- **NumPy**: Efficient numerical operations
- **Docker**: Containerization for deployment
- **GCP Compute Engine**: Used GCP for custom TURN server with coTURN, and backend deployment with Docker

## 📋 Prerequisites

- Python 3.9+
- Docker (optional, for containerized deployment)
- TURN server (for production NAT traversal)

## 🚀 Quick Start

### Local Development

1. **Clone the repository**
```bash
git clone https://github.com/yourusername/connect4ar-backend.git
cd connect4ar-backend
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Run the server**
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

4. **Test the API**
```bash
curl http://localhost:8000/
```

### Docker Deployment

1. **Build the image**
```bash
docker build -t connect4ar-backend:latest .
```

2. **Run the container**
```bash
docker run -d \
  -p 8000:8000 \
  -e TURN_SERVER_IP=your.turn.server.ip \
  -e TURN_USERNAME=username \
  -e TURN_PASSWORD=password \
  --name connect4ar-backend \
  connect4ar-backend:latest
```

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `TURN_SERVER_IP` | TURN server IP address for NAT traversal | Required |
| `TURN_USERNAME` | TURN server authentication username | Required |
| `TURN_PASSWORD` | TURN server authentication password | Required |

### WebRTC Configuration

The backend uses the following ICE servers:
- Google STUN servers (public IP discovery)
- Custom TURN server (relay for NAT traversal)

Configuration in `main.py`:
```python
ICE_SERVERS = [
    RTCIceServer(urls="stun:stun.l.google.com:19302"),
    RTCIceServer(
        urls=f"turn:{TURN_SERVER_IP}:3478",
        username=TURN_USERNAME,
        credential=TURN_PASSWORD
    ),
]
```

## 📡 API Endpoints

### `POST /offer`
Initiates WebRTC connection by receiving SDP offer from client.

**Request Body:**
```json
{
  "sdp": "v=0\r\no=- ...",
  "type": "offer",
  "resolution": 720
}
```

**Response:**
```json
{
  "sdp": "v=0\r\no=- ...",
  "type": "answer"
}
```

### `POST /stop`
Closes all active peer connections.

### `POST /reset`
Resets the game board state for all active games.

### `POST /toggle_tracking`
Toggles visibility of hand tracking landmarks overlay.

### `GET /`
Health check endpoint.

**Response:**
```json
{
  "status": "ok",
  "message": "FastAPI backend is running!",
  "turn_server": "34.145.38.148",
  "ice_servers": 3
}
```

### `GET /ice-config`
Returns ICE server configuration (useful for debugging).

## 🎯 Game Logic

### Hand Gesture Detection

The system detects pinch gestures using MediaPipe hand landmarks:
- Calculates distance between thumb tip (landmark 4) and index tip (landmark 8)
- Pinch threshold: 5% of frame width
- 5-frame temporal smoothing to reduce jitter

### Gameplay Flow

1. **Grab**: Pinch above the board to grab a chip
2. **Drag**: Move hand horizontally to select column
3. **Release**: Release pinch to drop chip in column
4. **Win Detection**: Automatically checks for 4-in-a-row (horizontal, vertical, diagonal)

### Connect 4 Implementation

```python
class Connect4:
    - 7×6 game board (configurable)
    - Turn-based gameplay (Player 1: Red, Player 2: Yellow)
    - Win condition checking in 4 directions
    - Valid move validation
```

## 🎨 Visual Features

- **Board Overlay**: Semi-transparent blue board with white holes
- **Chip Animation**: Smooth falling animation using time-based interpolation
- **Real-time Updates**: Game state rendered at video frame rate
- **Hand Tracking Visualization**: Optional landmark overlay (toggle with `/toggle_tracking`)

## 🔍 Performance Considerations

### Optimization Techniques

1. **Frame Processing**
   - Efficient NumPy operations for board rendering
   - Direct pixel manipulation with OpenCV
   - Minimal memory allocation per frame

2. **Hand Tracking**
   - Single-hand mode to reduce computation
   - Confidence thresholds tuned for reliability (0.7 detection, 0.5 tracking)

3. **Video Encoding**
   - Configurable resolution (720p/1080p)
   - Maintains original frame rate
   - Uses VideoFrame format for efficient aiortc integration

## 🐛 Troubleshooting

### Connection Issues

**Problem**: ICE connection fails or disconnects
- **Solution**: Verify TURN server is running and accessible
- **Check**: Firewall allows UDP ports 49152-65535 for TURN relay

**Problem**: High latency or dropped frames
- **Solution**: Reduce resolution or increase instance CPU/memory
- **Check**: Network bandwidth and server load

### Hand Tracking Issues

**Problem**: Gestures not detected consistently
- **Solution**: Ensure good lighting and contrast
- **Check**: Hand is within camera frame and fully visible

**Problem**: False pinch detections
- **Solution**: Adjust threshold in `game.py`: `thresh = w * 0.05`

## 📦 Dependencies

```
fastapi
uvicorn
aiortc
opencv-python
mediapipe
numpy
python-av
```

See `requirements.txt` for complete list with versions.

## 🚧 Known Limitations

- Single simultaneous game session per backend instance
- Requires GPU/hardware acceleration for optimal performance at 1080p
- TURN server required for production deployment (NAT traversal)

## 🔮 Future Improvements

- [ ] AI opponent using minimax algorithm
- [ ] WebGL-accelerated rendering
- [ ] Horizontal scaling with load balancer

## 📄 License

MIT License - see LICENSE file for details

## 👤 Author

James Wen
- GitHub: [@jameswen10](https://github.com/jameswen10)

## 🙏 Acknowledgments

- MediaPipe team for hand tracking models
- aiortc contributors for Python WebRTC implementation
- Google for STUN server infrastructure

---

**Note**: This backend requires a corresponding frontend client. See [Connect4AR Frontend](https://github.com/yourusername/connect4ar-frontend) for the React web application.

