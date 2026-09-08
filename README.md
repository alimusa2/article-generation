# Furnish Luxe — Editorial Article & Asset Automation

A production-grade article generation, SEO optimization, asset creation, and publishing pipeline for [furnish-luxe.com](https://furnish-luxe.com), developed by **Siddiqui Innovations**.

## Monorepo Architecture

```
Article/
├── package.json                # Root package with unified scripts
├── backend/                    # Python FastAPI service
│   ├── app/                    # Application source code
│   │   ├── config.py           # Settings & API keys
│   │   ├── main.py             # FastAPI entrypoint
│   │   ├── models/             # Pydantic data schemas
│   │   ├── routers/            # Health & pipeline routes
│   │   ├── services/           # LLM, Image gen, Cloudinary, WP, Pinterest
│   │   └── utils/              # Parsing & retry logic
│   ├── tests/                  # Automated pytest suite (15 tests)
│   ├── requirements.txt
│   └── README.md
│
├── frontend/                   # React + Vite application
│   ├── src/
│   │   ├── assets/             # Brand identity & mockup assets
│   │   ├── components/         # Modular UI components
│   │   ├── constants/          # Pipeline stages & presets
│   │   ├── services/           # Backend API client
│   │   ├── App.jsx             # Top-level orchestrator
│   │   └── index.css           # Editorial styling & tokens
│   ├── package.json
│   ├── vite.config.js
│   └── README.md
│
├── workflows/                  # Workflow definitions
│   └── article_generation_fireplace.json # Original n8n automation definition
│
├── .gitignore                  # Unified monorepo gitignore
└── README.md                   # Monorepo documentation
```

---

## Quick Start

### Start Full Stack (Backend + Frontend)
From the root directory:
```bash
npm install
npm run dev
```
Running `npm run dev` automatically launches both services concurrently:
- **Backend API**: `http://localhost:8000` (FastAPI + Uvicorn)
- **Frontend App**: `http://localhost:5173` (Vite + React)
- **Interactive Swagger Docs**: `http://localhost:8000/docs`

When you press `Ctrl+C`, both services terminate cleanly together without leaving orphaned background processes.

---

### Individual Service Commands

#### Backend Only
```bash
# Run tests
npm run test:backend

# Run backend service
npm run dev:backend
```

#### Frontend Only
```bash
# Build production bundle
npm run build

# Run frontend UI only
npm run dev:frontend
```

---

## Automated Pipeline Stages
1. **Writing Article**: Google Gemini (`gemini-3.5-flash`) generates deep, long-form editorial content with `[IMAGE_1]` to `[IMAGE_8]` placeholders.
2. **SEO Metadata**: OpenRouter LLM (`openrouter/free`) generates focus keyphrase, SEO title, meta description, and URL slug.
3. **Image Prompts**: OpenRouter LLM creates 8 unique, photorealistic interior photography prompts.
4. **Generating Images**: Cloudflare Workers AI (`@cf/black-forest-labs/flux-1-schnell`) generates 8 images sequentially with exact 2000ms intervals.
5. **Uploading Media**: Uploads images to Cloudinary, formats WordPress AVIF media files, and generates raw Cloudinary URLs for Pinterest.
6. **Publishing Draft**: Creates a draft post on WordPress REST API with embedded AVIF image figures.
7. **Pinning**: Creates 8 rich pins in the Pinterest Sandbox API referencing the raw Cloudinary image URLs and meta description.
