import React from 'react';

export default function ImageGalleryModal({
  isOpen,
  onClose,
  images,
  selectedIndex,
  onSelectHero,
}) {
  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card modal-card-gallery" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div>
            <h3>Generated Visual Assets Gallery</h3>
            <p className="modal-subtitle">Full set of 8 editorial assets generated for WordPress & Pinterest</p>
          </div>
          <button type="button" className="modal-close-btn" onClick={onClose}>✕</button>
        </div>

        <div className="gallery-grid">
          {images.map((img, idx) => {
            const isHero = idx === selectedIndex;
            const url = typeof img === 'string' ? img : (img.avif_url || img.cloudinary_url);
            const prompt = typeof img === 'object' && img.prompt ? img.prompt : `Rustic stone fireplace interior asset #${idx + 1}`;

            return (
              <div key={idx} className={`gallery-item ${isHero ? 'is-hero' : ''}`}>
                <div className="gallery-item-thumb-wrapper">
                  <img src={url} alt={`Visual asset ${idx + 1}`} />
                  {isHero && <span className="gallery-hero-badge">Featured Hero</span>}
                </div>
                <div className="gallery-item-details">
                  <span className="gallery-item-num">Asset #{idx + 1}</span>
                  <p className="gallery-item-prompt">{prompt}</p>
                  <div className="gallery-item-actions">
                    <a
                      href={url}
                      target="_blank"
                      rel="noreferrer"
                      className="gallery-action-link"
                    >
                      View full size ↗
                    </a>
                    {!isHero && (
                      <button
                        type="button"
                        className="set-hero-btn"
                        onClick={() => onSelectHero(url, idx)}
                      >
                        Set as hero
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        <div className="modal-footer" style={{ marginTop: '20px', display: 'flex', justifyContent: 'flex-end' }}>
          <button
            type="button"
            className="request-changes-btn"
            style={{ flex: 'none', padding: '8px 20px' }}
            onClick={onClose}
          >
            Close Gallery
          </button>
        </div>
      </div>
    </div>
  );
}
