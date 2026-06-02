import { useState } from "react";
import { useApp } from "../context/AppContext";

interface RecordingItem {
  id: string;
  name: string;
  timestamp: string;
  duration: string;
  size: string;
  camera: string;
  reason: "Motion" | "Manual" | "Schedule";
}

const INITIAL_RECORDINGS: RecordingItem[] = [
  {
    id: "rec_1",
    name: "Front Gate — Motion Detected",
    timestamp: "2026-06-02T09:42:15Z",
    duration: "00:45",
    size: "12.4 MB",
    camera: "Front Yard (Webcam)",
    reason: "Motion",
  },
  {
    id: "rec_2",
    name: "Manual Capture",
    timestamp: "2026-06-02T08:15:00Z",
    duration: "02:15",
    size: "34.8 MB",
    camera: "Front Yard (Webcam)",
    reason: "Manual",
  },
  {
    id: "rec_3",
    name: "Front Gate — Vehicle Passing",
    timestamp: "2026-06-01T18:30:22Z",
    duration: "01:00",
    size: "18.1 MB",
    camera: "Front Yard (Webcam)",
    reason: "Motion",
  },
  {
    id: "rec_4",
    name: "Scheduled Night Patrol",
    timestamp: "2026-06-01T03:00:00Z",
    duration: "10:00",
    size: "155.2 MB",
    camera: "Front Yard (Webcam)",
    reason: "Schedule",
  },
  {
    id: "rec_5",
    name: "Front Gate — Mail Carrier",
    timestamp: "2026-05-31T14:10:05Z",
    duration: "00:30",
    size: "8.9 MB",
    camera: "Front Yard (Webcam)",
    reason: "Motion",
  },
];

export default function Recordings() {
  const { isRecording } = useApp();
  const [recordings, setRecordings] = useState<RecordingItem[]>(INITIAL_RECORDINGS);
  const [searchTerm, setSearchTerm] = useState("");
  const [reasonFilter, setReasonFilter] = useState<string>("All");
  const [selectedRecording, setSelectedRecording] = useState<RecordingItem | null>(null);

  const handleDelete = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (confirm("Are you sure you want to delete this recording?")) {
      setRecordings((prev) => prev.filter((rec) => rec.id !== id));
    }
  };

  const filteredRecordings = recordings.filter((rec) => {
    const matchesSearch =
      rec.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      rec.camera.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesReason = reasonFilter === "All" || rec.reason === reasonFilter;
    return matchesSearch && matchesReason;
  });

  return (
    <div className="page">
      <div className="page-header">
        <h1>Saved Recordings</h1>
        <p className="page-subtitle">View and manage local security archives</p>
      </div>

      {isRecording && (
        <div className="recording-alert-banner">
          <span className="blink-dot" />
          <span>Currently recording live feed... The new archive will appear here once stopped.</span>
        </div>
      )}

      {/* Filters Toolbar */}
      <div className="toolbar">
        <div className="search-box">
          <span className="search-icon">🔍</span>
          <input
            type="text"
            placeholder="Search recordings or cameras..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>

        <div className="filter-group">
          <button
            className={`btn-tab ${reasonFilter === "All" ? "active" : ""}`}
            onClick={() => setReasonFilter("All")}
          >
            All
          </button>
          <button
            className={`btn-tab ${reasonFilter === "Motion" ? "active" : ""}`}
            onClick={() => setReasonFilter("Motion")}
          >
            Motion
          </button>
          <button
            className={`btn-tab ${reasonFilter === "Manual" ? "active" : ""}`}
            onClick={() => setReasonFilter("Manual")}
          >
            Manual
          </button>
          <button
            className={`btn-tab ${reasonFilter === "Schedule" ? "active" : ""}`}
            onClick={() => setReasonFilter("Schedule")}
          >
            Schedule
          </button>
        </div>
      </div>

      {/* Recordings Grid */}
      {filteredRecordings.length === 0 ? (
        <div className="empty-state">
          <span className="empty-icon">📁</span>
          <h3>No recordings found</h3>
          <p>Try adjusting your search filters or start a manual recording on the dashboard.</p>
        </div>
      ) : (
        <div className="recordings-grid">
          {filteredRecordings.map((rec) => (
            <div
              key={rec.id}
              className="recording-card"
              onClick={() => setSelectedRecording(rec)}
            >
              <div className="card-thumb">
                <span className="thumb-icon">🎥</span>
                <span className={`badge-reason reason-${rec.reason.toLowerCase()}`}>
                  {rec.reason}
                </span>
                <span className="thumb-duration">{rec.duration}</span>
              </div>
              <div className="card-details">
                <h4 className="card-title">{rec.name}</h4>
                <p className="card-meta">
                  <span>📅 {new Date(rec.timestamp).toLocaleString()}</span>
                </p>
                <div className="card-footer">
                  <span className="card-size">💾 {rec.size}</span>
                  <button
                    className="btn-icon-danger"
                    onClick={(e) => handleDelete(rec.id, e)}
                    title="Delete recording"
                  >
                    🗑️
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Playback Modal */}
      {selectedRecording && (
        <div className="modal-overlay" onClick={() => setSelectedRecording(null)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>{selectedRecording.name}</h3>
              <button className="btn-close" onClick={() => setSelectedRecording(null)}>
                ✕
              </button>
            </div>
            <div className="modal-body">
              {/* Playback player frame */}
              <div className="playback-player">
                <div className="playback-canvas-placeholder">
                  <div className="scanlines" />
                  <div className="hud">
                    <span className="hud-rec">● PLAY</span>
                    <span className="hud-time">
                      {new Date(selectedRecording.timestamp).toLocaleTimeString()}
                    </span>
                  </div>
                  <div className="playback-static-text">
                    <p className="static-title">CCTV PLAYBACK STREAM</p>
                    <p className="static-sub">{selectedRecording.camera}</p>
                    <p className="static-desc">File size: {selectedRecording.size}</p>
                  </div>
                  <div className="cctv-overlay-grid" />
                </div>
                
                {/* Playback controls */}
                <div className="playback-controls">
                  <button className="control-btn">◀◀ Rewind</button>
                  <button className="control-btn play-active">▶ Play / Pause</button>
                  <button className="control-btn">Fast Fwd ▶▶</button>
                </div>
              </div>

              <div className="playback-info-table">
                <div className="info-row">
                  <span className="info-lbl">Camera</span>
                  <span className="info-val">{selectedRecording.camera}</span>
                </div>
                <div className="info-row">
                  <span className="info-lbl">Date Recorded</span>
                  <span className="info-val">
                    {new Date(selectedRecording.timestamp).toLocaleString()}
                  </span>
                </div>
                <div className="info-row">
                  <span className="info-lbl">File size</span>
                  <span className="info-val">{selectedRecording.size}</span>
                </div>
                <div className="info-row">
                  <span className="info-lbl">Trigger Source</span>
                  <span className="info-val">{selectedRecording.reason} Trigger</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
