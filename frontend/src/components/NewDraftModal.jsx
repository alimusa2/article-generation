import React, { useState } from 'react';
import { PRESETS } from '../constants/pipeline';

export default function NewDraftModal({
  isOpen,
  onClose,
  onSubmit,
  loading,
  currentTitle,
}) {
  const [topic, setTopic] = useState(currentTitle);

  if (!isOpen) return null;

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!topic.trim() || loading) return;
    onSubmit(topic.trim());
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>Start Pipeline Generation</h3>
          <button type="button" className="modal-close-btn" onClick={onClose}>✕</button>
        </div>

        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: '16px' }}>
            <label className="field-label">Article Topic / Keyword Title</label>
            <input
              type="text"
              className="field-input"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="e.g. Rustic Stone Fireplace Inspiration for 2026"
              required
            />
          </div>

          <div style={{ marginBottom: '16px' }}>
            <label className="field-label" style={{ marginBottom: '8px' }}>Presets</label>
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
              {PRESETS.map((p, idx) => (
                <button
                  key={idx}
                  type="button"
                  className="preset-chip-btn"
                  onClick={() => setTopic(p)}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
            <button
              type="button"
              className="request-changes-btn"
              style={{ flex: 'none', padding: '8px 16px' }}
              onClick={onClose}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="approve-publish-btn"
              style={{ flex: 'none', padding: '8px 20px' }}
              disabled={loading || !topic.trim()}
            >
              {loading ? "Starting..." : "Generate Pipeline"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
