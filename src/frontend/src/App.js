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

    // 1️⃣ Get local video
    const localStream = await navigator.mediaDevices.getUserMedia({
      video: { width: 1920, height: 1080, frameRate: 25 },
      audio: false
    });

    if (localVideoRef.current) localVideoRef.current.srcObject = localStream;

    // 2️⃣ Add local tracks
    localStream.getTracks().forEach(track => pc.addTrack(track, localStream));

    // 3️⃣ Create offer **after tracks added**
    const offer = await pc.createOffer();
    await pc.setLocalDescription(offer);

    // 4️⃣ Send offer to backend
    const response = await fetch(`${BACKEND_URL}/offer`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sdp: offer.sdp, type: offer.type, resolution: 720 }),
    });
    const answer = await response.json();

    // 5️⃣ Set remote description
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