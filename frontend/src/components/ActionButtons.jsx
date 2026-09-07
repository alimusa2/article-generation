import React from 'react';

export default function ActionButtons({
  onPublish,
  isPublishing,
  isPublished,
  onRequestChanges,
}) {
  return (
    <div className="action-buttons-group">
      <button
        type="button"
        className="request-changes-btn"
        id="request-changes-btn"
        onClick={onRequestChanges}
      >
        Request changes
      </button>

      <button
        type="button"
        className="approve-publish-btn"
        id="approve-publish-btn"
        onClick={onPublish}
        disabled={isPublishing}
        style={isPublished ? { backgroundColor: '#15803d' } : {}}
      >
        {isPublishing
          ? "Publishing to WordPress..."
          : isPublished
          ? "Published Live ✓"
          : "Approve & Publish"}
      </button>
    </div>
  );
}
