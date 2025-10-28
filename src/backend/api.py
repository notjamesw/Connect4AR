from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack, RTCConfiguration, RTCIceServer, RTCDataChannel
from aiortc.contrib.media import MediaBlackhole, MediaRecorder
from contextlib import asynccontextmanager
from av import VideoFrame
from game import Game
import cv2
import time
# import httpx
# import os
# from dotenv import load_dotenv
# load_dotenv()

# OPEN_RELAY_API_KEY = os.getenv("OPEN_RELAY_API_KEY")

class OpenCVCaptureTrack(VideoStreamTrack):
    def __init__(self, track, res):
        super().__init__()
        self.game = Game(res)
        self.track = track
        self.running = True
        self.frame_id = 0
        self.start_time = time.time()


    async def recv(self):
        # Capture frame from OpenCV and convert to VideoFrame
        # print("Receiving frame")
        frame = await self.track.recv()
        img = frame.to_ndarray(format="bgr24")

        # print("Frame size received:", frame.width, frame.height)

        if(frame.width != 1280 or frame.height != 720):
            # print("frame mismatch")
            img = cv2.resize(img, (1280, 720))
            processed_frame = self.game.process_frame(img, key=None)
        else:
            processed_frame = self.game.process_frame(img, key=None)

        new_frame = VideoFrame.from_ndarray(processed_frame, format="bgr24")
        new_frame.pts = frame.pts
        new_frame.time_base = frame.time_base
        
        return new_frame

# WebRTC configuration with ICE servers
ICE_SERVERS = [
    RTCIceServer(urls="stun:stun.l.google.com:19302"),
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/offer")
async def offer(request: Request):
    params = await request.json()
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])
    res = params.get("resolution")
    print("Received offer")

    # print("Received offer SDP lines:")
    # for line in offer.sdp.splitlines():
    #     print(line)

    # # Fetch ICE servers dynamically
    # async with httpx.AsyncClient() as client:
    #     ice_resp = await client.get(f"https://connect4ar.metered.live/api/v1/turn/credentials?apiKey={OPEN_RELAY_API_KEY}")
    #     ice_resp.raise_for_status()
    #     ice_config = ice_resp.json()
    
    # # Build RTCConfiguration from Open Relay response and add Google's STUN server
    # ice_servers = [RTCIceServer(**s) for s in ice_config]
    # ice_servers.append(RTCIceServer(urls="stun:stun.l.google.com:19302"))

    # config = RTCConfiguration(ice_servers)

    # pc = RTCPeerConnection(config)
    pc = RTCPeerConnection(CONFIG)
    pcs.add(pc)

    recorder = MediaBlackhole() # used for debugging, can be replaced with MediaRecorder to save to file

    @pc.on("track")
    def on_track(track):
        print("Received track:", track.kind)
        if track.kind == "video":
            local_video = OpenCVCaptureTrack(track, res)
            active_tracks.add(local_video)
            pc.addTrack(local_video)
        else:
            print("Received unsupported track:", track.kind)

        @track.on("ended")
        async def on_ended():
            local_video.running = False
            await recorder.stop()
            await pc.close()
            pcs.discard(pc)
    
    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

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
    return {"status": "ok", "message": "FastAPI backend is running!"}
