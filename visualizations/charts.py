"""
Spotify Review Discovery Engine - Plotly Charting Library
=========================================================
Generates Spotify-themed, dark mode interactive charts using Plotly.
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from config import settings


class ChartBuilder:
    """Builds interactive dark-themed Plotly charts for the Streamlit dashboard."""

    def __init__(self) -> None:
        self.template = settings.PLOTLY_TEMPLATE
        self.colors = settings.PLOTLY_COLOR_SEQUENCE

    def _apply_layout_theme(self, fig: go.Figure) -> go.Figure:
        """Applies dark theme styles to a Plotly figure."""
        fig.update_layout(
            template=self.template,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color=settings.SPOTIFY_WHITE, family="sans serif"),
            margin=dict(l=40, r=40, t=60, b=40),
            hovermode="closest",
        )
        # Style axes
        fig.update_xaxes(
            gridcolor=settings.SPOTIFY_MEDIUM_GRAY,
            zerolinecolor=settings.SPOTIFY_MEDIUM_GRAY,
        )
        fig.update_yaxes(
            gridcolor=settings.SPOTIFY_MEDIUM_GRAY,
            zerolinecolor=settings.SPOTIFY_MEDIUM_GRAY,
        )
        return fig

    def sentiment_distribution(self, df: pd.DataFrame) -> go.Figure:
        """Generates a histogram of sentiment scores.

        Parameters
        ----------
        df : pd.DataFrame
            DataFrame containing 'sentiment_compound' and 'sentiment_label'.

        Returns
        -------
        go.Figure
            Plotly figure object.
        """
        if df.empty or "sentiment_compound" not in df.columns:
            return go.Figure()

        # Categorized histogram
        fig = px.histogram(
            df,
            x="sentiment_compound",
            color="sentiment_label",
            color_discrete_map={
                "Positive": settings.SPOTIFY_GREEN,
                "Neutral": settings.SPOTIFY_LIGHT_GRAY,
                "Negative": "#E91429",  # Spotify red-ish accent
            },
            title="How sentiment is spread",
            labels={
                "sentiment_compound": "Sentiment (−1 to +1)",
                "sentiment_label": "Tone",
            },
            nbins=30,
            barmode="overlay",
        )
        fig.update_traces(opacity=0.75)
        return self._apply_layout_theme(fig)

    def rating_distribution(self, df: pd.DataFrame) -> go.Figure:
        """Generates a bar chart of star ratings.

        Parameters
        ----------
        df : pd.DataFrame
            DataFrame containing 'rating' and 'source'.

        Returns
        -------
        go.Figure
            Plotly figure object.
        """
        # Exclude rows without rating (e.g. Reddit)
        df_rated = df[df["rating"].notna() & (df["rating"] > 0)]
        if df_rated.empty:
            # Return empty figure with warning title
            fig = go.Figure()
            fig.update_layout(title="No star ratings in this run (Reddit / forum only)")
            return self._apply_layout_theme(fig)

        # Group by rating and source
        grouped = df_rated.groupby(["rating", "source"]).size().reset_index(name="count")

        fig = px.bar(
            grouped,
            x="rating",
            y="count",
            color="source",
            barmode="group",
            color_discrete_sequence=self.colors,
            title="Star ratings by source",
            labels={"rating": "Stars (1–5)", "count": "Review count", "source": "Source"},
        )
        fig.update_layout(xaxis=dict(tickmode="linear", tick0=1, dtick=1))
        return self._apply_layout_theme(fig)

    def source_comparison(self, df: pd.DataFrame) -> go.Figure:
        """Compares sources based on average sentiment and rating.

        Parameters
        ----------
        df : pd.DataFrame
            Enriched reviews DataFrame.

        Returns
        -------
        go.Figure
            Plotly figure object.
        """
        if df.empty:
            return go.Figure()

        stats = []
        for src, group in df.groupby("source"):
            avg_sent = group["sentiment_compound"].mean() if "sentiment_compound" in group.columns else 0.0
            # Only calculate avg rating for sources with ratings
            rated_group = group[group["rating"].notna() & (group["rating"] > 0)]
            avg_rating = rated_group["rating"].mean() if not rated_group.empty else None

            stats.append(
                {
                    "Source": src,
                    "Avg Sentiment": avg_sent,
                    "Avg Rating": avg_rating if avg_rating is not None else 0.0,
                    "Has Rating": avg_rating is not None,
                }
            )

        df_stats = pd.DataFrame(stats)

        # Create dual-axis comparison or side-by-side bar chart
        fig = go.Figure()

        # Add Avg Sentiment bar
        fig.add_trace(
            go.Bar(
                x=df_stats["Source"],
                y=df_stats["Avg Sentiment"],
                name="Avg sentiment (−1 to +1)",
                marker_color=settings.SPOTIFY_GREEN,
                yaxis="y1",
            )
        )

        fig.update_layout(
            title="Average sentiment by source",
            barmode="group",
            yaxis=dict(title="Sentiment (−1 to +1)", range=[-1, 1]),
        )

        return self._apply_layout_theme(fig)

    def theme_prevalence(self, df: pd.DataFrame, negative_only: bool = False) -> go.Figure:
        """Generates a horizontal bar chart of theme prevalence.

        Parameters
        ----------
        df : pd.DataFrame
            DataFrame containing theme boolean columns.
        negative_only : bool
            When True, count themes among negative reviews only.

        Returns
        -------
        go.Figure
            Plotly figure object.
        """
        theme_cols = [c for c in df.columns if c.startswith("theme_") and c != "theme_count"]
        if not theme_cols:
            return go.Figure()

        subset = df.copy()
        if negative_only:
            if "sentiment_label" in subset.columns:
                subset = subset[subset["sentiment_label"] == "Negative"]
            elif "sentiment_compound" in subset.columns:
                subset = subset[subset["sentiment_compound"] < settings.SENTIMENT_NEGATIVE_THRESHOLD]
            if subset.empty:
                fig = go.Figure()
                fig.update_layout(title="No negative reviews to chart")
                return self._apply_layout_theme(fig)

        counts = subset[theme_cols].sum().reset_index()
        counts.columns = ["theme", "count"]
        counts["theme"] = counts["theme"].str.replace("theme_", "")
        counts = counts[counts["count"] > 0].sort_values(by="count", ascending=True)
        if counts.empty:
            fig = go.Figure()
            fig.update_layout(title="No themed pain areas in negative reviews")
            return self._apply_layout_theme(fig)

        title = "Pain themes in negative reviews" if negative_only else "Which themes come up most"
        x_label = "Negative mentions" if negative_only else "Mentions"

        fig = px.bar(
            counts,
            y="theme",
            x="count",
            orientation="h",
            color="count",
            color_continuous_scale=[settings.SPOTIFY_DARK_GRAY, settings.SPOTIFY_GREEN],
            title=title,
            labels={"theme": "Theme", "count": x_label},
        )
        fig.update_layout(coloraxis_showscale=False)
        return self._apply_layout_theme(fig)

    def theme_cooccurrence_heatmap(self, cooccurrence_matrix: pd.DataFrame) -> go.Figure:
        """Generates a heatmap showing co-occurrence between themes.

        Parameters
        ----------
        cooccurrence_matrix : pd.DataFrame
            Symmetric square DataFrame representing theme intersections.

        Returns
        -------
        go.Figure
            Plotly figure object.
        """
        if cooccurrence_matrix.empty:
            return go.Figure()

        # Rename index and columns to be shorter/cleaner
        clean_matrix = cooccurrence_matrix.copy()
        clean_matrix.index = clean_matrix.index.astype(str).str.replace("theme_", "", regex=False)
        clean_matrix.columns = clean_matrix.columns.astype(str).str.replace("theme_", "", regex=False)

        fig = px.imshow(
            clean_matrix,
            labels=dict(x="Theme A", y="Theme B", color="Overlap Count"),
            x=clean_matrix.columns,
            y=clean_matrix.index,
            color_continuous_scale=[settings.SPOTIFY_DARK_GRAY, settings.SPOTIFY_GREEN],
            title="Themes that appear together",
        )
        return self._apply_layout_theme(fig)

    def sentiment_over_time(self, df: pd.DataFrame) -> go.Figure:
        """Generates a line chart of average sentiment over time.

        Parameters
        ----------
        df : pd.DataFrame
            DataFrame containing 'date' and 'sentiment_compound'.

        Returns
        -------
        go.Figure
            Plotly figure object.
        """
        if df.empty or "date" not in df.columns or "sentiment_compound" not in df.columns:
            return go.Figure()

        df_time = df.copy()
        df_time["date"] = pd.to_datetime(df_time["date"], errors="coerce", utc=True, format="mixed")
        if hasattr(df_time["date"].dt, "tz_convert"):
            df_time["date"] = df_time["date"].dt.tz_convert(None)
        df_time = df_time.dropna(subset=["date"])
        if df_time.empty:
            return go.Figure()

        df_time = df_time.set_index("date")
        daily_avg = df_time["sentiment_compound"].resample("D").mean().reset_index()
        if daily_avg.empty:
            return go.Figure()

        daily_avg["rolling_7d"] = daily_avg["sentiment_compound"].rolling(window=7, min_periods=1).mean()

        fig = go.Figure()

        # Raw Daily Sentiment
        fig.add_trace(
            go.Scatter(
                x=daily_avg["date"],
                y=daily_avg["sentiment_compound"],
                mode="markers",
                name="Daily Avg Sentiment",
                marker=dict(color=settings.SPOTIFY_LIGHT_GRAY, size=5, opacity=0.4),
            )
        )

        # 7-day Rolling Average
        fig.add_trace(
            go.Scatter(
                x=daily_avg["date"],
                y=daily_avg["rolling_7d"],
                mode="lines",
                name="7-day Rolling Avg",
                line=dict(color=settings.SPOTIFY_GREEN, width=3),
            )
        )

        fig.update_layout(
            title="Sentiment Trends Over Time",
            xaxis_title="Date",
            yaxis_title="Average Sentiment (Compound Score)",
            yaxis=dict(range=[-1, 1]),
        )
        return self._apply_layout_theme(fig)

    def topic_visualization(self, topics: list) -> go.Figure:
        """Generates a treemap representing topics and their keywords.

        Parameters
        ----------
        topics : list of dict
            List containing dictionaries with 'topic_id', 'keywords', 'weight'.

        Returns
        -------
        go.Figure
            Plotly figure object.
        """
        if not topics:
            return go.Figure()

        labels = []
        parents = []
        values = []

        # Root node
        labels.append("Discussion themes")
        parents.append("")
        values.append(sum(t.get("weight", 1.0) for t in topics))

        # Add each topic and keywords as leaf nodes
        for topic in topics:
            tid = topic["topic_id"]
            kw_list = topic["keywords"]
            # Main keyword or combined string
            topic_label = f"Topic {tid}: {', '.join(kw_list[:3])}"
            weight = topic.get("weight", 1.0)

            labels.append(topic_label)
            parents.append("Discussion themes")
            values.append(weight)

            # Add keyword children for deep nesting
            for kw in kw_list[:5]:
                labels.append(f"{kw} ({tid})")
                parents.append(topic_label)
                values.append(weight / 5.0)

        fig = go.Figure(
            go.Treemap(
                labels=labels,
                parents=parents,
                values=values,
                branchvalues="total",
                marker=dict(colorscale="Viridis"),
            )
        )
        fig.update_layout(title="What users talk about (by theme)")
        return self._apply_layout_theme(fig)

    def rating_sentiment_scatter(self, df: pd.DataFrame) -> go.Figure:
        """Generates a scatter plot of rating vs sentiment score.

        Parameters
        ----------
        df : pd.DataFrame
            DataFrame containing 'rating' and 'sentiment_compound'.

        Returns
        -------
        go.Figure
            Plotly figure object.
        """
        df_rated = df[df["rating"].notna() & (df["rating"] > 0)]
        if df_rated.empty or "sentiment_compound" not in df.columns:
            return go.Figure()

        # Add jitter to ratings so points don't overlap completely
        import numpy as np

        df_plot = df_rated.copy()
        rng = np.random.default_rng(seed=42)
        df_plot["rating_jittered"] = df_plot["rating"] + rng.uniform(-0.25, 0.25, size=len(df_plot))

        scatter_kwargs = dict(
            x="rating_jittered",
            y="sentiment_compound",
            color="sentiment_label",
            color_discrete_map={
                "Positive": settings.SPOTIFY_GREEN,
                "Neutral": settings.SPOTIFY_LIGHT_GRAY,
                "Negative": "#E91429",
            },
            opacity=0.6,
            title="Do low ratings match negative tone?",
            labels={
                "rating_jittered": "Star rating",
                "sentiment_compound": "Sentiment (−1 to +1)",
                "sentiment_label": "Tone",
            },
        )
        try:
            fig = px.scatter(
                df_plot,
                **scatter_kwargs,
                trendline="ols",
                trendline_color_override=settings.SPOTIFY_WHITE,
            )
        except Exception:
            fig = px.scatter(df_plot, **scatter_kwargs)
        return self._apply_layout_theme(fig)
