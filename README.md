# Spotify Review Discovery Engine 🎵

A feedback tool for Spotify product teams. It pulls reviews and discussions from India app stores, Reddit, and the community forum, then tags them so you can see where music discovery and recommendations are falling short.

Use it to answer practical questions: why users get stuck replaying the same tracks, what breaks in the recommendation experience, and which pain points keep showing up across channels.

**Repository:** [github.com/persistentgorilla/NL_Project3](https://github.com/persistentgorilla/NL_Project3)

---

## 🚀 Key Features

* **Scalable Scraping Layer** (India · English only for app stores):
  * **Google Play Store**: Pulls English reviews from the India storefront using `google-play-scraper` with continuation-token pagination and polite rate-limiting.
  * **Apple App Store**: Extracts iOS reviews from the India storefront via the public iTunes RSS feed (with optional `app-store-scraper` library support locally).
  * **Reddit Discussions**: Crawls subreddits via RSS (`old.reddit.com`) with PullPush API fallback when RSS is blocked.
  * **Spotify Community Forums**: Scrapes the public recent-posts feed on `community.spotify.com` (board pages require login).
* **Review Quality Filters** (applied before NLP analysis):
  * Drops reviews that contain **emoji** characters.
  * Drops reviews with **fewer than 4 words**.
* **AI & NLP Analysis Pipeline**:
  * **VADER Sentiment Engine**: Optimized for social language and app reviews.
  * **Subjectivity Indexing**: Measures subjective opinions vs. factual issues using TextBlob.
  * **Topic Modeling**: Clusters feedback using TF-IDF and Latent Dirichlet Allocation (LDA).
  * **Theme Taxonomy Classifier**: Rule-based keyword classifier for Discovery Frustrations, Algorithm Complaints, Playlist Issues, Listening Behavior, Feature Requests, and more.
* **Streamlit Multi-page App**:
  * **Dashboard** — Validation-first view: inferred tier toggle (All / Free / Premium), four user segments, top pain areas, quotes to validate, and optional supporting charts. **Reset** clears session and local cache.
  * **Deep Dive** — Search and filter by segment, tier, source, sentiment, and themes; respects the Dashboard tier toggle. CSV + Excel export.
  * **Trends** — Sentiment and theme volume over time, with Excel export.
  * **Strategic Insights** — AI-written (or rule-based) answers by discovery question, user segments, pain areas, and validation quotes. Excel export.

---

## Metrics & definitions

Plain-language reference for what you see in the app. Technical method names (VADER, LDA, etc.) sit in tooltips and the section below only where they help you interpret the output.

### Volume & sources

| Metric | What it means |
|--------|----------------|
| **Reviews in view** | Feedback in the current Dashboard filter (All users, or Free/Premium inferred tier). |
| **Negative reviews** | Reviews with negative tone — primary signal for user problems. |
| **% negative** | Share of the current view that is negative. |
| **Top pain area** | Most common themed problem among negative reviews in the current view. |
| **Sources with data** | How many channels contributed (e.g. Play Store, App Store, Reddit, Community). |
| **Volume by source** | Raw count per channel. Reddit and forum posts do not carry star ratings. |

### Quality filters (applied before analysis)

| Rule | Why |
|------|-----|
| **No emojis** | Short emoji-heavy posts skew sentiment and add noise. |
| **Minimum 4 words** | Single-word or fragment posts are rarely actionable for product decisions. |
| **Deduplication** | Identical review text (case-insensitive) is counted once. |

App store scraping is locked to **India (IN)** and **English**. Review targets per store: **0–5,000** (default 300).

### Sentiment

| Metric | What it means |
|--------|----------------|
| **Overall sentiment** | Average tone across all reviews on a −1 to +1 scale. Closer to +1 = mostly positive; closer to −1 = mostly negative. |
| **Sentiment (compound score)** | Per-review score from VADER, tuned for informal language in app reviews and forums. |
| **Tone / sentiment label** | Buckets each review as **Positive**, **Neutral**, or **Negative** using fixed cutoffs on the compound score. |
| **How sentiment is spread** | Histogram showing how many reviews fall in each tone bucket. |

### Ratings (app stores only)

| Metric | What it means |
|--------|----------------|
| **Avg star rating (stores)** | Mean 1–5 star score from Play Store and App Store reviews only. |
| **Star ratings by source** | Breakdown of 1–5 star counts per store channel. |
| **Do low ratings match negative tone?** | Scatter plot comparing star rating to sentiment — useful for spotting mismatches (e.g. 5 stars but negative text). |

### Themes & topics

| Metric | What it means |
|--------|----------------|
| **Theme** | A rule-based tag from keyword matching — e.g. discovery frustration, algorithm complaints, playlist issues, listening behavior, feature requests. A review can match multiple themes. |
| **Which themes come up most** | Bar chart of theme mention counts across the dataset. |
| **Themes that appear together** | Heatmap of reviews tagged with two themes at once — surfaces compound pain points. |
| **Topic (LDA)** | Unsupervised cluster of reviews that share similar vocabulary. Unlike themes, topics are discovered from the data rather than predefined keywords. |
| **Share of conversation** | Approximate proportion of the corpus assigned to each topic cluster. |
| **Words that show up most** | Word cloud of the most frequent terms after basic text cleaning. |

### Other signals

| Metric | What it means |
|--------|----------------|
| **Subjectivity** | How opinion-heavy vs factual a review reads (TextBlob). High = personal take; low = descriptive or bug-report style. |
| **7-day rolling avg (Trends)** | Smoothed sentiment line to reduce day-to-day noise when reading trends over time. |

### User segments (four consolidated groups)

Reviews can belong to more than one segment. These four cohorts are what you validate in research.

| Segment | Who they are |
|---------|----------------|
| **Discovery & recommendation frustrated** | Repetitive music, weak recommendations, playlist issues (Discover Weekly, Daily Mix), or lack of variety. |
| **App experience & value frustrated** | Crashes, slow UI, confusing navigation, or free vs premium complaints (ads, pricing). |
| **Low-rating app store users** | Play Store or App Store reviewers who left 1–2 stars. |
| **Social & forum discussants** | Users posting on Reddit or the Spotify community forum. |

Each segment card shows negative review count, share of all negative feedback, and top issue. Strategic Insights adds AI-written answers per discovery question when an API key is configured.

### Inferred Free vs Premium toggle

The Dashboard and Strategic Insights include a **View by inferred user tier** toggle:

| Option | Meaning |
|--------|---------|
| **All users** | Full dataset (default) |
| **Free (inferred)** | Reviews whose text mentions free-tier signals (ads, free plan, etc.) |
| **Premium (inferred)** | Reviews mentioning premium, subscription, or paid plan |

This is **inferred from review text**, not Spotify account metadata. Deep Dive respects the same toggle (set on the Dashboard). The `inferred_user_tier` column is added during analysis.

### Optional: AI-written insight answers

Strategic question answers can be written in plain language using OpenAI.

1. Copy `.env.example` to `.env`
2. Set `OPENAI_API_KEY=your-key` (never commit `.env`)
3. Restart the app

For Streamlit Cloud, add `OPENAI_API_KEY` under **App settings → Secrets**.

If no key is set, the app falls back to rule-based summaries.

---

### Under the hood (for reference)

- **VADER** — Sentiment scoring for short, informal text.
- **TextBlob** — Subjectivity scoring.
- **TF-IDF + LDA** — Topic clustering: TF-IDF weights important words; LDA groups reviews into themes by shared vocabulary.
- **Theme taxonomy** — Keyword rules defined in `config/settings.py` for product-relevant categories.

---

## 🛠️ Tech Stack

* **Frontend & Dashboard**: Streamlit (Spotify-themed dark mode UI)
* **NLP & Analytics**: scikit-learn, NLTK, VADER Sentiment, TextBlob
* **Scrapers**: google-play-scraper, requests, BeautifulSoup4 (App Store via iTunes RSS)
* **Data & Plots**: Pandas, Plotly, WordCloud, Matplotlib

---

## ⚙️ Setup & Local Installation

### Prerequisites

* Python 3.9 or higher

### 1. Clone the repository

```bash
git clone https://github.com/persistentgorilla/NL_Project3.git
cd NL_Project3
```

### 2. Create and activate a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

**Optional (local only):** For the App Store library scraper in addition to RSS, install without pulling its outdated `requests` pin:

```bash
pip install app-store-scraper --no-deps
```

> Do not add `app-store-scraper` to `requirements.txt` — it pins `requests==2.23.0`, which conflicts with Streamlit and causes Cloud deploy failures.

---

## 🎮 Running the Application

```bash
streamlit run app.py
```

The app opens at `http://localhost:8501`.

### Workflow

1. **Home page** — Run summary after scraping: review count, negative %, top pain, links to Dashboard and Strategic Insights.
2. **Sidebar** — Pick sources, set app store targets (0–5,000; default 300), then **Start Scraping & Analysis**.
3. **Dashboard** — Use **View by inferred user tier** (All / Free / Premium) to branch results. Review segments, pain areas, and validation quotes.
4. **Strategic Insights** — Same tier toggle; read AI-written answers per discovery question (requires `OPENAI_API_KEY`).
5. **Deep Dive** — Filter individual reviews; inherits tier selection from the Dashboard.
6. **Load cache** — **Load Previously Analyzed Data** reloads CSV files from the local `data/` folder.
7. **Reset** — On the Dashboard, **Reset** clears session data, insights cache, and local CSV files.

> **Re-analyze after updates:** If you loaded data before a feature release (e.g. tier labels), run a fresh scrape or load raw cache and re-analyze so new columns are populated.

---

## ☁️ Deploy on Streamlit Community Cloud

1. Push this repository to GitHub.
2. Go to [share.streamlit.io](https://share.streamlit.io) and sign in.
3. Click **New app** and select `persistentgorilla/NL_Project3`.
4. Set **Main file path** to `app.py`.
5. Set **Python version** to **3.11** (matches `.python-version` in the repo).
6. Click **Deploy**.

Dependencies are installed from `requirements.txt`. Theme and server settings live in `.streamlit/config.toml`.

**Optional — AI insight answers on Cloud:** In **App settings → Secrets**, add:

```toml
OPENAI_API_KEY = "sk-..."
OPENAI_MODEL = "gpt-4o-mini"
```

> **Deploy troubleshooting:** If you see *"installer returned a non-zero exit code"*, open the deploy logs and look for dependency conflicts. The most common cause is adding `app-store-scraper` to `requirements.txt`.

> **Note:** Streamlit Cloud uses ephemeral storage. CSV files saved under `data/` do not persist across redeploys; scraped data remains available for the current browser session via Streamlit session state.

---

## 🧪 Testing

Run the unit test suite:

```bash
python3 -m unittest discover -s tests -v
```

Tests cover scraper schemas, sentiment and theme classification, review quality filters, user segments, tier inference, optional LLM insight shape, and CSV/Excel export round-trips.

---

## 📁 Repository Structure

```
NL_Project3/
├── app.py                          # Streamlit entry point & pipeline orchestrator
├── requirements.txt                # Python dependencies
├── README.md
├── .env.example                    # Template for OPENAI_API_KEY (copy to .env locally)
├── .gitignore
├── .streamlit/
│   ├── config.toml                 # Streamlit theme & server settings
│   └── packages.txt                # Optional OS packages for cloud deploy
├── config/
│   ├── __init__.py
│   └── settings.py                 # App IDs, scraping thresholds, theme taxonomy
├── scrapers/
│   ├── base_scraper.py
│   ├── playstore_scraper.py
│   ├── appstore_scraper.py
│   ├── reddit_scraper.py
│   └── community_scraper.py
├── analysis/
│   ├── sentiment.py
│   ├── topic_modeling.py
│   ├── theme_classifier.py
│   ├── user_segments.py            # Four consolidated user segment profiles
│   ├── llm_analyzer.py             # Optional OpenAI answers for insights
│   └── insights_engine.py
├── visualizations/
│   ├── charts.py
│   └── wordclouds.py
├── pages/
│   ├── 1_📊_Dashboard.py
│   ├── 2_🔍_Deep_Dive.py
│   ├── 3_📈_Trends.py
│   └── 4_💡_Strategic_Insights.py
├── utils/
│   ├── data_io.py                  # CSV save/load with type restoration
│   ├── html.py                     # HTML escaping for safe markup
│   ├── session_reset.py            # Clear session state and local data cache
│   ├── dashboard_context.py        # Cached exec summary, validation quotes
│   ├── tier_inference.py           # Inferred Free / Premium from review text
│   └── text_filters.py             # Emoji and minimum word-count filters
├── data/
│   └── .gitkeep                    # Local cache for scraped CSVs (gitignored)
└── tests/
    └── test_scrapers.py
```

---

## 💡 Strategic Growth Questions Answered

1. **Why do users struggle to discover new music?**
2. **What are the most common frustrations with recommendations?**
3. **What listening behaviors are users trying to achieve?**
4. **What causes users to repeatedly listen to the same content?**
5. **Which user segments experience different discovery challenges?**
6. **What unmet needs emerge consistently across reviews?**

---

## ✅ Health Check (pre-release)

| Check | Status |
|-------|--------|
| Unit tests (`tests/test_scrapers.py`, 17 tests) | Pass |
| Core module imports | Pass |
| `utils` package (data I/O, filters, session reset, tier inference) | Present |
| Validation-first Dashboard (segments, pain, quotes) | Configured |
| India-only / English-only app store scraping | Configured |
| Review quality filter (no emojis, ≥4 words) | Configured |
| User segments (4 consolidated cohorts) | Configured |
| Inferred Free / Premium tier toggle | Configured |
| Optional LLM insight answers (`OPENAI_API_KEY`) | Configured |
| Streamlit config (`.streamlit/config.toml`) | Configured |
| Requirements pinned for cloud deploy | Configured |
