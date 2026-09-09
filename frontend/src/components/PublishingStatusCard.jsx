import React, { useState, useEffect } from 'react';
import { getPinterestBoards } from '../services/api';

export default function PublishingStatusCard({ wordpressPostLink, isPublished, wordpressPostId, pinterestPins }) {
  const [boards, setBoards] = useState([]);
  const [selectedBoardId, setSelectedBoardId] = useState('');
  const [boardInput, setBoardInput] = useState('');
  const [extractedBoardId, setExtractedBoardId] = useState('');
  const [isFetchingBoards, setIsFetchingBoards] = useState(false);
  const [boardsError, setBoardsError] = useState(null);

  const handleFetchBoards = async () => {
    setIsFetchingBoards(true);
    setBoardsError(null);
    try {
      const data = await getPinterestBoards();
      if (data && data.boards && data.boards.length > 0) {
        setBoards(data.boards);
      } else if (data && data.error) {
        setBoardsError(data.error);
      } else {
        setBoardsError("No boards found for account or token expired");
      }
    } catch (err) {
      setBoardsError(err.message || "Failed to fetch boards");
    } finally {
      setIsFetchingBoards(false);
    }
  };

  const handleBoardInputChange = (val) => {
    setBoardInput(val);
    if (!val) {
      setExtractedBoardId('');
      return;
    }
    const trimmed = val.trim();
    if (/^\d+$/.test(trimmed)) {
      setExtractedBoardId(trimmed);
      setSelectedBoardId(trimmed);
      return;
    }
    const matchNum = trimmed.match(/boards\/(\d+)/i) || trimmed.match(/\/(\d{10,})\/?$/);
    if (matchNum) {
      setExtractedBoardId(matchNum[1]);
      setSelectedBoardId(matchNum[1]);
      return;
    }
    const matchSlug = trimmed.match(/pinterest\.com\/[^/]+\/([^/]+)/i);
    if (matchSlug) {
      setExtractedBoardId(matchSlug[1]);
      setSelectedBoardId(matchSlug[1]);
      return;
    }
    setExtractedBoardId(trimmed);
  };

  const handleSelectBoard = (boardId) => {
    setSelectedBoardId(boardId);
    setExtractedBoardId(boardId);
    setBoardInput(boardId);
  };

  return (
    <div className="sidebar-card" id="publishing-status-card">
      <div className="sidebar-card-header">
        <span className="sidebar-card-title">Publishing & Pinterest Status</span>
      </div>

      <div className={`draft-alert-box ${isPublished ? 'published' : ''}`} style={isPublished ? { backgroundColor: '#f0fdf4', borderColor: '#bbf7d0' } : {}}>
        <div className="draft-alert-title" style={isPublished ? { color: '#166534' } : {}}>
          {isPublished ? "Published" : "Draft"}
        </div>
        <div className="draft-alert-text" style={isPublished ? { color: '#15803d' } : {}}>
          {isPublished
            ? `WordPress post #${wordpressPostId || ''} is live and published.`
            : "WordPress post is in draft state. Nothing is published live automatically."}
        </div>
      </div>

      <div className="draft-link-info" style={{ marginBottom: '12px' }}>
        {wordpressPostLink ? (
          <a href={wordpressPostLink} target="_blank" rel="noreferrer" style={{ fontWeight: '600', color: '#1e392a' }}>
            {isPublished ? "View Live Post on WordPress ↗" : "Open Draft in WordPress ↗"}
          </a>
        ) : (
          "Draft link will appear once created."
        )}
      </div>

      {/* Pinterest Board Selector */}
      <div className="pinterest-board-section" style={{ borderTop: '1px solid #e5e7eb', paddingTop: '12px', marginTop: '12px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
          <label style={{ fontSize: '0.78rem', fontWeight: '600', color: '#374151' }}>
            📌 Pinterest Board Selector
          </label>
          <button
            type="button"
            onClick={handleFetchBoards}
            disabled={isFetchingBoards}
            style={{
              padding: '2px 8px',
              fontSize: '0.72rem',
              fontWeight: '600',
              color: '#1e392a',
              backgroundColor: '#f3f4f6',
              border: '1px solid #d1d5db',
              borderRadius: '4px',
              cursor: isFetchingBoards ? 'wait' : 'pointer',
            }}
          >
            {isFetchingBoards ? "Fetching..." : "Fetch Boards 🔄"}
          </button>
        </div>
        
        {boards.length > 0 && (
          <select
            value={selectedBoardId}
            onChange={(e) => handleSelectBoard(e.target.value)}
            style={{
              width: '100%',
              padding: '6px 10px',
              fontSize: '0.8rem',
              borderRadius: '6px',
              border: '1px solid #d1d5db',
              marginBottom: '8px',
              backgroundColor: '#fff',
            }}
          >
            <option value="">-- Select Board from Account --</option>
            {boards.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name} (ID: {b.id})
              </option>
            ))}
          </select>
        )}

        <input
          type="text"
          placeholder="Paste Pinterest Board URL or Board ID..."
          value={boardInput}
          onChange={(e) => handleBoardInputChange(e.target.value)}
          style={{
            width: '100%',
            padding: '6px 10px',
            fontSize: '0.8rem',
            borderRadius: '6px',
            border: '1px solid #d1d5db',
          }}
        />

        {extractedBoardId && (
          <div style={{ fontSize: '0.72rem', color: '#059669', marginTop: '4px', fontWeight: '500' }}>
            ✓ Board ID extracted: <code>{extractedBoardId}</code>
          </div>
        )}

        {boardsError && (
          <div style={{ fontSize: '0.72rem', color: '#dc2626', marginTop: '4px' }}>
            ⚠ {boardsError}
          </div>
        )}
      </div>

      {/* Pinterest Pins List (8 Pins) */}
      {pinterestPins && pinterestPins.length > 0 && (
        <div className="pinterest-pins-section" style={{ borderTop: '1px solid #e5e7eb', paddingTop: '12px', marginTop: '12px' }}>
          <div style={{ fontSize: '0.78rem', fontWeight: '600', color: '#374151', marginBottom: '8px' }}>
            📌 Generated Pins ({pinterestPins.length} pins created)
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '240px', overflowY: 'auto' }}>
            {pinterestPins.map((pin, idx) => (
              <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '6px', backgroundColor: '#f9fafb', borderRadius: '6px', border: '1px solid #f3f4f6' }}>
                <img
                  src={pin.image_url || pin.media_source?.url || 'https://images.unsplash.com/photo-1542314831-068cd1dbfeeb?w=200'}
                  alt={pin.title || `Pin ${idx + 1}`}
                  style={{ width: '40px', height: '28px', objectFit: 'cover', borderRadius: '4px' }}
                />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: '0.75rem', fontWeight: '600', color: '#111827', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {pin.title || `Pin #${idx + 1}`}
                  </div>
                  <a
                    href={pin.link || wordpressPostLink || '#'}
                    target="_blank"
                    rel="noreferrer"
                    style={{ fontSize: '0.7rem', color: '#2563eb', textDecoration: 'none' }}
                  >
                    Redirect to WordPress Post ↗
                  </a>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
