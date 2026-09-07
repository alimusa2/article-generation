import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from app.main import app
from app.models.schemas import JobStatus

client = TestClient(app)


def test_health_endpoint():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_pipeline_generate_and_get_job():
    # Mock _execute_pipeline to prevent real API calls during test
    with patch("app.routers.pipeline._execute_pipeline", new_callable=AsyncMock):
        create_resp = client.post("/pipeline/generate", json={"title": "Rustic Stone Fireplace Inspiration for 2026"})
        assert create_resp.status_code == 200
        data = create_resp.json()
        assert "job_id" in data
        assert data["title"] == "Rustic Stone Fireplace Inspiration for 2026"
        assert data["status"] == "pending"

        job_id = data["job_id"]

        # Fetch job by ID
        get_resp = client.get(f"/pipeline/jobs/{job_id}")
        assert get_resp.status_code == 200
        job_data = get_resp.json()
        assert job_data["job_id"] == job_id

        # List all jobs
        list_resp = client.get("/pipeline/jobs")
        assert list_resp.status_code == 200
        jobs = list_resp.json()
        assert any(j["job_id"] == job_id for j in jobs)


def test_update_job_seo():
    with patch("app.routers.pipeline._execute_pipeline", new_callable=AsyncMock):
        create_resp = client.post("/pipeline/generate", json={"title": "Modern Fireplace Design"})
        job_id = create_resp.json()["job_id"]

        seo_payload = {
            "seo_title": "Updated Modern Fireplace Design 2026",
            "meta_description": "New meta description for testing.",
            "url_slug": "updated-modern-fireplace-2026",
            "focus_keyphrase": "modern fireplace",
            "secondary_keywords": ["living room", "stone"],
        }
        patch_resp = client.patch(f"/pipeline/jobs/{job_id}/seo", json=seo_payload)
        assert patch_resp.status_code == 200
        assert patch_resp.json()["status"] == "updated"

        # Verify job was updated
        get_resp = client.get(f"/pipeline/jobs/{job_id}")
        assert get_resp.json()["seo"]["seo_title"] == "Updated Modern Fireplace Design 2026"


def test_submit_job_feedback():
    with patch("app.routers.pipeline._execute_pipeline", new_callable=AsyncMock):
        create_resp = client.post("/pipeline/generate", json={"title": "Cozy Living Room Fireplace"})
        job_id = create_resp.json()["job_id"]

        feedback_payload = {
            "notes": "Please regenerate image 3 to feature more wooden beam details.",
            "category": "images",
        }
        fb_resp = client.post(f"/pipeline/jobs/{job_id}/feedback", json=feedback_payload)
        assert fb_resp.status_code == 200
        assert fb_resp.json()["status"] == "recorded"
        assert fb_resp.json()["feedback_count"] == 1


def test_publish_job_post():
    with patch("app.routers.pipeline._execute_pipeline", new_callable=AsyncMock):
        create_resp = client.post("/pipeline/generate", json={"title": "Rustic Stone Fireplace"})
        job_id = create_resp.json()["job_id"]

        # If job has no WP post ID yet, expect 400
        err_resp = client.post(f"/pipeline/jobs/{job_id}/publish")
        assert err_resp.status_code == 400

        # Inject fake post ID into router job
        from app.routers.pipeline import _jobs
        _jobs[job_id].wordpress_post_id = 1234

        with patch("app.services.wordpress_service.publish_post", new_callable=AsyncMock) as mock_pub:
            mock_pub.return_value = {"id": 1234, "link": "https://furnish-luxe.com/rustic-stone-fireplace"}
            pub_resp = client.post(f"/pipeline/jobs/{job_id}/publish")
            assert pub_resp.status_code == 200
            assert pub_resp.json()["status"] == "published"
            assert pub_resp.json()["link"] == "https://furnish-luxe.com/rustic-stone-fireplace"
