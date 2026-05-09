# 🚀 InsightFlow

### **Agentic Data Analytics Platform for Modern Data Exploration**

InsightFlow is a powerful **full-stack data analytics platform** that enables users to upload datasets, analyze data quality, perform exploratory analysis, and interact with data using natural language queries.

Designed as a **placement-level portfolio project**, InsightFlow combines **backend analytics engineering**, **interactive UI/UX**, and **agentic workflows** into a single intelligent analytics workspace.

---

# ✨ Features

## 📂 Smart Dataset Upload
- Upload **CSV**, **Excel**, and **JSON** files
- Instant dataset ingestion using FastAPI + Pandas
- Real-time backend processing

---

## 📊 Automated Analytics Dashboard
- Total Rows & Columns
- Missing Value Detection
- Duplicate Row Analysis
- Numeric vs Categorical Column Detection
- Dataset Profiling

---

## 🔍 Exploratory Data Analysis (EDA)
- Statistical summaries
- Correlation analysis
- Automated dataset insights
- Real-time backend-driven analytics

---

## 🧹 Data Cleaning Insights
- Missing value inspection
- Duplicate row detection
- Column-level null analysis

---

## 🤖 Ask Your Data (Agentic Analytics)
Ask natural language questions like:

- “Show missing values”
- “How many duplicates exist?”
- “List all columns”
- “Give dataset summary”
- “Show numeric columns”

The backend intelligently interprets queries and generates analytics responses using pandas.

---

# 🛠️ Tech Stack

## 🎨 Frontend
- **HTML**
- **Tailwind CSS**
- **Vanilla JavaScript**

---

## ⚙️ Backend
- **FastAPI**
- **Pandas**
- **NumPy**
- **Uvicorn**

---

# 🧠 Architecture

```text
Frontend UI
    ↓
REST API Calls
    ↓
FastAPI Backend
    ↓
Pandas Data Processing
    ↓
Analytics + Insights
    ↓
Interactive UI Rendering
```

---

# 📌 Core Functionalities

| Module | Description |
|---|---|
| 📂 Upload Engine | Upload datasets instantly |
| 📊 Dashboard | Automated KPI generation |
| 🔍 EDA | Statistical analysis |
| 🧹 Cleaning | Data quality inspection |
| 🤖 Ask Data | Natural language analytics |
| 📑 Data Preview | Real dataset table rendering |

---

# 🌐 API Endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/` | GET | Backend health check |
| `/upload` | POST | Upload dataset |
| `/eda` | GET | Exploratory analysis |
| `/data` | GET | Dataset preview |
| `/cleaning` | GET | Cleaning insights |
| `/ask` | POST | Ask questions about data |

---

# ⚡ Installation & Setup

## 1️⃣ Clone Repository

```bash
git clone https://github.com/ranjannrohit/InsightFlow.git
cd InsightFlow
```

---

## 2️⃣ Install Dependencies

```bash
pip install -r requirements.txt
```

---

## 3️⃣ Run Backend

```bash
python -m uvicorn main:app --reload
```

Backend runs on:

```text
http://127.0.0.1:8000
```

---

## 4️⃣ Run Frontend

```bash
python -m http.server 5500
```

Open:

```text
http://localhost:5500
```

---

# 🚀 Future Enhancements

- 📈 Interactive Charts
- 🧠 AI-Powered Insights
- 🗄️ SQL Query Generation
- 📄 Export Reports (PDF)
- 🔐 User Authentication
- ☁️ Cloud Dataset Storage
- ⚡ Real-Time Dashboard Updates
- 🤖 LLM-Powered Data Agent

---

# 🎯 Project Vision

InsightFlow aims to become a modern **agentic analytics workspace** that simplifies how users interact with data.

The project demonstrates:
- Full-stack development
- Data analytics workflows
- Backend engineering
- UI/UX design thinking
- Real-world project architecture
- Agentic system design

---

# 👨‍💻 Author

### **Rohit Ranjan**
Aspiring Data Analyst | Data Analytics Enthusiast | Full-Stack Builder

---

# ⭐ Support

If you found this project useful, consider giving it a ⭐ on GitHub.