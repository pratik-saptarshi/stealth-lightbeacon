"""
modules/scraping package exposing pluggable ScrapingEngines and selectors.
"""

from modules.scraping.base import ScrapingEngine
from modules.scraping.obscura import ObscuraEngine
from modules.scraping.zendriver import ZendriverEngine
from modules.scraping.stealth_mcp import StealthMcpLayer
from modules.scraping.factory import ScrapingFactory
