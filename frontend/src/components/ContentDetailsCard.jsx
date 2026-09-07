import React from 'react';

export default function ContentDetailsCard({
  wordCount,
  readTimeMin,
  createdAt,
  updatedAt,
}) {
  return (
    <div className="sidebar-card" id="content-details-card">
      <div className="sidebar-card-header">
        <span className="sidebar-card-title">Content Details</span>
      </div>

      <div className="details-row">
        <span className="details-label">Word count</span>
        <span className="details-value">{wordCount.toLocaleString()}</span>
      </div>

      <div className="details-row">
        <span className="details-label">Estimated read time</span>
        <span className="details-value">{readTimeMin} min</span>
      </div>

      <div className="details-row">
        <span className="details-label">Created</span>
        <span className="details-value">{createdAt}</span>
      </div>

      <div className="details-row">
        <span className="details-label">Last updated</span>
        <span className="details-value">{updatedAt}</span>
      </div>
    </div>
  );
}
