from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack, RTCConfiguration, RTCIceServer
from aiortc.contrib.media import MediaBlackhole
from contextlib import asynccontextmanager
from av import VideoFrame
from game import Game
import cv2
import time
import os

class OpenCVCaptureTrack(VideoStreamTrack):
    def __init__(self, track, res):
        super().__init__()
        self.game = Game(res)
        self.track = track
        self.running = True
        self.frame_id = 0
        self.start_time = time.time()

    async def recv(self):
        frame = await self.track.recv()
        img = frame.to_ndarray(format="bgr24")

        if(frame.width != 1280 or frame.height != 720):
            img = cv2.resize(img, (1280, 720))
            processed_frame = self.game.process_frame(img, key=None)
        else:
            processed_frame = self.game.process_frame(img, key=None)

        new_frame = VideoFrame.from_ndarray(processed_frame, format="bgr24")
        new_frame.pts = frame.pts
        new_frame.time_base = frame.time_base
        
        return new_frame

# CRITICAL: Use your VM's EXTERNAL IP, not localhost or internal IP
TURN_SERVER_IP = os.getenv("TURN_SERVER_IP", "EXTERNAL_IP")
TURN_USERNAME = os.getenv("TURN_USERNAME", "username")
TURN_PASSWORD = os.getenv("TURN_PASSWORD", "password")

# WebRTC configuration with ICE servers
ICE_SERVERS = [
    # Google's STUN servers (for discovering public IP)
    RTCIceServer(urls="stun:stun.l.google.com:19302"),
    RTCIceServer(urls="stun:stun1.l.google.com:19302"),
    
    # Your TURN server (for relaying when direct connection fails)
    RTCIceServer(
        urls=f"turn:{TURN_SERVER_IP}:3478",
        username=TURN_USERNAME,
        credential=TURN_PASSWORD
    ),
    # Also add TURNS (TLS) if you have certificates
    # RTCIceServer(
    #     urls=f"turns:{TURN_SERVER_IP}:5349",
    #     username=TURN_USERNAME,
    #     credential=TURN_PASSWORD
    # ),
]

CONFIG = RTCConfiguration(ICE_SERVERS)

pcs = set()
active_tracks: set[OpenCVCaptureTrack] = set()

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    for pc in pcs:
        await pc.close()
    pcs.clear()

app = FastAPI(lifespan=lifespan)

origins = [
    "http://localhost:3000",
    "https://jameswen.netlify.app",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/offer")
async def offer(request: Request):
    params = await request.json()
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])
    res = params.get("resolution")
    
    print("=" * 50)
    print("Received offer")
    print(f"TURN Server: {TURN_SERVER_IP}")
    print(f"ICE Servers configured: {len(ICE_SERVERS)}")
    print("=" * 50)

    pc = RTCPeerConnection(CONFIG)
    pcs.add(pc)

    # Add detailed logging for ICE
    @pc.on("iceconnectionstatechange")
    async def on_ice_state_change():
        print(f"ICE Connection State: {pc.iceConnectionState}")
        if pc.iceConnectionState == "failed":
            print("ICE CONNECTION FAILED - Check TURN server configuration!")

    @pc.on("connectionstatechange")
    async def on_connection_state_change():
        print(f"Connection State: {pc.connectionState}")

    @pc.on("icegatheringstatechange")
    async def on_ice_gathering_state_change():
        print(f"ICE Gathering State: {pc.iceGatheringState}")

    recorder = MediaBlackhole()

    @pc.on("track")
    def on_track(track):
        print(f"Received track: {track.kind}")
        if track.kind == "video":
            local_video = OpenCVCaptureTrack(track, res)
            active_tracks.add(local_video)
            pc.addTrack(local_video)
        else:
            print(f"Received unsupported track: {track.kind}")

        @track.on("ended")
        async def on_ended():
            local_video.running = False
            await recorder.stop()
            await pc.close()
            pcs.discard(pc)
    
    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    print(f"Answer created with {len(answer.sdp.splitlines())} SDP lines")

    return {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}

@app.post("/stop")
async def stop():
    for pc in pcs:
        await pc.close()
    pcs.clear()
    return {"status": "stopped"}

@app.post("/reset")
async def reset(request: Request):
    params = await request.json()
    for track in active_tracks:
        track.game.reset()
    return {"status": "reset"}

@app.post("/toggle_tracking")
async def toggle_tracking(request: Request):
    params = await request.json()
    for track in active_tracks:
        track.game.toggle_hands()
    return {"status": "toggled"}

@app.get("/")
async def root():
    return {
        "status": "ok", 
        "message": "FastAPI backend is running!",
        "turn_server": TURN_SERVER_IP,
        "ice_servers": len(ICE_SERVERS)
    }

@app.get("/ice-config")
async def ice_config():
    """Endpoint to verify ICE server configuration"""
    return {
        "ice_servers": [
            {"urls": server.urls, "username": getattr(server, 'username', None), "credential": getattr(server, 'credential', None)}
            for server in ICE_SERVERS
        ]
    }