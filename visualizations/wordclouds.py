"""
Spotify Review Discovery Engine - Word Cloud Generator
======================================================
Creates Spotify-branded, dark background word clouds from review text.
"""

import random

import matplotlib.pyplot as plt
import pandas as pd
from wordcloud import WordCloud
from config import settings


class WordCloudGenerator:
    """Generates word clouds styled with the Spotify green color palette."""

    def __init__(self) -> None:
        self.background_color = settings.SPOTIFY_BLACK
        # Spotify greens/greys color function
        self.colors = [
            settings.SPOTIFY_GREEN,
            settings.SPOTIFY_GREEN_LIGHT,
            "#2EBD59",
            "#57B660",
            "#7BC67E",
            settings.SPOTIFY_WHITE,
            settings.SPOTIFY_LIGHT_GRAY,
        ]

    def _spotify_color_func(self, word, font_size, position, orientation, random_state=None, **kwargs):
        """Custom color function for Spotify themes."""
        return random.choice(self.colors)

    def generate(self, text: str, title: str) -> plt.Figure:
        """Generates a word cloud from a raw text string.

        Parameters
        ----------
        text : str
            Full text body to generate the word cloud from.
        title : str
            Title of the word cloud figure.

        Returns
        -------
        plt.Figure
            Matplotlib figure containing the word cloud.
        """
        fig, ax = plt.subplots(figsize=(10, 5), facecolor=self.background_color)
        
        if not text or not text.strip():
            # If no text, return empty figure with notice
            ax.text(
                0.5,
                0.5,
                "No text data to display",
                color=settings.SPOTIFY_WHITE,
                ha="center",
                va="center",
                fontsize=14,
            )
            ax.set_facecolor(self.background_color)
            ax.axis("off")
            return fig

        # Load standard and custom stopwords
        from wordcloud import STOPWORDS
        stopwords = set(STOPWORDS)
        stopwords.update([w.lower() for w in settings.CUSTOM_STOPWORDS])

        wc = WordCloud(
            width=800,
            height=400,
            background_color=self.background_color,
            stopwords=stopwords,
            max_words=100,
            collocations=False,
        ).generate(text)

        # Apply Spotify colors
        wc.recolor(color_func=self._spotify_color_func, random_state=42)

        ax.imshow(wc, interpolation="bilinear")
        ax.axis("off")
        ax.set_title(title, color=settings.SPOTIFY_WHITE, fontsize=16, pad=15)
        fig.tight_layout(pad=0)
        
        return fig

    def generate_by_sentiment(self, df: pd.DataFrame, sentiment_label: str) -> plt.Figure:
        """Generates a word cloud filtered by sentiment.

        Parameters
        ----------
        df : pd.DataFrame
            Enriched reviews DataFrame.
        sentiment_label : str
            'Positive', 'Neutral', or 'Negative'.

        Returns
        -------
        plt.Figure
            Matplotlib figure containing the word cloud.
        """
        if df.empty or "sentiment_label" not in df.columns:
            return self.generate("", f"{sentiment_label} Reviews Word Cloud")

        sub_df = df[df["sentiment_label"] == sentiment_label]
        all_text = " ".join(sub_df["review_text"].dropna().astype(str).tolist())
        return self.generate(all_text, f"{sentiment_label} Reviews Word Cloud")

    def generate_by_theme(self, df: pd.DataFrame, theme_name: str) -> plt.Figure:
        """Generates a word cloud filtered by theme.

        Parameters
        ----------
        df : pd.DataFrame
            Enriched reviews DataFrame.
        theme_name : str
            Theme name to filter by (e.g. 'Discovery Frustrations').

        Returns
        -------
        plt.Figure
            Matplotlib figure containing the word cloud.
        """
        theme_col = f"theme_{theme_name}"
        if df.empty or theme_col not in df.columns:
            return self.generate("", f"Theme: {theme_name} Word Cloud")

        sub_df = df[df[theme_col].astype(bool)]
        all_text = " ".join(sub_df["review_text"].dropna().astype(str).tolist())
        return self.generate(all_text, f"Theme: {theme_name} Word Cloud")
