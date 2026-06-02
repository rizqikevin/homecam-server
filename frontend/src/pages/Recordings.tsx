import { useState, useEffect } from "react";
import { useApp } from "../context/AppContext";
import { api } from "../api";
import type { RecordingItem } from "../api";

export default function Recordings() {
  const { isRecording } = useApp();
  const [recordings, setRecordings] = useState<RecordingItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [reasonFilter, setReasonFilter] = useState<string>("All");
  const [selectedRecording, setSelectedRecording] = useState<RecordingItem | null>(null);

  const fetchRecordings = async () => {
    setLoading(true);
    try {
      const res = await api.getRecordings();
      setRecordings(res.items);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load recordings");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRecordings();
  }, []);

  const handleDelete = async (filename: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (confirm(`Are you sure you want to delete recording "${filename}"?`)) {
      try {
        await api.deleteRecording(filename);
        // Refresh the list
        await fetchRecordings();
        // If the deleted one was open, close it
        if (selectedRecording?.filename === filename) {
          setSelectedRecording(null);
        }
      } catch (err) {
        alert(err instanceof Error ? err.message : "Failed to delete recording");
      }
    }
  };

  const filteredRecordings = recordings.filter((rec) => {
    const matchesSearch = rec.filename.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesReason =
      reasonFilter === "All" || rec.type.toLowerCase() === reasonFilter.toLowerCase();
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
            placeholder="Search recordings by filename..."
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

      {error && <div className="error-banner">{error}</div>}

      {/* Grid view */}
      {loading ? (
        <div className="loading-state">
          <div className="spinner" />
          <p>Scanning security archive...</p>
        </div>
      ) : filteredRecordings.length === 0 ? (
        <div className="empty-state">
          <span className="empty-icon">📁</span>
          <h3>No recordings found</h3>
          <p>Try adjusting your search filters or start a manual recording on the dashboard.</p>
        </div>
      ) : (
        <div className="recordings-grid">
          {filteredRecordings.map((rec) => (
            <div
              key={rec.filename}
              className="recording-card"
              onClick={() => setSelectedRecording(rec)}
            >
              <div className="card-thumb">
                <span className="thumb-icon">🎥</span>
                <span className={`badge-reason reason-${rec.type.toLowerCase()}`}>
                  {rec.type.toUpperCase()}
                </span>
              </div>
              <div className="card-details">
                <h4 className="card-title" title={rec.filename}>
                  {rec.filename}
                </h4>
                <p className="card-meta">
                  <span>📅 {new Date(rec.created_at).toLocaleString()}</span>
                </p>
                <div className="card-footer">
                  <span className="card-size">💾 {rec.size_label}</span>
                  <button
                    className="btn-icon-danger"
                    onClick={(e) => handleDelete(rec.filename, e)}
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
              <h3 title={selectedRecording.filename}>{selectedRecording.filename}</h3>
              <button className="btn-close" onClick={() => setSelectedRecording(null)}>
                ✕
              </button>
            </div>
            <div className="modal-body">
              <div className="playback-player">
                {/* Real HTML5 video tag supporting Range HTTP playback streams */}
                <video
                  src={api.getPlaybackUrl(selectedRecording.filename)}
                  controls
                  autoPlay
                  className="playback-video-element"
                  style={{ width: "100%", maxHeight: "360px", background: "#000" }}
                />
              </div>

              <div className="playback-info-table">
                <div className="info-row">
                  <span className="info-lbl">File Name</span>
                  <span className="info-val" style={{ wordBreak: "break-all" }}>
                    {selectedRecording.filename}
                  </span>
                </div>
                <div className="info-row">
                  <span className="info-lbl">Date Recorded</span>
                  <span className="info-val">
                    {new Date(selectedRecording.created_at).toLocaleString()}
                  </span>
                </div>
                <div className="info-row">
                  <span className="info-lbl">File Size</span>
                  <span className="info-val">{selectedRecording.size_label}</span>
                </div>
                <div className="info-row">
                  <span className="info-lbl">Trigger Source</span>
                  <span className="info-val">{selectedRecording.type.toUpperCase()}</span>
                </div>
              </div>

              <div style={{ marginTop: "20px", display: "flex", justifyContent: "flex-end", gap: "10px" }}>
                <a
                  href={api.getDownloadUrl(selectedRecording.filename)}
                  className="btn btn-primary"
                  style={{ textDecoration: "none" }}
                  download
                >
                  📥 Download Video
                </a>
                <button className="btn btn-secondary" onClick={() => setSelectedRecording(null)}>
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
