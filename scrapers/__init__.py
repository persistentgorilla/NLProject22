# Spotify Review Discovery Engine - Scrapers
from scrapers.playstore_scraper import PlayStoreScraper
from scrapers.appstore_scraper import AppStoreScraper
from scrapers.reddit_scraper import RedditScraper
from scrapers.community_scraper import CommunityForumScraper

__all__ = [
    "PlayStoreScraper",
    "AppStoreScraper",
    "RedditScraper",
    "CommunityForumScraper",
]
