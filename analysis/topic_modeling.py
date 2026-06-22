"""
Spotify Review Discovery Engine — Topic Modeling Module

Uses scikit-learn TfidfVectorizer + LatentDirichletAllocation to discover
latent topics across user reviews.  Text preprocessing uses NLTK for
tokenisation, lemmatisation, and stop-word removal.
"""

from __future__ import annotations

import logging
import re
import string
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

import nltk
from nltk.corpus import stopwords as nltk_stopwords
from nltk.stem import WordNetLemmatizer
from nltk.tokenize import word_tokenize

from sklearn.decomposition import LatentDirichletAllocation
from sklearn.feature_extraction.text import TfidfVectorizer

from config.settings import (
    CUSTOM_STOPWORDS,
    LDA_MAX_FEATURES,
    LDA_MAX_ITER,
    LDA_NUM_TOPICS,
    LDA_TOP_WORDS_PER_TOPIC,
)

logger = logging.getLogger(__name__)

_NLTK_READY = False


def _ensure_nltk_data() -> None:
    """Download required NLTK resources once per process."""
    global _NLTK_READY
    if _NLTK_READY:
        return
    for resource in (
        "stopwords",
        "wordnet",
        "punkt",
        "punkt_tab",
        "omw-1.4",
        "averaged_perceptron_tagger",
        "averaged_perceptron_tagger_eng",
    ):
        nltk.download(resource, quiet=True)
    _NLTK_READY = True


