"use client";

import { useState } from "react";
import { LiveKitRoom, RoomAudioRenderer, useRoomContext } from "@livekit/components-react";
import { AudioLines, LoaderCircle, PhoneOff, VolumeX, X } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const LIVEKIT_URL = process.env.NEXT_PUBLIC_LIVEKIT_URL || "ws://localhost:7880";

function ActiveVoiceControls({ onError }: { onError: (message: string) => void }) {
  const room = useRoomContext();
  const [stopping, setStopping] = useState(false);

  const stopReply = async () => {
    setStopping(true);
    onError("");
    try {
      const command = new TextEncoder().encode(JSON.stringify({ action: "stop_reply" }));
      await room.localParticipant.publishData(command, { reliable: true, topic: "harizon-control" });
      window.setTimeout(() => setStopping(false), 900);
    } catch {
      setStopping(false);
      onError("Could not stop the voice reply. Try ending the voice session.");
    }
  };

  return <div className="live-voice-actions">
    <button type="button" className="live-stop-reply" onClick={() => void stopReply()} disabled={stopping}>
      <VolumeX size={15}/>{stopping ? "Stopping reply…" : "Stop reply"}
    </button>
    <button type="button" className="live-end-call" onClick={() => room.disconnect()}>
      <PhoneOff size={15}/>End voice
    </button>
  </div>;
}

export default function LiveVoice({ onClose }: { onClose: () => void }) {
  const [credentials, setCredentials] = useState<{ token: string; url: string; customerAuthenticated: boolean } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const connect = async () => {
    setLoading(true);
    setError("");
    try {
      const response = await fetch(`${API}/api/voice/token`, { method: "POST", credentials: "include" });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not start the voice session");
      setCredentials({ token: data.token, url: data.url || LIVEKIT_URL, customerAuthenticated: !!data.customer_authenticated });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not start voice");
    } finally {
      setLoading(false);
    }
  };

  return <div className="live-voice-card">
    <div className="live-voice-heading">
      <span className="live-voice-icon"><AudioLines size={17}/></span>
      <div><b>Live voice with HarizonAI</b><small>YOUR AUDIO IS NOT RECORDED</small></div>
      <button onClick={onClose} aria-label="Close voice and assistant"><X size={16}/></button>
    </div>
    {credentials ? <LiveKitRoom token={credentials.token} serverUrl={credentials.url} connect={true} audio={true} video={false} onDisconnected={() => setCredentials(null)} className="livekit-room">
      <RoomAudioRenderer/>
      <div className="live-connected"><span className="live-pulse"/><div><b>Connected{credentials.customerAuthenticated ? " · signed in" : " · guest"}</b><small>{credentials.customerAuthenticated ? "Use Stop reply to interrupt HarizonAI, or End voice to disconnect." : "Product help is available. Sign in and reconnect to ask about your orders."}</small></div></div>
      <ActiveVoiceControls onError={setError}/>
      {error && <div className="live-voice-error" role="status">{error}</div>}
    </LiveKitRoom> : <div className="live-voice-body">
      <p>Talk naturally about products, delivery, returns, and warranty.</p>
      {error && <div className="live-voice-error" role="alert">{error}</div>}
      <button className="button button-dark live-connect" onClick={() => void connect()} disabled={loading}>
        {loading ? <LoaderCircle className="spin" size={16}/> : <AudioLines size={16}/>}
        {loading ? "Connecting…" : "Start live voice"}
      </button>
      <small>Microphone permission is requested by your browser.</small>
    </div>}
  </div>;
}
