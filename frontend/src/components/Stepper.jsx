import React from 'react';
import { STAGES } from '../constants/pipeline';

export default function Stepper({ job }) {
  const getStageState = (stageId, index) => {
    // 1. If job is marked completed, all stages are completed
    if (job?.status === 'completed') {
      return 'completed';
    }

    // 2. If job failed at a specific stage
    if (job?.status === 'failed') {
      const failedIdx = STAGES.findIndex((s) => s.id === job.error_stage);
      if (failedIdx !== -1) {
        if (index < failedIdx) return 'completed';
        if (index === failedIdx) return 'failed';
        return 'pending';
      }
    }

    const currentStatusIdx = job?.status ? STAGES.findIndex((s) => s.id === job.status) : -1;

    // 3. Determine completion by data presence or status progress
    let isCompleted = false;

    if (currentStatusIdx !== -1 && index < currentStatusIdx) {
      isCompleted = true;
    } else if (job) {
      if (stageId === 'writing_article' && job.article_html) isCompleted = true;
      if (stageId === 'generating_seo' && job.seo) isCompleted = true;
      if (stageId === 'generating_image_prompts' && job.images && job.images.length > 0) isCompleted = true;
      if (stageId === 'generating_images' && job.images && job.images.some((i) => i.cloudinary_url || i.avif_url)) isCompleted = true;
      if (stageId === 'uploading_images' && job.images && job.images.some((i) => i.wordpress_media_url)) isCompleted = true;
      if (stageId === 'publishing_wordpress' && (job.wordpress_post_id || job.wordpress_post_link)) isCompleted = true;
      if (stageId === 'publishing_pinterest' && (job.pinterest_pins && job.pinterest_pins.length > 0 || job.pinterest_pin_id)) isCompleted = true;
    } else {
      // Default state when viewing pre-loaded draft before running a job
      isCompleted = true;
    }

    if (isCompleted && currentStatusIdx !== index) {
      return 'completed';
    }

    if (currentStatusIdx === index) {
      return 'active';
    }

    if (!job && index === 0) {
      return 'completed';
    }

    return isCompleted ? 'completed' : 'pending';
  };

  const handleStepClick = (stageId) => {
    let targetEl = null;
    if (stageId === 'writing_article') {
      targetEl = document.querySelector('.article-main-card');
    } else if (stageId === 'generating_seo') {
      targetEl = document.querySelector('#seo-metadata-card');
    } else if (stageId === 'generating_image_prompts' || stageId === 'generating_images' || stageId === 'uploading_images') {
      targetEl = document.querySelector('.generated-images-block');
    } else if (stageId === 'publishing_wordpress' || stageId === 'publishing_pinterest') {
      targetEl = document.querySelector('#publishing-status-card');
    }

    if (targetEl) {
      targetEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  };

  return (
    <section className="stepper-section" aria-label="Pipeline Progress Stepper">
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
                {state === 'completed' ? '✓' : s.number}
              </div>
              <div className="step-label">{s.name}</div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

