"""
Spotify Review Discovery Engine - Configuration & Constants
"""

# ============================================================
# App Metadata
# ============================================================
APP_NAME = "Spotify Review Discovery Engine"
APP_VERSION = "1.0.0"
APP_DESCRIPTION = (
    "AI-powered analysis of Spotify user feedback to surface insights "
    "about music discovery challenges and repetitive listening behavior."
)

# ============================================================
# Spotify App Identifiers
# ============================================================
SPOTIFY_PLAYSTORE_ID = "com.spotify.music"
SPOTIFY_APPSTORE_ID = "324684580"
SPOTIFY_APPSTORE_NAME = "spotify"

# ============================================================
# Scraper Configuration
# ============================================================

# Browser-like headers are required for Reddit RSS and Spotify Community pages.
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
DEFAULT_REQUEST_HEADERS = {
    "User-Agent": BROWSER_USER_AGENT,
    "Accept-Language": "en-US,en;q=0.9",
}

# Google Play Store (India, English only)
PLAYSTORE_DEFAULT_COUNTRY = "in"
PLAYSTORE_DEFAULT_LANG = "en"
PLAYSTORE_MIN_REVIEWS = 300
PLAYSTORE_REVIEW_COUNT_MIN = 0
PLAYSTORE_REVIEW_COUNT_MAX = 5000
PLAYSTORE_BATCH_SIZE = 200
PLAYSTORE_SLEEP_MS = 2000  # milliseconds between batches

# Apple App Store (India, English only)
APPSTORE_DEFAULT_COUNTRY = "in"
APPSTORE_DEFAULT_REVIEWS = 300

# LLM (optional — set OPENAI_API_KEY in .env or Streamlit secrets)
OPENAI_MODEL = "gpt-4o-mini"

# Review quality filters applied after scraping
MIN_REVIEW_WORD_COUNT = 4

# Inferred user tier (from review text — not account metadata)
FREE_TIER_KEYWORDS = [
    "free version", "free tier", "free plan", "free user", "free account",
    "free spotify", "with ads", "too many ads", "advertisement", "advertisements",
    " ad ", " ads ", "ad supported", "ad-supported", "free mode",
    "without paying", "don't pay", "cant pay", "can't pay", "cannot pay",
]
PREMIUM_TIER_KEYWORDS = [
    "spotify premium", "premium user", "premium account", "premium member",
    "premium plan", "premium subscription", "paid subscription", "subscribed to",
    "pay for premium", "paying for", "subscription fee", "monthly subscription",
    "premium worth", "renew premium", "premium family", "student premium",
    "premium duo", "premium individual",
]
# Shorter signals used when longer phrases miss
FREE_TIER_KEYWORDS.extend(["free", "ads"])
PREMIUM_TIER_KEYWORDS.extend(["premium", "subscription", "subscribed", "paid plan"])

# Reddit
REDDIT_SUBREDDITS = ["spotify", "SpotifyIndia", "Music", "LetsTalkMusic"]
REDDIT_SEARCH_QUERIES = [
    "spotify discovery",
    "spotify recommendations",
    "spotify same songs",
    "spotify algorithm",
    "spotify repeat",
    "spotify playlist boring",
    "spotify discover weekly",
    "spotify india",
]
REDDIT_POSTS_PER_QUERY = 25
REDDIT_SLEEP_SECONDS = 2  # delay between RSS requests
REDDIT_USE_RSS = True  # JSON endpoints are blocked from most cloud IPs; RSS is reliable

# Spotify Community Forum (public recent-posts feed; board pages require login)
COMMUNITY_BASE_URL = "https://community.spotify.com"
COMMUNITY_RECENT_POSTS_PATH = "/t5/forums/recentpostspage/tab/message"
COMMUNITY_PAGES = 3
COMMUNITY_SLEEP_SECONDS = 2

# ============================================================
# Analysis Configuration
# ============================================================

# Sentiment Analysis
SENTIMENT_POSITIVE_THRESHOLD = 0.05
SENTIMENT_NEGATIVE_THRESHOLD = -0.05

# Topic Modeling (LDA)
LDA_NUM_TOPICS = 8
LDA_MAX_FEATURES = 5000
LDA_TOP_WORDS_PER_TOPIC = 15
LDA_MAX_ITER = 20

# Custom Stopwords (domain-specific)
CUSTOM_STOPWORDS = [
    "spotify", "app", "music", "song", "songs", "listen", "listening",
    "play", "playing", "use", "using", "get", "got", "like", "just",
    "really", "one", "would", "could", "also", "much", "even", "still",
    "every", "make", "made", "know", "want", "think", "good", "great",
    "best", "love", "time", "well", "way", "thing", "things", "lot",
    "please", "thanks", "thank", "update", "version", "phone",
]

