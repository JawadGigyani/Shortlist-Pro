# ShortlistPro

**Intelligent Candidate Evaluation and Recruitment Assistant**

An AI-powered recruitment platform that automates the initial screening and pre-interview stages of hiring — from resume parsing and candidate-job matching to AI-conducted initial interviews and evaluation — so HR teams can focus on the human side of recruitment.

> **BS Computer Science — Final Year Project**
> Department of Computer Science, University of Peshawar (Session 2021–2025)

[![Demo Video](https://img.shields.io/badge/Demo-YouTube-red?style=for-the-badge&logo=youtube)](https://youtu.be/inf4R8LdctA)

---

## Table of Contents

- [Overview](#overview)
- [Demo](#demo)
- [Key Features](#key-features)
- [System Architecture](#system-architecture)
- [Tech Stack](#tech-stack)
- [AI Agents (Microservices)](#ai-agents-microservices)
- [Screening Pipeline Flow](#recruitment-pipeline-flow)
- [Data Model](#data-model)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Installation & Setup](#installation--setup)
- [Environment Variables](#environment-variables)
- [Running the Application](#running-the-application)
- [API Endpoints Reference](#api-endpoints-reference)
- [Screenshots](#screenshots)
- [Authors](#authors)
- [License](#license)

---

## Overview

The early stages of recruitment — screening resumes, shortlisting candidates, and conducting initial interviews — are the most time-consuming and repetitive parts of hiring. HR teams manually sift through hundreds of resumes, make subjective shortlisting decisions, and spend hours on preliminary phone screens before a candidate ever reaches a human interviewer.

**ShortlistPro** automates this pre-screening bottleneck. The platform uses six AI agents to parse resumes into structured data, score candidates against job descriptions, generate tailored screening questions, conduct initial voice interviews through ElevenLabs Conversational AI, and evaluate interview transcripts — producing a clear PROCEED/CONDITIONAL/REJECT recommendation for each candidate. HR professionals then take over for technical, behavioral, and final interview rounds with candidates who have already been vetted by AI.

The system follows a microservices architecture where the Django web application orchestrates six independent FastAPI services, each powered by Google Gemini LLMs. This modular design enables independent scaling, clear separation of concerns, and resilience — if one agent is down, the rest of the platform continues to function.

---

## Demo

A full walkthrough of the platform is available on YouTube:

**[Watch the Demo →](https://youtu.be/inf4R8LdctA)**

---

## Key Features

- **AI Resume Parsing** — Two-stage parsing pipeline (extraction + quality control refinement) supporting PDF, DOC, and DOCX formats via Google Gemini
- **AI Candidate-Job Matching** — Scores candidates on skills, experience, and education alignment (0–100) with Interview/Maybe/Skip recommendations
- **AI Interview Question Generation** — Generates 3–4 tailored screening questions per candidate based on their resume, the job description, and matching results
- **AI Voice Interviews** — Candidates complete an AI-conducted initial interview powered by ElevenLabs Conversational AI, with full audio recording and transcript storage
- **AI Interview Evaluation** — Evaluates initial interview transcripts on Communication Clarity, Relevant Experience, and Role Interest & Fit (0–10 scale) with PROCEED/CONDITIONAL/REJECT recommendations
- **Handoff to Human Interviewers** — Candidates who pass AI screening are forwarded for human-led technical, behavioral, and final interview rounds, with per-round scoring and Zoom scheduling
- **Automated Email Communication** — Sends beautifully designed selection, rejection, and next-round invitation emails with interview portal links
- **Zoom Integration** — Automatically creates Zoom meetings for human-led interview rounds via Server-to-Server OAuth
- **OTP Email Verification** — Secure 6-digit OTP registration with rate limiting and attempt tracking
- **HR Dashboard** — Real-time analytics, activity charts, notifications, and candidate management

---

## System Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        CLIENT (Browser)                          │
│                  HR Dashboard  ·  Candidate Portal                │
└──────────────────────┬───────────────────────────────────────────┘
                       │ HTTP
┌──────────────────────▼───────────────────────────────────────────┐
│                    DJANGO WEB APP (:8000)                         │
│                                                                   │
│   Views · Models · Templates · Forms · Signals · Admin            │
│   Custom Auth (Email/Username) · OTP Verification                 │
│   ElevenLabs Service Layer · Notification System                  │
└──┬────────┬────────┬────────┬────────┬────────┬──────────────────┘
   │        │        │        │        │        │
   │ REST   │ REST   │ REST   │ REST   │ REST   │ REST
   ▼        ▼        ▼        ▼        ▼        ▼
┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐
│Resume│ │Resume│ │ Int. │ │ Int. │ │Email │ │ Zoom │
│Parser│ │Match │ │ Q's  │ │ Eval │ │Agent │ │ API  │
│:8001 │ │:8005 │ │:8004 │ │:8002 │ │:8003 │ │      │
└──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘
   │        │        │        │        │        │
   ▼        ▼        ▼        ▼        ▼        ▼
┌──────────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
│ Google Gemini│  │ElevenLabs│  │Gmail SMTP│  │ Zoom API │
│   LLM API   │  │  ConvAI  │  │  Server  │  │  OAuth   │
└──────────────┘  └──────────┘  └──────────┘  └──────────┘
        │
┌───────▼──────────────────────────────────────────────────────────┐
│                     PostgreSQL Database                            │
│          shortlistpro_db · 13 Models · 26 Migrations              │
└──────────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technologies |
|---|---|
| **Backend** | Python 3.10+, Django 5.2, FastAPI, Uvicorn |
| **AI / LLM** | Google Gemini (2.5 Flash, 1.5 Flash), LangChain, LangChain Google GenAI |
| **Voice AI** | ElevenLabs Conversational AI (WebSocket-based) |
| **Frontend** | Django Templates, Tailwind CSS (CDN), JavaScript, Chart.js |
| **Database** | PostgreSQL |
| **Email** | Gmail SMTP (App Passwords), HTML email templates |
| **Video Conferencing** | Zoom API (Server-to-Server OAuth) |
| **Document Processing** | PDFPlumber, PyMuPDF, python-docx, Docx2txt |
| **Data Validation** | Pydantic |
| **Auth** | django-registration, Custom OTP verification, Email-or-Username backend |
| **Version Control** | Git, GitHub |

---

## AI Agents (Microservices)

ShortlistPro uses six independent FastAPI microservices, each responsible for a specific stage of the initial screening process:

| # | Agent | Port | AI Model | Description |
|---|---|---|---|---|
| 1 | **Resume Parser** | 8001 | Gemini 2.5 Flash | Two-stage pipeline: initial structured extraction + quality control refinement. Supports PDF, DOC, DOCX. |
| 2 | **Interview Evaluation** | 8002 | Gemini 2.5 Flash | Evaluates interview transcripts on 3 criteria (Communication Clarity, Relevant Experience, Role Interest & Fit) with strict scoring caps based on resume match. |
| 3 | **Email Agent** | 8003 | — (SMTP) | Sends selection, rejection, OTP verification, and next-round interview invitation emails. Creates Zoom meetings for human-led rounds. |
| 4 | **Interview Questions** | 8004 | Gemini 1.5 Flash | Generates 3–4 focused screening questions tailored to the candidate's resume gaps and the job requirements. |
| 5 | **Resume Matching** | 8005 | Gemini 2.5 Flash | Screens candidates with Interview/Maybe/Skip decisions. Scores skills, experience, and education alignment (0–100). |
| 6 | **Zoom Integration** | — | — | Creates scheduled Zoom meetings via Server-to-Server OAuth for human-led interview rounds (technical, behavioral, final). |

---

## Screening Pipeline Flow

The AI handles steps 1–8 (the initial screening bottleneck). After that, qualified candidates are handed off to human interviewers for further evaluation.

```
┌─────────────────────────────────────────────────────────────┐
│                   AI-AUTOMATED SCREENING                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. Registration & OTP Verification                          │
│     HR registers → 6-digit OTP via email → account activated │
│                                                              │
│  2. Job Description Management                               │
│     HR creates job descriptions (title, department, desc.)   │
│                                                              │
│  3. Resume Upload & AI Parsing                               │
│     Upload PDF/DOCX → Resume Parser Agent extracts data      │
│     → Two-stage pipeline: extraction + quality refinement    │
│                                                              │
│  4. AI Matching                                              │
│     Resume Matching Agent scores each resume against the JD  │
│     → Interview / Maybe / Skip recommendation                │
│     → Scores: Overall, Skills, Experience, Education (0–100) │
│                                                              │
│  5. Shortlisting & Interview Questions                       │
│     HR shortlists candidates → Interview Questions Agent     │
│     auto-generates 3–4 tailored screening questions          │
│                                                              │
│  6. Email Communication                                      │
│     HR sends selection emails (with interview portal link)   │
│     or rejection emails → HTML email templates               │
│                                                              │
│  7. AI Initial Interview                                     │
│     Candidate clicks link → ElevenLabs AI voice interview    │
│     → Audio recorded, transcript stored                      │
│                                                              │
│  8. AI Evaluation                                            │
│     Evaluation Agent scores the interview transcript         │
│     → Communication, Experience, Role Fit (0–10 each)        │
│     → PROCEED / CONDITIONAL / REJECT recommendation          │
│                                                              │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼ Candidates who PROCEED
┌─────────────────────────────────────────────────────────────┐
│               HUMAN-LED INTERVIEW ROUNDS                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  9. Further Interview Rounds (conducted by humans)           │
│     Technical → Behavioral → Final                           │
│     → HR scores each round manually                          │
│     → Zoom meetings auto-created for online rounds           │
│     → Selection/rejection emails sent per round              │
│                                                              │
│  10. Onboarding                                              │
│      Eligible candidates → onboarding email sent             │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Data Model

The system uses 13 Django models. The core models support the AI-automated screening flow, while supporting models track handoff to human-led rounds:

```
User (Django built-in)
 ├── Profile (1:1) — company_name, profile_picture, office_address
 ├── EmailVerificationOTP (1:1) — 6-digit OTP, expiry, attempts
 ├── JobDescription (1:N) — title, department, description
 └── Resume (1:N) — candidate info, skills (JSON), experience (JSON), education (JSON)
      └── MatchingResult (N:1 Resume + N:1 JD) — scores, matched/missing skills, reasoning
           ├── InterviewQuestions (1:1) — AI-generated questions, categories, priorities
           ├── InterviewSession (1:N) — voice session metadata, transcript
           └── InterviewRecording (1:1) — ElevenLabs conversation data, audio, transcript
                ├── InterviewMessage (1:N) — individual conversation turns
                ├── InterviewEvaluation (1:1) — AI scores, recommendation, strengths, concerns
                ├── InterviewStage (1:N) — human-led rounds (technical, behavioral, final)
                └── CandidatePipeline (1:1) — pipeline status, onboarding eligibility

Shortlisted (linked to Resume) — legacy shortlist tracking
Interview (linked to Resume) — legacy interview scheduling
```

---

## Project Structure

```
Shortlist-Pro/
├── AI Agents/                          # FastAPI microservices
│   ├── resume_parser.py                # Port 8001 — AI resume parsing
│   ├── resume_matching.py              # Port 8005 — AI candidate-job matching
│   ├── interview_questions_agent.py    # Port 8004 — AI question generation
│   ├── interview_evaluation_agent.py   # Port 8002 — AI interview evaluation
│   ├── email_agent.py                  # Port 8003 — Email automation + SMTP
│   └── zoom_integration.py            # Zoom API meeting creation
│
├── shortlistpro/                       # Django project root
│   ├── manage.py                       # Django management script
│   ├── shortlistpro/                   # Django project settings
│   │   ├── settings.py                 # Configuration (DB, auth, static, media)
│   │   ├── urls.py                     # Root URL routing
│   │   ├── wsgi.py                     # WSGI entry point
│   │   └── asgi.py                     # ASGI entry point
│   │
│   ├── home/                           # Main Django app
│   │   ├── models.py                   # 13 database models
│   │   ├── views.py                    # All view functions (~3800 lines)
│   │   ├── urls.py                     # App URL patterns
│   │   ├── forms.py                    # Registration, profile, JD, resume forms
│   │   ├── admin.py                    # Django admin configuration
│   │   ├── backends.py                 # Email-or-Username auth backend
│   │   ├── signals.py                  # Auto-create profile on user creation
│   │   ├── utils.py                    # OTP generation, validation, formatting
│   │   ├── services_elevenlabs.py      # ElevenLabs API service layer
│   │   ├── templatetags/               # Custom template filters
│   │   │   ├── json_extras.py
│   │   │   └── resume_filters.py
│   │   ├── management/commands/        # Custom management commands
│   │   │   ├── interview_admin.py
│   │   │   ├── auto_fix_interviews.py
│   │   │   └── fix_interview_recordings.py
│   │   ├── migrations/                 # 26 database migrations
│   │   └── templates/home/             # App templates
│   │       ├── index.html              # Landing page
│   │       ├── dashboard_base.html     # Dashboard layout
│   │       ├── dashboard_home.html     # Dashboard home
│   │       ├── job_descriptions.html   # Job management
│   │       ├── resumes.html            # Resume management
│   │       ├── matching.html           # AI matching interface
│   │       ├── shortlisted.html        # Shortlisted candidates
│   │       ├── emails.html             # Email sending UI
│   │       ├── interview_dashboard.html     # Unified interview dashboard
│   │       ├── interview_pipeline.html      # Multi-round pipeline
│   │       ├── candidate_interview.html     # Candidate-facing interview portal
│   │       ├── voice_interview.html         # ElevenLabs voice interview
│   │       ├── interview_evaluation_detail.html  # Evaluation details
│   │       ├── reports.html            # Reports page
│   │       ├── profile.html            # User profile
│   │       ├── contact.html            # Contact page
│   │       ├── documentation.html      # Documentation page
│   │       ├── privacy_policy.html     # Privacy policy
│   │       └── terms_of_service.html   # Terms of service
│   │
│   └── templates/registration/         # Auth templates
│       ├── login.html
│       ├── logged_out.html
│       ├── registration_form.html
│       └── verify_otp.html
│
├── requirements.txt                    # Python dependencies
├── .gitignore                          # Git ignore rules
└── README.md                           # This file
```

---

## Prerequisites

Before setting up, ensure you have:

- **Python 3.10+**
- **PostgreSQL** (running locally or remote)
- **Git**
- **API Keys:**
  - Google Gemini API key (for AI agents)
  - ElevenLabs API key + Agent ID (for voice interviews)
  - Zoom OAuth credentials (for meeting creation)
  - Gmail App Password (for email sending)

---

## Installation & Setup

### 1. Clone the Repository

```bash
git clone https://github.com/your-username/Shortlist-Pro.git
cd Shortlist-Pro
```

### 2. Create and Activate Virtual Environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
pip install django django-registration Pillow psycopg2-binary
```

### 4. Set Up PostgreSQL Database

Create the database using `psql` or pgAdmin:

```sql
CREATE DATABASE shortlistpro_db;
```

### 5. Create the `.env` File

Create a `.env` file in the project root (`Shortlist-Pro/.env`):

```env
# Google Gemini AI
GOOGLE_API_KEY=your_google_gemini_api_key

# ElevenLabs Voice AI
ELEVENLABS_API_KEY=your_elevenlabs_api_key
ELEVENLABS_AGENT_ID=your_elevenlabs_agent_id

# Zoom API (Server-to-Server OAuth)
ZOOM_ACCOUNT_ID=your_zoom_account_id
ZOOM_CLIENT_ID=your_zoom_client_id
ZOOM_CLIENT_SECRET=your_zoom_client_secret

# Gmail SMTP (App Password)
EMAIL_ADDRESS=your_email@gmail.com
APP_PASSWORD=your_gmail_app_password
```

### 6. Run Django Migrations

```bash
cd shortlistpro
python manage.py migrate
```

### 7. Create a Superuser (optional)

```bash
python manage.py createsuperuser
```

---

## Environment Variables

| Variable | Description | Required |
|---|---|---|
| `GOOGLE_API_KEY` | Google Gemini API key for all AI agents | Yes |
| `ELEVENLABS_API_KEY` | ElevenLabs API key for voice interviews | Yes |
| `ELEVENLABS_AGENT_ID` | ElevenLabs Agent ID for interview bot | Yes |
| `ZOOM_ACCOUNT_ID` | Zoom Server-to-Server OAuth Account ID | For Zoom meetings |
| `ZOOM_CLIENT_ID` | Zoom OAuth Client ID | For Zoom meetings |
| `ZOOM_CLIENT_SECRET` | Zoom OAuth Client Secret | For Zoom meetings |
| `EMAIL_ADDRESS` | Gmail address for sending emails | Yes |
| `APP_PASSWORD` | Gmail App Password (not your regular password) | Yes |

---

## Running the Application

You need to start the Django server and each AI agent separately. Open a terminal for each:

### Terminal 1 — Django Web App

```bash
cd shortlistpro
python manage.py runserver
```
> Runs on http://localhost:8000

### Terminal 2 — Resume Parser Agent

```bash
cd "AI Agents"
python resume_parser.py
```
> Runs on http://localhost:8001

### Terminal 3 — Interview Evaluation Agent

```bash
cd "AI Agents"
python interview_evaluation_agent.py
```
> Runs on http://localhost:8002

### Terminal 4 — Email Agent

```bash
cd "AI Agents"
python email_agent.py
```
> Runs on http://localhost:8003

### Terminal 5 — Interview Questions Agent

```bash
cd "AI Agents"
python interview_questions_agent.py
```
> Runs on http://localhost:8004

### Terminal 6 — Resume Matching Agent

```bash
cd "AI Agents"
python resume_matching.py
```
> Runs on http://localhost:8005

Once all services are running, open **http://localhost:8000** in your browser.

---

## API Endpoints Reference

### FastAPI Agent Endpoints

| Agent | Endpoint | Method | Description |
|---|---|---|---|
| Resume Parser | `/parse-resumes` | POST | Parse uploaded resume file (PDF/DOC/DOCX) |
| Resume Parser | `/health` | GET | Health check |
| Resume Matching | `/match-resume` | POST | Screen resume against job description |
| Resume Matching | `/health` | GET | Health check |
| Interview Questions | `/generate-questions` | POST | Generate tailored screening questions |
| Interview Questions | `/health` | GET | Health check |
| Interview Evaluation | `/evaluate-interview` | POST | Evaluate interview transcript |
| Interview Evaluation | `/health` | GET | Health check |
| Email Agent | `/send-emails` | POST | Send selection/rejection/onboarding emails |
| Email Agent | `/send-otp` | POST | Send OTP verification email |
| Email Agent | `/health` | GET | Health check |

All FastAPI agents include auto-generated interactive docs at `/docs` (Swagger UI).

---

## Screenshots

*Screenshots of the platform can be found in the [demo video](https://youtu.be/inf4R8LdctA).*

<!-- 
Add screenshots here:
![Dashboard](screenshots/dashboard.png)
![AI Matching](screenshots/matching.png)
![Voice Interview](screenshots/voice-interview.png)
![Evaluation](screenshots/evaluation.png)
-->

---

## Authors

| Name | Role |
|---|---|
| **Muhammad Jawad** | Developer |
| **Harum Fawad** | Developer |

**Supervisor:** Dr. Fatima Tuz Zuhra
**Program:** BS Computer Science (Session 2021–2025)
**Institution:** Department of Computer Science, University of Peshawar

---

## License

This project was developed as a Final Year Project for academic purposes at the University of Peshawar. All rights reserved.
