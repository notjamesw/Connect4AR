import React, { useRef, useState } from "react";

const BACKEND_URL = "http://127.0.0.1:8000";

function App() {
  const localVideoRef = useRef(null);
  const remoteVideoRef = useRef(null);
  const [pc, setPc] = useState(null);
  const [streaming, setStreaming] = useState(false);


  const startGame = async () => {
    setStreaming(true);
    const pc = new RTCPeerConnection();
    setPc(pc);

    // Register remote track handler
    pc.ontrack = (event) => {
      remoteVideoRef.current.srcObject = event.streams[0];
    };

    // Get local video feed from browser
    const localStream = await navigator.mediaDevices.getUserMedia({
      video: { width: 1280, height: 720, frameRate: 25, resizeMode: "none" },
      audio: false
    });

    // Adjust sender params for better quality
    const sender = pc.getSenders().find(s => s.track && s.track.kind === "video");
    if (sender) {
      const params = sender.getParameters();
      if (!params.encodings) params.encodings = [{}];

      params.encodings[0].scaleResolutionDownBy = 1; // no downscaling
      params.encodings[0].maxBitrate = 5_000_000;    // allow up to 5 Mbps bitrate
      
      await sender.setParameters(params);
      
      console.log("Sender parameters:", params);
      // Also inspect the video track itself
      const settings = sender.track.getSettings();
      console.log(`Track capture: ${settings.width}x${settings.height} @ ${settings.frameRate}fps`);
    }

    if (localVideoRef.current) localVideoRef.current.srcObject = localStream;

    // Add local tracks
    localStream.getTracks().forEach(track => pc.addTrack(track, localStream));

    // Create offer after tracks are added
    const offer = await pc.createOffer();
    await pc.setLocalDescription(offer);

    // Send offer to backend
    const response = await fetch(`${BACKEND_URL}/offer`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sdp: offer.sdp, type: offer.type, resolution: 720 }),
    });
    const answer = await response.json();

    // Set remote description
    await pc.setRemoteDescription(answer);
  };

  // Stop game / close peer connection
  const stopGame = async () => {
    setStreaming(false);
    if (pc) {
      pc.close();
      setPc(null);
    }

    try {
      await fetch(`${BACKEND_URL}/stop`, { method: "POST" });
    } catch (err) {
      console.warn("Backend stop call failed:", err);
    }

    if (localVideoRef.current?.srcObject) {
      localVideoRef.current.srcObject.getTracks().forEach((t) => t.stop());
      localVideoRef.current.srcObject = null;
    }

    if (remoteVideoRef.current?.srcObject) {
      remoteVideoRef.current.srcObject.getTracks().forEach((t) => t.stop());
      remoteVideoRef.current.srcObject = null;
    }
  };

    return (
    <div style={{ textAlign: "center", padding: "2rem" }}>
      <h1>Connect4 AR Demo</h1>

      <div style={{ display: "flex", flexDirection: "column",justifyContent: "center", gap: "2rem" }}>
        <div>
          <h3>🎥 Local Camera</h3>
          <video ref={localVideoRef} autoPlay playsInline width="1280" height="720" />
        </div>

        <div>
          <h3>🧠 Processed Stream</h3>
          <video ref={remoteVideoRef} autoPlay playsInline width="1280" height="720" />
        </div>
      </div>

      <div style={{ marginTop: "1rem" }}>
        {!streaming ? (
          <button onClick={startGame}>Start Game</button>
        ) : (
          <button onClick={stopGame}>Stop Game</button>
        )}
      </div>
    </div>
  );
}

export default App;