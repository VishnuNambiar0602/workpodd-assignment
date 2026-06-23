# AutoRefund Agent Setup & Execution Guide

This system uses a **LangGraph State Machine** to automate e-commerce refund decisions with structured outputs. It performs semantic policy lookups on a **pgvector** PostgreSQL database, writes decisions to transaction logs, streams chat tokens to the customer WebSocket, and broadcasts real-time reasoning logs to the admin dashboard.

---

## Prerequisite: Running the Database

1. Ensure **Docker Desktop** is open and active on your system.
2. In your terminal, run the following command in the project root to launch the PostgreSQL database container with the `pgvector` extension:
   ```bash
   docker-compose up -d
   ```
3. Verify that the container is running and healthy:
   ```bash
   docker ps
   ```

---

## Step 1: Backend Setup

Navigate to the `backend/` directory:
```bash
cd backend
```

### 1. Create a Python Virtual Environment
We recommend utilizing a clean virtual environment:
```bash
python -m venv venv
```

Activate the environment:
- **Windows (PowerShell)**:
  ```powershell
  .\venv\Scripts\Activate.ps1
  ```
- **Windows (Command Prompt)**:
  ```cmd
  .\venv\Scripts\activate.bat
  ```

### 2. Install Dependencies
Install all required libraries including FastAPI, SQLAlchemy, pgvector, LangGraph, and sentence-transformers:
```bash
pip install -r requirements.txt
```

### 3. Environment Configuration
Create or open the `.env` file at `backend/.env` and populate it with your actual Gemini API Key:
```env
DATABASE_URL=postgresql://postgres:password@localhost:5432/refund_db
GEMINI_API_KEY=your_gemini_api_key_here
```


---

## Step 2: Database Seeding

Run the seed script to create the SQL schema, populate the 15 simulated customer profiles, insert their respective order histories, chunk the markdown refund policy, and generate vector embeddings using `all-MiniLM-L6-v2` locally:
```bash
python seed.py
```
*(This script will download the 90MB sentence-transformers model automatically on its first run.)*

---

## Step 3: Run the CLI Test Agent

You can test the LangGraph state machine directly in the terminal before running the servers:
```bash
# General usage: python test_agent.py <customer_id> "<message>"
python test_agent.py 1 "Hi, I purchased Premium Headphones (ORD-001) but the left speaker stopped working. I'd like a refund."
```
This will run the agent loop end-to-end and display the **final synthesized response** along with the **step-by-step reasoning trace logs** (Intake &rarr; Fetch Customer Context &rarr; Retrieve Policy &rarr; Reason and Decide &rarr; Execute Action &rarr; Respond).

---

## Step 4: Run the API Server

Start the FastAPI application on port `8000`:
```bash
python main.py
```
*The server will start at `http://localhost:8000` with the WebSocket endpoints listening at `/ws/chat/{customer_id}` and `/ws/admin/logs`.*

---

## Step 5: Frontend Development

Open a separate terminal window. Navigate to the `frontend/` directory:
```bash
cd frontend
```

### 1. Install Node Dependencies
```bash
npm install
```

### 2. Launch Vite Developer Server
Start the client application:
```bash
npm run dev
```
Open `http://localhost:5173` in your browser.

---

## System Architecture Flow

```
   ┌──────────────────────────────────────────────────────────┐
   │                       Customer UI                        │
   │           (Select profile #1-15 & send chat)             │
   └───────────────────────────┬──────────────────────────────┘
                               │ WS (JSON message)
                               ▼
   ┌──────────────────────────────────────────────────────────┐
   │                      FastAPI Server                      │
   │  ┌────────────────────────────────────────────────────┐  │
   │  │               LangGraph State Machine              │  │
   │  │                                                    │  │
   │  │  1. intake (extract order_id, reason)              │  │
   │  │  2. fetch_customer_context (SQL query profiles)    │  │
   │  │  3. retrieve_policy (pgvector semantic search)     │  │
   │  │  4. reason_and_decide (LLM compliance check)       │  │
   │  │  5. execute_action (Write to DB: approve/deny/esc) │  │
   │  │  6. respond (Synthesize user chat answer)          │  │
   │  └────────────────────────┬───────────────────────────┘  │
   └───────────────────────────┼──────────────────────────────┘
                               │ WS (Reasoning trace stream)
                               ▼
   ┌──────────────────────────────────────────────────────────┐
   │                     Admin Dashboard                      │
   │   (Live trace log scrolling terminal + 3D active core)   │
   └──────────────────────────────────────────────────────────┘
```

### 3D Component Note
The backend decisions are reflected in the admin panel's center orb. Built using **Three.js** and **React Three Fiber**, it moves and rotates in dynamic synchronization with your mouse cursor and reacts when hovered.

# workpodd-assignment
