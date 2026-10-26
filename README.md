# 🏥 Smart Hospital Navigation System v2 — with Real Data, Login & Interactive Map

An upgraded, full-stack AI/ML project that:
1. Lets a user **log in / register** (secure, hashed passwords)
2. Predicts the correct hospital **department** from symptoms, using a model trained on a **real 4,920-row public medical dataset** (132 symptoms, 41 diseases)
3. Calculates the shortest path from Entrance to that department using **Dijkstra's Algorithm**
4. Shows it all on an **interactive, zoomable/pannable SVG hospital map** with hover tooltips
5. Is ready to **deploy for free** on Render

---

## 🆕 What's new in this version

| Area | v1 (prototype) | v2 (this upgrade) |
|---|---|---|
| **Dataset** | 110 hand-written rows | **Real public dataset**: 4,920 rows, 132 symptoms, 41 diseases |
| **ML accuracy** | ~68% (tiny, noisy data) | **100% test accuracy** (see honesty note below) |
| **ML approach** | Single Naive Bayes model | **4 models compared** with 5-fold cross-validation (Naive Bayes, Logistic Regression, Random Forest, Linear SVM) — best one auto-selected |
| **Symptom input** | Free text only, guessed via TF-IDF | **Interactive searchable symptom picker** (132 exact symptoms) + free-text fallback that matches against the same vocabulary |
| **Map** | Static SVG | **Interactive**: scroll-to-zoom, drag-to-pan, hover tooltips, zoom/reset buttons |
| **Users** | None | **Login system** (Flask-Login + SQLite, hashed passwords) — predictor is behind a login wall |
| **Deployment** | Local only | **Procfile + render.yaml** for free hosting on Render |

---

## 📊 Honesty note on the "100% accuracy"

The dataset used (`model/data/Training.csv`) is a well-known, widely-used **educational** dataset (originally published on Kaggle as *"Disease Prediction Using Machine Learning"*). It is synthetically clean: every disease has a fixed, non-overlapping set of symptoms, so getting 100% accuracy on it is expected and easy — it does **not** mean the model would be 100% accurate on messy real-world patient data with typos, overlapping symptoms, or missing information.

This is actually a great thing to say out loud in your presentation — it shows you understand the difference between "accuracy on a clean benchmark" and "real-world robustness," which is exactly the kind of thing an interviewer wants to hear. Good talking points:
- "The dataset is clean/synthetic, so 100% is expected — real-world accuracy would require noisier, more realistic data."
- "I compared 4 algorithms with cross-validation instead of just picking one, which is good ML practice."
- "The confidence score and matched-symptoms display are shown to the user so they can sanity-check the prediction instead of trusting a black box."

---

## 📁 Project Structure

```
smart-hospital-navigation/
│
├── app.py                       # Flask backend — auth + /predict, /symptoms, /map APIs
├── requirements.txt
├── Procfile                     # For gunicorn (Render/Railway/Heroku-style hosts)
├── render.yaml                  # One-click free deploy config for Render
├── .gitignore
│
├── model/
│   ├── data/
│   │   └── Training.csv         # Real dataset: 4,920 rows, 132 symptoms, 41 diseases
│   ├── disease_department_map.py# Maps each disease -> hospital department
│   ├── symptom_utils.py         # Shared symptom name cleanup + text matching
│   ├── train_model.py           # Trains + compares 4 models, saves the best one
│   ├── department_model.pkl     # Saved trained model (auto-generated)
│   ├── feature_columns.pkl      # Saved exact symptom column order (auto-generated)
│   └── training_metrics.json    # Saved accuracy/CV scores (auto-generated)
│
├── graph/
│   └── hospital_graph.py        # Hospital map as a graph + Dijkstra's algorithm
│
├── auth/
│   └── models.py                # SQLite-backed User model (Flask-Login)
│
├── templates/
│   ├── index.html               # Main app page (protected — must be logged in)
│   ├── login.html
│   └── register.html
│
├── static/
│   ├── css/style.css
│   └── js/script.js             # API calls, symptom picker, interactive map
│
└── hospital_app.db               # SQLite database (auto-created on first run)
```

---

## ⚙️ Installation

Requires **Python 3.9+**.

```bash
# 1. (Optional but recommended) create a virtual environment
python -m venv venv
source venv/bin/activate      # On Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt
```

## 🧠 Step 1 — Train the ML Model

```bash
python model/train_model.py
```

You'll see it load the real dataset, cross-validate 4 models, and save the best one:
```
📂 Loading real-world dataset (Training.csv)...
✅ Loaded 4920 patient records with 132 symptoms across 41 diseases.
🏥 Departments in training data: [...]
🧠 Training & cross-validating candidate models...
  Naive Bayes (Bernoulli)      -> 100.00% (5-fold CV avg)
  Logistic Regression          -> 100.00% (5-fold CV avg)
  Random Forest                -> 100.00% (5-fold CV avg)
  Linear SVM                   -> 100.00% (5-fold CV avg)
🏆 Best model: Naive Bayes (Bernoulli) (100.0% CV accuracy)
📈 Final held-out test accuracy: 100.0%
💾 Model saved to: model/department_model.pkl
```

## 🌐 Step 2 — Run the Web App

```bash
python app.py
```

Open **http://127.0.0.1:5000** — you'll be redirected to a login page.

