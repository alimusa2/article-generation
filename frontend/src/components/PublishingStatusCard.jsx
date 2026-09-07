import React from 'react';

export default function PublishingStatusCard({ wordpressPostLink, isPublished, wordpressPostId }) {
  return (
    <div className="sidebar-card" id="publishing-status-card">
      <div className="sidebar-card-header">
        <span className="sidebar-card-title">Publishing Status</span>
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

      <div className="draft-link-info">
        {wordpressPostLink ? (
          <a href={wordpressPostLink} target="_blank" rel="noreferrer">
            {isPublished ? "View Live Post on WordPress ↗" : "Open Draft in WordPress ↗"}
          </a>
        ) : (
          "Draft link will appear once created."
        )}
      </div>
    </div>
  );
}
