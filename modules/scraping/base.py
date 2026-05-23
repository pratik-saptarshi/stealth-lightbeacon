"""
base.py — Abstract interface for multi-tiered adversarial scraping engines.
"""

from abc import ABC, abstractmethod

class ScrapingEngine(ABC):
    """
    Interface for multi-tiered adversarial scraping engines.
    """
    @abstractmethod
    async def scrape(self, url: str) -> str:
        """
        Executes adversarial web scraping on the target URL, returning HTML content.
        """
        pass
