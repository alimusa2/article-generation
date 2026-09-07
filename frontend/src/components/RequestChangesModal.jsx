import React, { useState } from 'react';

export default function RequestChangesModal({
  isOpen,
  onClose,
  onSubmit,
  isSubmitting,
}) {
  const [category, setCategory] = useState("images");
  const [notes, setNotes] = useState("");

  if (!isOpen) return null;

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!notes.trim() || isSubmitting) return;
    onSubmit({ notes: notes.trim(), category });
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div>
            <h3>Request Editorial Revisions</h3>
            <p className="modal-subtitle">Submit feedback or specific change requests for this draft</p>
          </div>
          <button type="button" className="modal-close-btn" onClick={onClose}>✕</button>
        </div>

        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: '16px' }}>
            <label className="field-label">Revision Category</label>
            <div style={{ display: 'flex', gap: '8px', marginTop: '6px' }}>
              {[
                { id: 'images', label: 'Images & Visuals' },
                { id: 'seo', label: 'SEO & Keywords' },
                { id: 'content', label: 'Article Copy & Tone' },
              ].map((c) => (
                <button
                  key={c.id}
                  type="button"
                  className={`preset-chip-btn ${category === c.id ? 'active-chip' : ''}`}
                  style={category === c.id ? { backgroundColor: '#1e392a', color: '#ffffff', borderColor: '#1e392a' } : {}}
                  onClick={() => setCategory(c.id)}
                >
                  {c.label}
                </button>
              ))}
            </div>
          </div>

          <div style={{ marginBottom: '20px' }}>
            <label className="field-label">Revision Instructions & Feedback</label>
            <textarea
              className="field-textarea"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="e.g. Regenerate the bedroom fireplace images with lighter Scandinavian wood tones..."
              rows={4}
              required
              style={{ width: '100%', minHeight: '90px' }}
            />
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
            <button
              type="button"
              className="request-changes-btn"
              style={{ flex: 'none', padding: '8px 16px' }}
              onClick={onClose}
              disabled={isSubmitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="approve-publish-btn"
              style={{ flex: 'none', padding: '8px 20px' }}
              disabled={isSubmitting || !notes.trim()}
            >
              {isSubmitting ? "Submitting..." : "Submit Revision Request"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
