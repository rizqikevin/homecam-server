import { useState, useEffect, useCallback } from "react";
import { useApp } from "../context/AppContext";
import { api } from "../api";
import type { RecordingItem } from "../api";

type SizeBucket = "Any" | "<10MB" | "10–50MB" | ">50MB";

const SIZE_BUCKETS: { label: SizeBucket; test: (mb: number) => boolean }[] = [
  { label: "Any", test: () => true },
  { label: "<10MB", test: (mb) => mb < 10 },
  { label: "10–50MB", test: (mb) => mb >= 10 && mb <= 50 },
  { label: ">50MB", test: (mb) => mb > 50 },
];

export default function Recordings() {
  const { isRecording } = useApp();
  const [recordings, setRecordings] = useState<RecordingItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [reasonFilter, setReasonFilter] = useState<string>("All");
  const [hourFrom, setHourFrom] = useState("00:00");
  const [hourTo, setHourTo] = useState("23:59");
  const [sizeFilter, setSizeFilter] = useState<SizeBucket>("Any");
  const [selectedRecording, setSelectedRecording] = useState<RecordingItem | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  const fetchRecordings = useCallback(async () => {
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
  }, []);

  useEffect(() => {
    fetchRecordings();
  }, []);

  const handleDeleteRequest = (filename: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setDeleteError(null);
    setDeleteTarget(filename);
  };

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      await api.deleteRecording(deleteTarget);
      if (selectedRecording?.filename === deleteTarget) setSelectedRecording(null);
      await fetchRecordings();
      setDeleteTarget(null);
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : "Failed to delete recording");
    } finally {
      setDeleting(false);
    }
  };

  const filteredRecordings = recordings.filter((rec) => {
    const matchesSearch = rec.filename.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesReason =
      reasonFilter === "All" || rec.type.toLowerCase() === reasonFilter.toLowerCase();

    const recDate = new Date(rec.created_at);
    const recMinutes = recDate.getHours() * 60 + recDate.getMinutes();
    const [fH, fM] = hourFrom.split(":").map(Number);
    const [tH, tM] = hourTo.split(":").map(Number);
    const fromMinutes = fH * 60 + fM;
    const toMinutes = tH * 60 + tM;
    const matchesHour =
      fromMinutes <= toMinutes
        ? recMinutes >= fromMinutes && recMinutes <= toMinutes
        : recMinutes >= fromMinutes || recMinutes <= toMinutes;

    const mb = rec.size_bytes / (1024 * 1024);
    const bucket = SIZE_BUCKETS.find((b) => b.label === sizeFilter) ?? SIZE_BUCKETS[0];
    const matchesSize = bucket.test(mb);

    return matchesSearch && matchesReason && matchesHour && matchesSize;
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
      <div className="toolbar recordings-toolbar">
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

        <div className="filter-row">
          <div className="filter-inline">
            <label className="filter-label">🕐 Jam</label>
            <input
              type="time"
              className="input-time"
              value={hourFrom}
              onChange={(e) => setHourFrom(e.target.value)}
              title="Dari jam"
            />
            <span className="filter-sep">–</span>
            <input
              type="time"
              className="input-time"
              value={hourTo}
              onChange={(e) => setHourTo(e.target.value)}
              title="Sampai jam"
            />
          </div>

          <div className="filter-group">
            {(["Any", "<10MB", "10–50MB", ">50MB"] as const).map((bucket) => (
              <button
                key={bucket}
                className={`btn-tab ${sizeFilter === bucket ? "active" : ""}`}
                onClick={() => setSizeFilter(bucket)}
              >
                {bucket}
              </button>
            ))}
          </div>
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
                    onClick={(e) => handleDeleteRequest(rec.filename, e)}
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
                />
              </div>

              <div className="playback-info-table">
                <div className="info-row">
                  <span className="info-lbl">File Name</span>
                  <span className="info-val info-val--break">
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

              <div className="modal-actions">
                <a
                  href={api.getDownloadUrl(selectedRecording.filename)}
                  className="btn btn-primary modal-action-link"
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

      {deleteTarget && (
        <DeleteConfirmModal
          filename={deleteTarget}
          error={deleteError}
          deleting={deleting}
          onConfirm={handleDeleteConfirm}
          onCancel={() => { setDeleteTarget(null); setDeleteError(null); }}
        />
      )}
    </div>
  );
}

function DeleteConfirmModal({
  filename,
  error,
  deleting,
  onConfirm,
  onCancel,
}: {
  filename: string;
  error: string | null;
  deleting: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onCancel(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onCancel]);

  return (
    <div className="modal-overlay" onClick={onCancel}>
      <div
        className="modal-content modal-confirm"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="confirm-title"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header">
          <h3 id="confirm-title">Hapus rekaman?</h3>
          <button className="btn-close" onClick={onCancel} aria-label="Batal">✕</button>
        </div>
        <div className="modal-body">
          <p className="confirm-filename">{filename}</p>
          {error && <p className="delete-error">{error}</p>}
          <div className="modal-actions">
            <button className="btn btn-secondary" onClick={onCancel} disabled={deleting}>
              Batal
            </button>
            <button className="btn btn-danger" onClick={onConfirm} disabled={deleting} autoFocus>
              {deleting ? "Menghapus…" : "Hapus"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
