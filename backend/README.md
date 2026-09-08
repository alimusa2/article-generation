# Article Automation Pipeline (FastAPI) & React Dashboard

Exact, faithful port of the n8n "article generation fireplace" workflow (`article genertion fireplace.json`) into a Python FastAPI backend and a React + Vite dashboard.

---

## 1. Summary of Changes vs. Original n8n JSON

Per project guidelines, this port preserves the exact nodes, execution sequence, parameters, payload shapes, and header names byte-for-byte. The **only** deviation from the original JSON is credential loading:

- **Environment-based credentials**: All live API tokens previously hardcoded in the n8n export (Cloudflare Workers AI bearer token, Pinterest bearer token) as well as named n8n credentials (Gemini, OpenRouter, WordPress, Cloudinary) are loaded via a `.env` file rather than hardcoded in the codebase.
- **Scaffold guards removed**: Any extraneous quota guards (such as `_NeuronBudgetTracker` or `DailyQuotaExceeded` previously drafted in the scaffold) have been completely removed to avoid adding artificial rate limits or guards absent in the original n8n JSON.
- **Sequential image generation**: Enforced batch size 1 with an exact 2000ms pause between calls to Cloudflare Workers AI, mirroring n8n's `"batchSize": 1, "batchInterval": 2000`.
- **Retry Asymmetry Preserved**: `@external_call_retry` is applied **only** to the Gemini article writing step (`write the article` node with `retryOnFail: true`). All other steps operate without retry decorators, mirroring the exact asymmetry in the n8n JSON.

---

## 2. "Flagged, Not Fixed" Items

The following anomalies, inconsistencies, and potential bugs in the original n8n workflow have been preserved exactly as-is per instruction, with clear inline comments in the code:

| # | Item | Location in n8n JSON | Preserved Behavior | Why It's Worth Reviewing |
|---|---|---|---|---|
| 1 | **`featured_image_id` parameter** | Node `upload node` (WordPress post creation) | Sent as `"featured_image_id": featured_media_id` in post creation payload | Standard WordPress Core REST API v2 expects the field name `featured_media` (integer ID). `featured_image_id` will be ignored by standard WordPress unless a custom plugin or hook maps it. |
| 2 | **Post Title ignores generated SEO Title** | Node `upload node` vs `Code in JavaScript2` | Post creation sets `"title": $('On form submission').item.json.Title` | In `Code in JavaScript2`, the workflow extracts `seoTitle = seoObj.title`, but in `upload node` it discards that value and passes the original user input title instead. |
| 3 | **SEO Key naming mismatch** | `generate seo meta data` vs `Code in JavaScript2` | Handled via multi-step fallback extracting both `seo_title` and `title` | The system prompt instructs the LLM to output key `"seo_title"`, but `Code in JavaScript2` accesses `seoObj.title`. |
| 4 | **Pinterest Sandbox Endpoint** | Node `HTTP Request1` | Kept as `https://api-sandbox.pinterest.com/v5/pins` | Production Pinterest uses `https://api.pinterest.com/v5/pins`. Pins submitted to sandbox will not appear on a live production Pinterest profile. |
| 5 | **Hardcoded Pinterest Board ID** | Node `HTTP Request1` | Defaulted to `"1086423178800607052"` with env override | Board ID was hardcoded directly in the n8n HTTP Request JSON body string. |
| 6 | **Pinterest Pin Fan-out per image** | Node `Code in JavaScript1` -> `HTTP Request1` | Creates 1 pin per Cloudinary image (8 pins per article) | For every generated image in the article, a separate pin is created with the same article link and title, rather than pinning just the featured hero image. |
| 7 | **Pinterest Image URL Source** | Node `Code in JavaScript1` | Uses raw Cloudinary URL (`secure_url || url`), NOT `avif_url` | Cloudinary returns `secure_url`, transformed to `avif_url` for WordPress. Pinterest node strictly receives the raw Cloudinary URL from `Code in JavaScript1`. |
| 8 | **Pinterest Description Parsing Unguarded** | Node `HTTP Request1` | Single unguarded `json.loads` without fallbacks | Unlike the robust multi-step parser used for WordPress SEO, Pinterest node uses an unhandled `JSON.parse(...)` expression that raises on malformed input. |
| 9 | **Cloudinary `public_id` character replacement** | Node `Upload to Cloudinary` | Replicated as `re.sub(r'[^a-z0-9]', '-', title.lower())` | Uses character-by-character regex substitution which can produce multiple consecutive hyphens (e.g. `"a - b"` becomes `"a---b"`) instead of standard slugification. |
| 10 | **Dead-end `HTML1` node** | Node `HTML1` | Noted in architecture | Connected to `write the article` in n8n with no outgoing connections (likely used for manual inspection during workflow creation). |
| 11 | **Background Polling Scoping** | FastAPI Pipeline Layer | Strictly scoped job-status wrapper (`pending` -> `completed`) | Authorized exception for web API. Wraps the pipeline without altering order, payloads, parameters, or retry asymmetry inside any stage. |

---

## 3. Pipeline Architecture

```
User submits Title
   │
   ▼
1. Gemini (gemini-3.5-flash)
   └── Generates complete HTML article with 8 H2s and 8 [image space] placeholders
   │   [retryOnFail: true, 3 attempts]
   ▼
2. OpenRouter (openrouter/free)
   └── Generates SEO Metadata (JSON object: title, meta_description, slug, keyphrases)
   │
   ▼
3. OpenRouter (openrouter/free)
   └── Generates exactly 8 image prompts matching article sections
   │
   ▼
4. Cloudflare Workers AI (@cf/black-forest-labs/flux-1-schnell, steps: 4)
   └── Sequential image generation (batchSize: 1, 2000ms delay between images)
   │
   ▼
5. Cloudinary & WordPress Media
   ├── Upload PNG to Cloudinary -> get secure_url
   ├── Rewrite URL with f_avif delivery transform
   ├── Download AVIF binary
   └── Upload to WordPress Media (/wp-json/wp/v2/media) with Content-Type: image/avif
   │
   ▼
6. WordPress Draft Post (/wp-json/wp/v2/posts)
   ├── Replace [image space] placeholders with responsive <figure><img ...>
   ├── Apply responsive style catch-all to any <img> tags
   └── Create draft post with meta tags and featured_image_id
   │
   ▼
7. Pinterest Sandbox API (api-sandbox.pinterest.com/v5/pins)
   └── Fan-out: creates a pin for each Cloudinary image pointing to the WP post link
```

---

## 4. Setup & Running

### Backend

```bash
cd article-pipeline
python -m venv venv && source venv/bin/activate  # (On Windows: venv\Scripts\activate)
pip install -r requirements.txt
cp .env.example .env   # fill in your keys
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Visit `http://localhost:5173` to access the generation dashboard.
