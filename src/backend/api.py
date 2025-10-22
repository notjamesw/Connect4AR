from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack, RTCConfiguration, RTCIceServer, RTCDataChannel
from aiortc.contrib.media import MediaBlackhole, MediaRecorder
from av import VideoFrame
from src.backend.game import Game
import time

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
        frame = await self.track.recv()
        img = frame.to_ndarray(format="bgr24")

        # processed_frame = img
        processed_frame = self.game.process_frame(img, key=None)

        new_frame = VideoFrame.from_ndarray(processed_frame, format="bgr24")
        new_frame.pts = frame.pts
        new_frame.time_base = frame.time_base
        
        return new_frame
    
# WebRTC configuration with STUN server
ICE_SERVERS = [RTCIceServer("stun:stun.l.google.com:19302")]
CONFIG = RTCConfiguration(ICE_SERVERS)

pcs = set()

@app.post("/offer")
async def offer(request: Request):
    params = await request.json()
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])
    res = params.get("resolution")

    # print("Received offer SDP lines:")
    # for line in offer.sdp.splitlines():
    #     print(line)

    pc = RTCPeerConnection(CONFIG)
    pcs.add(pc)

    recorder = MediaBlackhole() # used for debugging, can be replaced with MediaRecorder to save to file

    @pc.on("track")
    def on_track(track):
        print("Received track:", track.kind)
        if track.kind == "video":
            local_video = OpenCVCaptureTrack(track, res)
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