# ============================================================
# Theme Classification Taxonomy
# ============================================================
THEME_TAXONOMY = {
    "Discovery Frustrations": {
        "keywords": [
            "same songs", "same music", "same artists", "echo chamber",
            "bubble", "repetitive", "repeat", "boring", "stale",
            "nothing new", "no new", "stuck", "loop", "over and over",
            "same thing", "same stuff", "fed up", "tired of",
        ],
        "description": "Users frustrated with lack of new music discovery",
        "icon": "🔁",
    },
    "Algorithm Complaints": {
        "keywords": [
            "algorithm", "ai", "recommendation", "suggest", "recommended",
            "suggestions", "personalization", "personalize", "curated",
            "machine learning", "not accurate", "wrong genre", "bad recs",
            "doesnt understand", "doesn't understand", "miss the mark",
        ],
        "description": "Issues with how the recommendation system works",
        "icon": "🤖",
    },
    "Playlist Issues": {
        "keywords": [
            "discover weekly", "release radar", "daily mix", "playlist",
            "playlists", "mix", "made for you", "blend", "radio",
            "autoplay", "auto play", "queue", "shuffle",
        ],
        "description": "Problems with specific playlist features",
        "icon": "📋",
    },
    "Listening Behavior": {
        "keywords": [
            "comfort zone", "familiar", "favorite", "favourite",
            "go-to", "go to", "always listen", "keep playing",
            "on repeat", "mood", "vibe", "energy", "workout",
            "study", "sleep", "focus", "background",
        ],
        "description": "User listening patterns and habits",
        "icon": "🎧",
    },
    "Feature Requests": {
        "keywords": [
            "wish", "should add", "please add", "need feature",
            "want feature", "missing", "would be nice", "should have",
            "can you add", "option to", "ability to", "let us",
            "allow us", "bring back", "improve",
        ],
        "description": "User requests for new or improved features",
        "icon": "💡",
    },
    "Content Diversity": {
        "keywords": [
            "genre", "genres", "diverse", "diversity", "variety",
            "different", "new artists", "indie", "underground",
            "mainstream", "popular", "trending", "local", "regional",
            "language", "hindi", "bollywood", "international",
        ],
        "description": "Desire for more diverse content recommendations",
        "icon": "🌍",
    },
    "Premium vs Free": {
        "keywords": [
            "premium", "free", "paid", "subscription", "ads",
            "advertisements", "ad-free", "offline", "download",
            "price", "cost", "worth", "money", "expensive", "cheap",
        ],
        "description": "Differences in experience between free and premium users",
        "icon": "💰",
    },
    "UI/UX Issues": {
        "keywords": [
            "interface", "ui", "ux", "design", "layout", "navigation",
            "hard to find", "confusing", "cluttered", "crash", "bug",
            "slow", "laggy", "battery", "storage", "glitch", "broken",
        ],
        "description": "User interface and experience problems",
        "icon": "📱",
    },
}

# ============================================================
# Strategic Questions
# ============================================================
STRATEGIC_QUESTIONS = [
    {
        "id": "q1",
        "question": "Why do users struggle to discover new music?",
        "relevant_themes": ["Discovery Frustrations", "Algorithm Complaints", "Content Diversity"],
        "icon": "🔍",
    },
    {
        "id": "q2",
        "question": "What are the most common frustrations with recommendations?",
        "relevant_themes": ["Algorithm Complaints", "Playlist Issues", "Discovery Frustrations"],
        "icon": "😤",
    },
    {
        "id": "q3",
        "question": "What listening behaviors are users trying to achieve?",
        "relevant_themes": ["Listening Behavior", "Content Diversity", "Feature Requests"],
        "icon": "🎯",
    },
    {
        "id": "q4",
        "question": "What causes users to repeatedly listen to the same content?",
        "relevant_themes": ["Discovery Frustrations", "Listening Behavior", "Algorithm Complaints"],
        "icon": "🔄",
    },
    {
        "id": "q5",
        "question": "Which user segments experience different discovery challenges?",
        "relevant_themes": ["Premium vs Free", "Content Diversity", "Listening Behavior"],
        "icon": "👥",
    },
    {
        "id": "q6",
        "question": "What unmet needs emerge consistently across reviews?",
        "relevant_themes": ["Feature Requests", "Content Diversity", "Discovery Frustrations"],
        "icon": "📊",
    },
]

# ============================================================
# Standardized DataFrame Columns
# ============================================================
STANDARD_COLUMNS = [
    "source",
    "review_text",
    "rating",
    "date",
    "username",
    "helpful_count",
    "app_version",
    "language",
    "country",
    "title",
]

# ============================================================
# Data Storage
# ============================================================
DATA_DIR = "data"
SCRAPED_DATA_FILE = "scraped_reviews.csv"
ANALYZED_DATA_FILE = "analyzed_reviews.csv"

# ============================================================
# Visualization Configuration
# ============================================================
SPOTIFY_GREEN = "#1DB954"
SPOTIFY_GREEN_LIGHT = "#1ED760"
SPOTIFY_BLACK = "#121212"
SPOTIFY_DARK_GRAY = "#1E1E1E"
SPOTIFY_MEDIUM_GRAY = "#282828"
SPOTIFY_LIGHT_GRAY = "#B3B3B3"
SPOTIFY_WHITE = "#FFFFFF"

PLOTLY_TEMPLATE = "plotly_dark"
PLOTLY_COLOR_SEQUENCE = [
    "#1DB954", "#1ED760", "#2EBD59", "#57B660",
    "#7BC67E", "#A0D8A4", "#509BF5", "#A3CFFF",
    "#F573A0", "#FFB4C8", "#F59B42", "#FFC97E",
]
