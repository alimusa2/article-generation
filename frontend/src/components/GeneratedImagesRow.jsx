import React from 'react';

export default function GeneratedImagesRow({ thumbnails, onViewAll, onSelectThumbnail }) {
  return (
    <div className="generated-images-block">
      <div className="generated-images-header">
        <span className="generated-images-title">Generated Images</span>
        <button
          type="button"
          className="view-all-link"
          id="view-all-images-btn"
          onClick={onViewAll}
          style={{ background: 'transparent', border: 'none', font: 'inherit', cursor: 'pointer' }}
        >
          View all images
        </button>
      </div>

      <div className="images-row">
        {thumbnails.map((imgUrl, i) => (
          <div
            key={i}
            className="image-thumb-card"
            onClick={() => onSelectThumbnail && onSelectThumbnail(i)}
            title={`Click to view Asset #${i + 1} details`}
            style={{ cursor: 'pointer' }}
          >
            <img src={imgUrl} alt={`Generated visual asset ${i + 1}`} />
          </div>
        ))}
      </div>
    </div>
  );
}
