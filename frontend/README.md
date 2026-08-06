# Suproc Listing Optimizer — Production Frontend (React + Vite)

A production-ready React application for Suproc Marketplace's Listing Optimizer agent. It communicates exclusively with the backend via `POST /api/analyze` to score B2B listings, extract structured specifications, run zero-trust grounding sanitization, and scan competitor marketplace data.

---

## 🛠 Tech Stack

- **Framework**: React 18 + Vite
- **Styling**: Modern B2B Slate & Blueprint CSS Design System
- **API Client**: Standard `fetch` (Zero client-side LLM calls, zero browser secrets)

---

## 🚀 Setup & Local Development

### 1. Install Dependencies
```bash
cd frontend
npm install
```

### 2. Environment Variables
Create a `.env` or `.env.local` file in the `frontend` directory:
```env
VITE_API_URL=http://localhost:8000
```

### 3. Run Dev Server
```bash
npm run dev
```
Open `http://localhost:5173` in your browser. Ensure the FastAPI backend server is running on `http://localhost:8000`.

---

## 📦 Production Build & Testing

Validate that the static production bundle compiles without warnings:
```bash
npm run build
```
This outputs static assets into `frontend/dist`.

Preview the built application locally:
```bash
npm run preview
```

---

## ☁️ Deployment (Vercel)

Deploying the frontend to **Vercel**:

1. Push your repository to GitHub / GitLab / Bitbucket.
2. Import project into Vercel and set Root Directory to `frontend`.
3. Configure the environment variable in Vercel settings:
   - `VITE_API_URL`: The public HTTPS URL of your FastAPI backend (e.g. `https://your-backend.onrender.com`).
4. Click **Deploy**.
