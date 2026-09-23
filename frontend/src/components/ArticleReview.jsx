import React, { useState } from 'react';
import GeneratedImagesRow from './GeneratedImagesRow';

export default function ArticleReview({
  title,
  heroImage,
  thumbnails,
  job,
  lastSavedAt,
  defaultContent,
  onViewAllImages,
  onSelectThumbnail,
}) {
  const [viewRaw, setViewRaw] = useState(false);

  const rawHtml = job?.formatted_content || job?.article_html || (
    `<h1>${title}</h1>\n<p>${defaultContent.intro}</p>\n\n<figure class="wp-block-image"><img src="${heroImage}" alt="${title}" /></figure>\n\n<h2>${defaultContent.subheading}</h2>\n<p>${defaultContent.body}</p>`
  );

  return (
    <section className="article-main-card">
      <div className="article-top-toolbar">
        <div className="article-status-group">
          <span className="draft-tag">Draft</span>
          <span className="last-saved-text">Last saved: {lastSavedAt}</span>
        </div>

        <button
          type="button"
          className="view-raw-btn"
          id="view-raw-html-btn"
          onClick={() => setViewRaw(!viewRaw)}
        >
          {viewRaw ? "View Article" : "View raw HTML"}
        </button>
      </div>

      {viewRaw ? (
        <pre className="raw-code-box">{rawHtml}</pre>
      ) : (
        <div>
          {job?.formatted_content || job?.article_html ? (
            <article
              className="article-rendered-body"
              id="live-article-content"
              dangerouslySetInnerHTML={{
                __html: job.formatted_content || job.article_html,
              }}
            />
          ) : job ? (
            <article className="article-generating-state">
              <h1 className="article-headline">{title}</h1>
              <div style={{
                padding: '24px',
                backgroundColor: '#f8fafc',
                border: '1px border-dashed #cbd5e1',
                borderRadius: '8px',
                margin: '20px 0',
                color: '#475569',
                display: 'flex',
                alignItems: 'center',
                gap: '12px'
              }}>
                <span className="status-dot-pulsing" style={{ display: 'inline-block', width: '10px', height: '10px', backgroundColor: '#3b82f6', borderRadius: '50%' }} />
                <span>Writing long-form article content for <strong>"{title}"</strong>...</span>
              </div>
            </article>
          ) : (
            <article>
              <h1 className="article-headline">{title}</h1>
              <p className="article-intro">{defaultContent.intro}</p>

              <figure className="article-hero-figure">
                <img src={heroImage} alt={title} />
              </figure>

              <h2 className="article-subheading">{defaultContent.subheading}</h2>
              <p className="article-body-text">{defaultContent.body}</p>
            </article>
          )}

          <GeneratedImagesRow
            thumbnails={thumbnails}
            onViewAll={onViewAllImages}
            onSelectThumbnail={onSelectThumbnail}
          />
        </div>
      )}
    </section>
  );
}
