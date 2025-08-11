# Atomberg Smart Fan Share of Voice (SoV) Analysis

A data-driven, AI-powered framework to quantify and visualize Atomberg’s Share of Voice in the smart fan market, leveraging web search, content analysis, and sentiment assessment.

---

## Overview

This project implements a scalable, rate-limit-aware pipeline using Python, Flask backend, and JavaScript frontend to monitor and analyze Atomberg’s presence across online content. It combines web search APIs, large language models, and natural language processing tools to provide insights and actionable recommendations.

---

## Tech Stack

### Backend
- **Python 3.x**
- **Flask** — REST API server
- **LangChain + LangGraph** — Workflow orchestration
- **Google Gemini 2.5 Flash** — NLP content analysis (via langchain-google-genai)
- **Tavily Search API** — Web content fetching
- **TextBlob** — Sentiment analysis
- **Custom Rate Limiters** — To respect free-tier API quotas
- **Pandas / NumPy** — Data processing

### Frontend
- **HTML5/CSS3/JavaScript**
- **Chart.js** — Visualization of metrics



## Setup & Deployment

### 1. Clone the Repository
```bash
git clone https://github.com/PriyadharsanBalaji/Project_Atomberg.git
cd atomberg-sov-analysis

2. Create and Activate Virtual Environment
bash
python -m venv venv
source venv/bin/activate   # On Windows: venv\Scripts\activate

3. Install Dependencies
bash
pip install -r requirements.txt

4. Configure API Keys
Duplicate .env.template as .env


Add your API keys:

GEMINI_API_KEY=your_gemini_api_key_here
TAVILY_API_KEY=your_tavily_api_key_here
FLASK_SECRET_KEY=your_flask_secret_key_here


5. Run the Backend Server

bash
python app.py
Open http://localhost:5000 in your browser to access the dashboard or use API endpoints at http://localhost:5000/.

Code Structure

atomberg-sov/
│
├── agent.py        # Core AI workflow, rate-limited content fetching & analysis
├── app.py          # Flask API exposing analysis endpoints
├── config.py       # Configuration (API keys, rate limiters)
├── requirements.txt
├── .env            # Environment variables (API keys)
│
├── templates/      # HTML frontend
│   └── index.html
│
└── static/
    ├── css/        # Stylesheets
    │   └── style.css
    └── js/         # JavaScript Logic
        └── app.js
