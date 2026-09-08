import React, { useState, useEffect, useRef } from 'react';
import Navbar from './components/Navbar';
import Stepper from './components/Stepper';
import ArticleReview from './components/ArticleReview';
import SeoMetadataCard from './components/SeoMetadataCard';
import PublishingStatusCard from './components/PublishingStatusCard';
import ContentDetailsCard from './components/ContentDetailsCard';
import ActionButtons from './components/ActionButtons';
import NewDraftModal from './components/NewDraftModal';
import ImageGalleryModal from './components/ImageGalleryModal';
import RequestChangesModal from './components/RequestChangesModal';

import { DEFAULT_ARTICLE } from './constants/pipeline';
import {
  generateArticle,
  getJobStatus,
  publishJobPost,
  updateJobSeo,
  submitJobFeedback,
} from './services/api';

import heroFireplace from './assets/hero-fireplace.jpg';
import thumb1 from './assets/thumb-1.jpg';
import thumb2 from './assets/thumb-2.jpg';
import thumb3 from './assets/thumb-3.jpg';
import thumb4 from './assets/thumb-4.jpg';
import thumb5 from './assets/thumb-5.jpg';

const MOCKUP_THUMBNAILS = [thumb1, thumb2, thumb3, thumb4, thumb5];

export default function App() {
  const [title, setTitle] = useState(DEFAULT_ARTICLE.title);
  const [jobId, setJobId] = useState(null);
  const [job, setJob] = useState(null);
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState(null);

  // Modals State
  const [showRunModal, setShowRunModal] = useState(false);
  const [showGalleryModal, setShowGalleryModal] = useState(false);
  const [showFeedbackModal, setShowFeedbackModal] = useState(false);
  const [selectedGalleryIndex, setSelectedGalleryIndex] = useState(0);
  const [isSubmittingFeedback, setIsSubmittingFeedback] = useState(false);
  const [customHeroUrl, setCustomHeroUrl] = useState(null);

  // Publishing & Approval State
  const [isPublishing, setIsPublishing] = useState(false);
  const [isPublished, setIsPublished] = useState(false);
  const [lastSavedAt, setLastSavedAt] = useState(DEFAULT_ARTICLE.lastSavedAt);
  const [updatedAt, setUpdatedAt] = useState(DEFAULT_ARTICLE.updatedAt);

  // SEO Form State
  const [seoTitle, setSeoTitle] = useState(DEFAULT_ARTICLE.seoTitle);
  const [metaDesc, setMetaDesc] = useState(DEFAULT_ARTICLE.metaDescription);
  const [focusKeyword, setFocusKeyword] = useState(DEFAULT_ARTICLE.focusKeyword);
  const [slug, setSlug] = useState(DEFAULT_ARTICLE.slug);

  const pollIntervalRef = useRef(null);

  // Synchronize SEO state when background job produces metadata
  useEffect(() => {
    if (job?.seo) {
      if (job.seo.seo_title) setSeoTitle(job.seo.seo_title);
      if (job.seo.meta_description) setMetaDesc(job.seo.meta_description);
      if (job.seo.focus_keyphrase) setFocusKeyword(job.seo.focus_keyphrase);
      if (job.seo.url_slug) setSlug(job.seo.url_slug);
    }
    if (job?.wordpress_post_link) {
      const now = new Date();
      const timeStr = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      setLastSavedAt(timeStr);
      setUpdatedAt(`May 9, 2026 ${timeStr}`);
    }
  }, [job]);

  // Background job polling
  useEffect(() => {
    if (!jobId) return;

    const poll = async () => {
      try {
        const data = await getJobStatus(jobId);
        setJob(data);

        if (data.status === 'completed' || data.status === 'failed') {
          setLoading(false);
          clearInterval(pollIntervalRef.current);
          if (data.status === 'failed') {
            setErrorMessage(`Pipeline failed at stage '${data.error_stage || 'unknown'}': ${data.error}`);
          }
        }
      } catch (err) {
        console.error("Polling error:", err);
      }
    };

    poll();
    pollIntervalRef.current = setInterval(poll, 1500);
    return () => clearInterval(pollIntervalRef.current);
  }, [jobId]);

  const handleStartGeneration = async (newTopic) => {
    setTitle(newTopic);
    setLoading(true);
    setErrorMessage(null);
    setShowRunModal(false);
    setIsPublished(false);
    setCustomHeroUrl(null);

    try {
      const data = await generateArticle(newTopic);
      setJobId(data.job_id);
      setJob(data);
    } catch (err) {
      setErrorMessage(err.message);
      setLoading(false);
    }
  };

  const handleSaveSeo = async (updatedSeo) => {
    const now = new Date();
    const timeStr = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    setLastSavedAt(timeStr);
    setUpdatedAt(`May 9, 2026 ${timeStr}`);

    if (jobId) {
      try {
        await updateJobSeo(jobId, updatedSeo);
      } catch (err) {
        console.warn("Could not synchronize SEO to backend job:", err);
      }
    }
  };

  const handleApprovePublish = async () => {
    if (job?.job_id && job?.wordpress_post_id) {
      setIsPublishing(true);
      try {
        const res = await publishJobPost(job.job_id);
        setIsPublished(true);
        if (res.link) {
          window.open(res.link, '_blank');
        }
      } catch (err) {
        setErrorMessage(err.message || 'Failed to publish post to WordPress');
      } finally {
        setIsPublishing(false);
      }
    } else if (job?.wordpress_post_link) {
      window.open(job.wordpress_post_link, '_blank');
    } else {
      alert("Post is marked approved. When a generation pipeline completes with valid WordPress credentials, this will publish the post live to WordPress.");
    }
  };

  const handleSubmitFeedback = async (feedbackData) => {
    setIsSubmittingFeedback(true);
    try {
      if (jobId) {
        await submitJobFeedback(jobId, feedbackData);
      }
      setShowFeedbackModal(false);
      alert(`Revision request recorded for [${feedbackData.category}]: "${feedbackData.notes}". The draft has been flagged.`);
    } catch (err) {
      alert(`Feedback recorded locally: "${feedbackData.notes}".`);
      setShowFeedbackModal(false);
    } finally {
      setIsSubmittingFeedback(false);
    }
  };

  // Content word count & read time
  const rawText = job?.formatted_content || job?.article_html || "";
  const wordCount = rawText
    ? rawText.replace(/<[^>]*>/g, ' ').split(/\s+/).filter(Boolean).length
    : DEFAULT_ARTICLE.wordCount;
  const readTimeMin = Math.max(1, Math.round(wordCount / 200));

  // Resolved image assets
  const currentHeroImage = customHeroUrl || (
    job?.images && job.images.length > 0
      ? (job.images[0].avif_url || job.images[0].cloudinary_url)
      : heroFireplace
  );

  const currentThumbnails = job?.images && job.images.length > 0
    ? job.images.slice(0, 5).map((img) => img.avif_url || img.cloudinary_url)
    : MOCKUP_THUMBNAILS;

  // Complete set of images for modal gallery
  const allGalleryImages = job?.images && job.images.length > 0
    ? job.images
    : [heroFireplace, ...MOCKUP_THUMBNAILS, thumb2, thumb3];

  return (
    <div className="editorial-app-root">
      {/* Top Navbar */}
      <Navbar
        onOpenNewDraft={() => setShowRunModal(true)}
        loading={loading}
      />

      {/* 7-Stage Connected Stepper */}
      <Stepper job={job} />

      {/* Error Notice */}
      {errorMessage && (
        <div style={{ maxWidth: '1440px', margin: '14px auto 0', padding: '0 40px' }}>
          <div style={{
            backgroundColor: '#fef2f2',
            border: '1px solid #fecaca',
            padding: '10px 16px',
            borderRadius: '6px',
            color: '#991b1b',
            fontSize: '0.85rem'
          }}>
            {errorMessage}
          </div>
        </div>
      )}

      {/* Main Two-Column Editorial Review Desk */}
      <main className="main-layout-container">
        {/* Left Column: Article Document Canvas */}
        <ArticleReview
          title={title}
          heroImage={currentHeroImage}
          thumbnails={currentThumbnails}
          job={job}
          lastSavedAt={lastSavedAt}
          defaultContent={DEFAULT_ARTICLE}
          onViewAllImages={() => {
            setSelectedGalleryIndex(0);
            setShowGalleryModal(true);
          }}
          onSelectThumbnail={(idx) => {
            setSelectedGalleryIndex(idx);
            setShowGalleryModal(true);
          }}
        />

        {/* Right Column: Sidebar Panels */}
        <aside className="sidebar-column">
          <SeoMetadataCard
            seoTitle={seoTitle}
            setSeoTitle={setSeoTitle}
            metaDesc={metaDesc}
            setMetaDesc={setMetaDesc}
            focusKeyword={focusKeyword}
            setFocusKeyword={setFocusKeyword}
            slug={slug}
            setSlug={setSlug}
            onSaveSeo={handleSaveSeo}
          />

          <PublishingStatusCard
            wordpressPostLink={job?.wordpress_post_link}
            isPublished={isPublished}
            wordpressPostId={job?.wordpress_post_id}
          />

          <ContentDetailsCard
            wordCount={wordCount}
            readTimeMin={readTimeMin}
            createdAt={DEFAULT_ARTICLE.createdAt}
            updatedAt={updatedAt}
          />

          <ActionButtons
            onPublish={handleApprovePublish}
            isPublishing={isPublishing}
            isPublished={isPublished}
            onRequestChanges={() => setShowFeedbackModal(true)}
          />
        </aside>
      </main>

      {/* New Draft Trigger Modal */}
      <NewDraftModal
        isOpen={showRunModal}
        onClose={() => setShowRunModal(false)}
        onSubmit={handleStartGeneration}
        loading={loading}
        currentTitle={title}
      />

      {/* All 8 Generated Visual Assets Modal */}
      <ImageGalleryModal
        isOpen={showGalleryModal}
        onClose={() => setShowGalleryModal(false)}
        images={allGalleryImages}
        selectedIndex={selectedGalleryIndex}
        onSelectHero={(url) => {
          setCustomHeroUrl(url);
          setShowGalleryModal(false);
        }}
      />

      {/* Editorial Feedback / Request Changes Modal */}
      <RequestChangesModal
        isOpen={showFeedbackModal}
        onClose={() => setShowFeedbackModal(false)}
        onSubmit={handleSubmitFeedback}
        isSubmitting={isSubmittingFeedback}
      />
    </div>
  );
}
