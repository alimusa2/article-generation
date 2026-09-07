import React from 'react';
import { STAGES } from '../constants/pipeline';

export default function Stepper({ job }) {
  const getStageState = (stageId, index) => {
    if (!job) {
      if (index === 0) return 'completed';
      if (index === 1) return 'active';
      return 'pending';
    }

    if (job.status === 'failed') {
      if (job.error_stage === stageId) return 'failed';
    }
    if (job.status === 'completed') return 'completed';

    const currentIndex = STAGES.findIndex((s) => s.id === job.status);
    if (currentIndex === -1) return 'pending';

    if (index < currentIndex) return 'completed';
    if (index === currentIndex) return 'active';
    return 'pending';
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
