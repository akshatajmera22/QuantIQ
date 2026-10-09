# QuantIQ — AI-Powered Data Analyst

QuantIQ is an AI-powered data analytics application that enables users to
analyze datasets using natural language. It combines AI-assisted SQL
generation, database connectivity, and automated insights in one platform.

## Features

- **AI Data Analysis:** Ask questions about your data in natural language.
- **CSV & Excel:** Upload structured datasets for analysis.
- **MySQL Integration:** Connect to databases and query data.
- **AI Insights:** Generate explanations from query results.
- **SQL Security:** Validate queries and restrict access to sensitive data.
- **Private Login:** Secure access through administrator authentication.
- **Dynamic Analysis:** Work with different datasets without hardcoded questions.

## Tech Stack

- **Frontend:** React, Vite
- **Backend:** Python, FastAPI
- **Data Processing:** Pandas, NumPy
- **Query Engine:** DuckDB
- **Database:** MySQL
- **AI:** Google Gemini API
- **Deployment:** Vercel

## Getting Started

### 1. Clone the repository

    git clone https://github.com/akshatajmera22/QuantIQ.git
    cd QuantIQ

### 2. Install backend dependencies

    python -m venv venv
    .\venv\Scripts\Activate.ps1
    pip install -r requirements.txt

### 3. Configure environment variables

Create a `.env` file in the project root:

    GEMINI_API_KEY=your_api_key
    QUANTIQ_LOGIN_USERNAME=your_username
    QUANTIQ_LOGIN_PASSWORD=your_password
    QUANTIQ_AUTH_SECRET=your_random_secret

Never commit your `.env` file or expose credentials.

### 4. Start the backend

    uvicorn main:app --reload

### 5. Start the frontend

    cd frontend
    npm install
    npm run dev

Configure `VITE_API_URL` to point to your backend.

## Live Demo

**Application:** https://quant-iq-mu.vercel.app

## Author

**Akshat Ajmera**

GitHub: https://github.com/akshatajmera22

---

*QuantIQ — Turning data into insights with AI.*