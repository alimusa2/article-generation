import React from 'react';
import { STAGES } from '../constants/pipeline';

const STAGE_DESCRIPTIONS = {
  writing_article: 'Generating long-form editorial article structure and content via Google Gemini AI...',
  generating_seo: 'Synthesizing focus keywords, SEO titles, meta descriptions, and URL slug via OpenRouter LLM...',
  generating_image_prompts: 'Crafting 8 photorealistic interior design photography prompts...',
  generating_images: 'Generating 8 photorealistic images sequentially via Cloudflare FLUX AI model...',
  uploading_images: 'Processing images, optimizing AVIF formats, and uploading to Cloudinary storage...',
  publishing_wordpress: 'Creating draft article post on WordPress REST API with embedded AVIF figures...',
  publishing_pinterest: 'Generating 8 rich editorial pins referencing Cloudinary URLs on Pinterest...',
};

const STAGE_PERCENTAGES = {
  writing_article: 14,
  generating_seo: 28,
  generating_image_prompts: 42,
  generating_images: 57,
  uploading_images: 71,
  publishing_wordpress: 85,
  publishing_pinterest: 95,
  completed: 100,
  failed: 0,
};

export default function Stepper({ job, loading, elapsedSeconds = 0 }) {
  const isJobActive = Boolean((job && job.status !== 'completed' && job.status !== 'failed') || loading);

  const getStageState = (stageId, index) => {
    // 1. If job is null or undefined, default sample draft view: show all completed
    if (!job && !loading) {
      return 'completed';
    }

    // 2. If job completed
    if (job?.status === 'completed') {
      return 'completed';
    }

    // 3. If job failed
    if (job?.status === 'failed') {
      const failedIdx = STAGES.findIndex((s) => s.id === job.error_stage);
      if (failedIdx !== -1) {
        if (index < failedIdx) return 'completed';
        if (index === failedIdx) return 'failed';
        return 'pending';
      }
      return 'failed';
    }

    // 4. Initial loading/pending state before job status updates
    if (!job || job.status === 'pending') {
      return index === 0 ? 'active' : 'pending';
    }

    // 5. Normal active job step sequence calculation
    const activeIdx = STAGES.findIndex((s) => s.id === job.status);
    if (activeIdx !== -1) {
      if (index < activeIdx) return 'completed';
      if (index === activeIdx) return 'active';
      return 'pending';
    }

    return 'pending';
  };

  const handleStepClick = (stageId) => {
    let targetEl = null;
    if (stageId === 'writing_article') {
      targetEl = document.querySelector('.article-main-card');
    } else if (stageId === 'generating_seo') {
      targetEl = document.querySelector('#seo-metadata-card');
    } else if (
      stageId === 'generating_image_prompts' ||
      stageId === 'generating_images' ||
      stageId === 'uploading_images'
    ) {
      targetEl = document.querySelector('.generated-images-block');
    } else if (
      stageId === 'publishing_wordpress' ||
      stageId === 'publishing_pinterest'
    ) {
      targetEl = document.querySelector('#publishing-status-card');
    }

    if (targetEl) {
      targetEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  };

  const formatTimer = (totalSec) => {
    const mins = Math.floor(totalSec / 60);
    const secs = totalSec % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const currentStageObj = STAGES.find((s) => s.id === job?.status) || STAGES[0];
  const activePercentage = job?.status ? (STAGE_PERCENTAGES[job.status] || 14) : (loading ? 14 : 100);
  const activeDescription = job?.status
    ? (STAGE_DESCRIPTIONS[job.status] || 'Processing pipeline stage...')
    : 'Initializing pipeline execution...';

  return (
    <section className="stepper-section" aria-label="Pipeline Progress Stepper">
      {/* 7-Stage Connected Stepper Container */}
      <div className="stepper-container">
        <div className="stepper-line" />
        {STAGES.map((s, idx) => {
          const state = getStageState(s.id, idx);
          return (
            <div
              key={s.id}
              className={`stepper-step ${state}`}
              id={`stepper-step-${s.id}`}
              onClick={() => handleStepClick(s.id)}
              style={{ cursor: 'pointer' }}
              title={`Stage ${s.number}: ${s.name} (${state}) — click to jump to section`}
            >
              <div className="step-circle">
                {state === 'completed' ? (
                  '✓'
                ) : state === 'failed' ? (
                  '✕'
                ) : state === 'active' ? (
                  <span className="active-spinner-icon" aria-hidden="true" />
                ) : (
                  s.number
                )}
              </div>
              <div className="step-label">{s.name}</div>
            </div>
          );
        })}
      </div>

      {/* Live Pipeline Progress Banner when job is running */}
      {isJobActive && (
        <div className="pipeline-progress-banner" aria-live="polite">
          <div className="progress-banner-header">
            <div className="progress-banner-left">
              <span className="live-status-pill">
                <span className="status-dot-pulsing" />
                Pipeline Active
              </span>
              <span className="progress-stage-title">
                Stage {currentStageObj.number} of 7: <strong>{currentStageObj.name}</strong>
              </span>
            </div>
            <div className="progress-banner-right">
              <span className="progress-timer">⏱️ {formatTimer(elapsedSeconds)} elapsed</span>
              <span className="progress-percent-badge">{activePercentage}%</span>
            </div>
          </div>

          <div className="progress-bar-track">
            <div
              className="progress-bar-fill"
              style={{ width: `${activePercentage}%` }}
            />
          </div>

          <div className="progress-banner-footer">
            <span className="progress-description-text">{activeDescription}</span>
          </div>
        </div>
      )}
    </section>
  );
}