class TopicModeler:
    """Discover latent topics in review text using TF-IDF + LDA.

    Attributes
    ----------
    n_topics : int
        Number of LDA topics (default from config).
    max_features : int
        Max vocabulary size for TF-IDF.
    top_words : int
        Number of keywords to extract per topic.
    max_iter : int
        Maximum LDA iterations.
    stopwords : set[str]
        Combined NLTK English + domain-specific stop-words.
    lemmatizer : WordNetLemmatizer
        NLTK lemmatiser instance.
    vectorizer : TfidfVectorizer | None
        Fitted vectoriser (available after :meth:`analyze`).
    lda_model : LatentDirichletAllocation | None
        Fitted LDA model (available after :meth:`analyze`).
    topic_data : list[dict]
        Per-topic keyword information (available after :meth:`analyze`).
    """

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def __init__(self, n_topics: Optional[int] = None) -> None:
        """Download NLTK data and initialise hyper-parameters.

        Parameters
        ----------
        n_topics : int, optional
            Override the default number of topics from config.
        """
        _ensure_nltk_data()

        self.n_topics: int = n_topics or LDA_NUM_TOPICS
        self.max_features: int = LDA_MAX_FEATURES
        self.top_words: int = LDA_TOP_WORDS_PER_TOPIC
        self.max_iter: int = LDA_MAX_ITER

        # Build combined stop-word set
        try:
            base_stopwords = set(nltk_stopwords.words("english"))
        except LookupError:
            base_stopwords = set()
        self.stopwords: set[str] = base_stopwords | set(CUSTOM_STOPWORDS)

        self.lemmatizer = WordNetLemmatizer()

        # Set after fitting
        self.vectorizer: Optional[TfidfVectorizer] = None
        self.lda_model: Optional[LatentDirichletAllocation] = None
        self.topic_data: List[Dict[str, Any]] = []

        logger.info(
            "TopicModeler initialised (n_topics=%d, max_features=%d, "
            "max_iter=%d, stopwords=%d)",
            self.n_topics,
            self.max_features,
            self.max_iter,
            len(self.stopwords),
        )

    # ------------------------------------------------------------------
    # Text preprocessing
    # ------------------------------------------------------------------

    def _preprocess(self, text: str) -> str:
        """Clean and lemmatise a single review.

        Steps
        -----
        1. Lowercase
        2. Remove URLs
        3. Remove punctuation / digits
        4. Tokenise
        5. Remove stop-words
        6. Lemmatise
        7. Drop tokens shorter than 3 characters

        Parameters
        ----------
        text : str
            Raw review text.

        Returns
        -------
        str
            Space-joined processed tokens.
        """
        try:
            text = str(text).lower()
            text = re.sub(r"http\S+|www\.\S+", "", text)
            text = re.sub(r"[^a-z\s]", " ", text)
            text = re.sub(r"\s+", " ", text).strip()

            tokens = word_tokenize(text)
            tokens = [
                self.lemmatizer.lemmatize(t)
                for t in tokens
                if t not in self.stopwords and len(t) >= 3
            ]
            return " ".join(tokens)
        except Exception as exc:
            logger.warning("Preprocessing failed (%.30s…): %s", text, exc)
            return ""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(
        self,
        df: pd.DataFrame,
        n_topics: Optional[int] = None,
    ) -> Tuple[pd.DataFrame, List[Dict[str, Any]]]:
        """Run topic modelling on the ``review_text`` column.

        Parameters
        ----------
        df : pd.DataFrame
            Must contain a ``review_text`` column.
        n_topics : int, optional
            Override the instance default for this run.

        Returns
        -------
        tuple[pd.DataFrame, list[dict]]
            * Enriched DataFrame with ``dominant_topic`` (int) and
              ``topic_distribution`` (list[float]) columns.
            * List of topic dicts, each containing ``topic_id``, ``keywords``
              (list[str]), and ``weight`` (float — proportion of corpus).

        Raises
        ------
        ValueError
            If ``review_text`` column is missing.
        """
        if "review_text" not in df.columns:
            raise ValueError("DataFrame must contain a 'review_text' column.")

        result = df.copy()
        n = n_topics or self.n_topics
        n_docs = len(result)
        logger.info(
            "Starting topic modelling on %d documents (n_topics=%d) …",
            n_docs,
            n,
        )

        # Handle degenerate cases
        if n_docs == 0:
            logger.warning("Empty DataFrame — returning with empty topic columns.")
            result["dominant_topic"] = pd.Series(dtype="int64")
            result["topic_distribution"] = pd.Series(dtype="object")
            self.topic_data = []
            return result, []

        # Pre-process text
        processed = result["review_text"].fillna("").astype(str).apply(self._preprocess)

        # Drop completely empty docs for fitting, but keep index aligned
        non_empty_mask = processed.str.strip() != ""
        valid_count = non_empty_mask.sum()

        if valid_count < 2:
            logger.warning(
                "Fewer than 2 non-empty documents (%d) — skipping LDA.",
                valid_count,
            )
            result["dominant_topic"] = 0
            result["topic_distribution"] = [
                [1.0] + [0.0] * (n - 1)
            ] * n_docs
            self.topic_data = [
                {"topic_id": 0, "keywords": [], "weight": 1.0}
            ]
            return result, self.topic_data

        # Adjust n_topics if there are very few documents
        n = min(n, valid_count)

        # TF-IDF vectorisation
        self.vectorizer = TfidfVectorizer(
            max_features=self.max_features,
            max_df=0.95,
            min_df=max(2, int(valid_count * 0.01)),  # at least 2
            stop_words=None,  # already removed
        )

        try:
            tfidf_matrix = self.vectorizer.fit_transform(processed[non_empty_mask])
        except ValueError as exc:
            logger.error("TF-IDF vectorisation failed: %s", exc)
            result["dominant_topic"] = 0
            result["topic_distribution"] = [[1.0 / n] * n] * n_docs
            self.topic_data = []
            return result, []

        feature_names = self.vectorizer.get_feature_names_out()

        # LDA fitting
        # Single-threaded LDA avoids resource contention on Streamlit Cloud.
        self.lda_model = LatentDirichletAllocation(
            n_components=n,
            max_iter=self.max_iter,
            learning_method="online",
            random_state=42,
            n_jobs=1,
        )
        try:
            doc_topic_matrix = self.lda_model.fit_transform(tfidf_matrix)
        except Exception as exc:
            logger.error("LDA fitting failed: %s", exc)
            result["dominant_topic"] = 0
            result["topic_distribution"] = [[1.0 / n] * n] * n_docs
            self.topic_data = []
            return result, []

        # Build topic metadata
        self.topic_data = []
        for topic_idx, topic_vec in enumerate(self.lda_model.components_):
            top_indices = topic_vec.argsort()[-self.top_words:][::-1]
            keywords = [str(feature_names[i]) for i in top_indices]
            weight = float(doc_topic_matrix[:, topic_idx].mean())
            self.topic_data.append(
                {
                    "topic_id": topic_idx,
                    "keywords": keywords,
                    "weight": round(weight, 4),
                }
            )

        # Assign columns — valid docs get real values, rest get uniform dist
        result["dominant_topic"] = 0
        result["topic_distribution"] = [[1.0 / n] * n] * n_docs

        dominant = doc_topic_matrix.argmax(axis=1)
        distributions = [row.tolist() for row in doc_topic_matrix]

        valid_indices = result.index[non_empty_mask]
        for i, idx in enumerate(valid_indices):
            result.at[idx, "dominant_topic"] = int(dominant[i])
            result.at[idx, "topic_distribution"] = distributions[i]

        logger.info("Topic modelling complete — %d topics extracted.", n)
        return result, self.topic_data

    # ------------------------------------------------------------------
    # Summary helpers
    # ------------------------------------------------------------------

    def get_topic_summary(self) -> List[Dict[str, Any]]:
        """Return a summary of discovered topics.

        Returns
        -------
        list[dict]
            Each dict has ``topic_id``, ``keywords``, ``weight``.
            Empty list if :meth:`analyze` has not been called.
        """
        if not self.topic_data:
            logger.warning("No topic data available — run analyze() first.")
        return self.topic_data

    def get_top_tfidf_terms(self, n_terms: int = 20) -> List[str]:
        """Return the top *n_terms* from the fitted TF-IDF vocabulary.

        Parameters
        ----------
        n_terms : int
            Number of terms to return.

        Returns
        -------
        list[str]
            Sorted by descending IDF weight.
        """
        if self.vectorizer is None:
            logger.warning("Vectorizer not fitted — run analyze() first.")
            return []
        try:
            idf = self.vectorizer.idf_
            feature_names = self.vectorizer.get_feature_names_out()
            top_indices = np.argsort(idf)[-n_terms:][::-1]
            return [str(feature_names[i]) for i in top_indices]
        except Exception as exc:
            logger.warning("Could not extract TF-IDF terms: %s", exc)
            return []