1. Click **Create an account** and register (username, email, password — min 6 characters).
2. Log in.
3. Either **search and pick symptoms** from the interactive list (most accurate), or **type them in your own words** in the text box below (matched automatically against the same 132 known symptoms).
4. Click **Find My Department** to see the predicted department, confidence, matched symptoms, shortest route, and the interactive map with the route highlighted.

---

## 🗺️ Interactive Map — how it works

- **Zoom**: scroll your mouse wheel over the map, or use the **+ / − Zoom** buttons.
- **Pan**: click and drag anywhere on the map.
- **Reset**: snaps back to the default view.
- **Hover** any room circle to see its name in a tooltip.
- The path returned by Dijkstra's Algorithm is drawn in **coral/red**, everything else in **teal**.

This is implemented in `static/js/script.js` using a single SVG `<g>` group whose `transform` (translate + scale) is updated on drag/scroll — no external charting library needed, so it's easy to explain line-by-line in a viva.

---

## 🔐 Login System — how it works

- `auth/models.py` defines a `User` class backed by a plain SQLite table (`hospital_app.db`, auto-created on first run).
- Passwords are **never stored in plain text** — `werkzeug.security.generate_password_hash` / `check_password_hash` (salted hashing) handle that.
- `Flask-Login` manages the session cookie, so once logged in you stay logged in across requests until you click **Log out**.
- Every data route (`/`, `/predict`, `/symptoms`, `/map`) is decorated with `@login_required`, so the predictor cannot be used without an account.

---

## 🧬 How the Real Dataset Became a "Department" Predictor

The public dataset labels each row with a **disease** (e.g. "Migraine", "Hypertension"), not a department — hospitals don't have a "Migraine department." `model/disease_department_map.py` maps all 41 diseases to the department that would actually treat them (e.g. Migraine → Neurology, Hypertension → Cardiology, Acne → Dermatology). Edit this dictionary if you want different department names or mappings.

> Note: 3 departments on the hospital map (Psychiatry, Pediatrics, Ophthalmology) currently have **no rows** in this particular dataset, so the model will never predict them. This is clearly documented as a known limitation — a great "future work" point: add real training rows for these departments to `model/data/Training.csv` (as extra columns/rows) to cover them too.

---

## 🚀 Deployment — Free Hosting on Render

[Render](https://render.com) has a free tier that works well for a Flask app like this one.

### Option A — One-click via `render.yaml` (recommended)
1. Push this project to a **GitHub repository** (create one on github.com, then `git init`, `git add .`, `git commit`, `git remote add origin <your-repo-url>`, `git push`).
2. Go to [render.com](https://render.com) → sign up/log in (free) → **New → Blueprint**.
3. Connect your GitHub repo. Render will detect `render.yaml` automatically and set everything up (build command trains the model, start command runs `gunicorn app:app`).
4. Click **Apply** — Render builds and deploys automatically. You'll get a live URL like `https://smart-hospital-navigation.onrender.com`.

### Option B — Manual Web Service on Render
1. Push your code to GitHub (see step 1 above).
2. On Render: **New → Web Service** → connect your repo.
3. Set:
   - **Build Command**: `pip install -r requirements.txt && python model/train_model.py`
   - **Start Command**: `gunicorn app:app`
   - **Environment Variable**: `SECRET_KEY` → any long random string
4. Click **Create Web Service**.

### Notes on the free tier
- Render's free web services **spin down after inactivity** and take ~30–60 seconds to wake up on the next request — perfectly fine for a college demo, just mention it if the first click seems slow.
- The SQLite database (`hospital_app.db`) lives on Render's local disk, which is **not persistent** on the free tier (it resets on redeploy). For a class project this is fine; for anything long-term, swap in a free hosted database (e.g. Render's free PostgreSQL tier) later.

### Alternatives
- **PythonAnywhere** (free tier, great for Flask, persistent storage, slightly more manual WSGI setup).
- **Railway** (free trial credits, very similar workflow to Render).

---

## 🩹 Error Handling Already Included

- Empty symptom input (no picker selection AND no text) → friendly inline error
- Free text that doesn't match any of the 132 known symptoms → clear message suggesting the picker instead
- Model not trained yet → clear message telling you to run `train_model.py`
- Wrong login credentials / duplicate username or email on registration → flashed error messages
- Network/server errors on the frontend → shown in the red error box instead of a silent failure

---

## 🎓 Suggested Presentation Flow

1. **Problem statement** — patients don't know which department to visit or how to get there in a large hospital.
2. **Real dataset + ML pipeline** — show `train_model.py` running live: loading real data, cross-validating 4 models, picking the best one. Be upfront about the clean/synthetic-data caveat above.
3. **Graph + Dijkstra** — show `hospital_graph.py`, explain nodes/edges/weights, run the shortest path.
4. **Live demo** — register/login, pick symptoms from the interactive list (or type them), show department + path + the zoomable/pannable map.
5. **Security** — mention hashed passwords + login-gated routes.
6. **Deployment** — show the live Render URL if you deployed it, or walk through `render.yaml`.
7. **Future scope** — bigger/noisier real-world dataset, more departments with real training data, hospital IoT integration, voice input, multi-floor navigation, persistent production database.

---

Built with **Python, scikit-learn, Flask, Flask-Login, SQLite, HTML/CSS/JavaScript** — no complex frameworks, so every line is easy to explain in a viva or interview.
