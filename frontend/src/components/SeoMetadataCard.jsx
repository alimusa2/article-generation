import React, { useState } from 'react';

export default function SeoMetadataCard({
  seoTitle,
  setSeoTitle,
  metaDesc,
  setMetaDesc,
  focusKeyword,
  setFocusKeyword,
  slug,
  setSlug,
  onSaveSeo,
}) {
  const [isEditing, setIsEditing] = useState(false);

  const handleToggleEdit = () => {
    if (isEditing && onSaveSeo) {
      onSaveSeo({
        seo_title: seoTitle,
        meta_description: metaDesc,
        focus_keyphrase: focusKeyword,
        url_slug: slug,
        secondary_keywords: [],
      });
    }
    setIsEditing(!isEditing);
  };

  return (
    <div className="sidebar-card" id="seo-metadata-card">
      <div className="sidebar-card-header">
        <span className="sidebar-card-title">SEO Metadata</span>
        <button
          type="button"
          className="edit-btn"
          onClick={handleToggleEdit}
        >
          {isEditing ? "Done" : "Edit"}
        </button>
      </div>

      <div className="sidebar-field-group">
        <label className="field-label">SEO title</label>
        <input
          type="text"
          className="field-input"
          value={seoTitle}
          onChange={(e) => setSeoTitle(e.target.value)}
          readOnly={!isEditing}
        />
      </div>

      <div className="sidebar-field-group">
        <label className="field-label">Meta description</label>
        <textarea
          className="field-textarea"
          value={metaDesc}
          onChange={(e) => setMetaDesc(e.target.value)}
          readOnly={!isEditing}
          rows={3}
        />
      </div>

      <div className="sidebar-field-group">
        <label className="field-label">Focus keyword</label>
        <input
          type="text"
          className="field-input"
          value={focusKeyword}
          onChange={(e) => setFocusKeyword(e.target.value)}
          readOnly={!isEditing}
        />
      </div>

      <div className="sidebar-field-group">
        <label className="field-label">Slug</label>
        <input
          type="text"
          className="field-input"
          value={slug}
          onChange={(e) => setSlug(e.target.value)}
          readOnly={!isEditing}
        />
      </div>
    </div>
  );
}
