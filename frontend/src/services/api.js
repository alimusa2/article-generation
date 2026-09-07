/**
 * API client for interacting with the FastAPI pipeline backend.
 */

export async function generateArticle(title) {
  const res = await fetch('/pipeline/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to trigger article pipeline');
  }

  return res.json();
}

export async function getJobStatus(jobId) {
  const res = await fetch(`/pipeline/jobs/${jobId}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to fetch job status');
  }
  return res.json();
}

export async function listJobs() {
  const res = await fetch('/pipeline/jobs');
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to list jobs');
  }
  return res.json();
}

export async function publishJobPost(jobId) {
  const res = await fetch(`/pipeline/jobs/${jobId}/publish`, {
    method: 'POST',
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to publish post to WordPress');
  }
  return res.json();
}

export async function updateJobSeo(jobId, seoData) {
  const res = await fetch(`/pipeline/jobs/${jobId}/seo`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(seoData),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to update SEO metadata');
  }
  return res.json();
}

export async function submitJobFeedback(jobId, feedbackData) {
  const res = await fetch(`/pipeline/jobs/${jobId}/feedback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(feedbackData),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to submit feedback');
  }
  return res.json();
}

export async function checkBackendHealth() {
  const res = await fetch('/health');
  if (!res.ok) {
    throw new Error('Backend health check failed');
  }
  return res.json();
}

