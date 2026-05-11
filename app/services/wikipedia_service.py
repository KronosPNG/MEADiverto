"""
Wikipedia enrichment service for MEADiverto semantic wiki.
Retrieves article summaries and images from Wikipedia.
"""

import requests
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

WIKIPEDIA_API = "https://en.wikipedia.org/api/rest_v1/page/summary"


class WikipediaService:
    """Service for retrieving and enriching data from Wikipedia"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'MEADiverto-WikiBot/1.0'
        })
    
    def get_summary(self, title: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve Wikipedia article summary by title.
        
        Args:
            title: Wikipedia article title (e.g., "Beer")
        
        Returns:
            Dictionary with summary data or None if not found
        """
        if not title:
            return None
        
        try:
            url = f"{WIKIPEDIA_API}/{title}"
            response = self.session.get(url, timeout=10)
            
            # Handle redirects and disambiguation
            if response.status_code == 404:
                return None
            
            response.raise_for_status()
            return response.json()
        
        except requests.RequestException as e:
            logger.warning(f"Error retrieving Wikipedia summary for '{title}': {e}")
            return None
    
    def extract_extract(self, summary_data: Dict) -> Optional[str]:
        """
        Extract article summary text from Wikipedia summary data.
        
        Args:
            summary_data: Response from Wikipedia summary API
        
        Returns:
            Article extract/summary text or None
        """
        try:
            return summary_data.get('extract')
        except (KeyError, TypeError):
            return None
    
    def extract_image_url(self, summary_data: Dict) -> Optional[str]:
        """
        Extract thumbnail image URL from Wikipedia summary data.
        
        Args:
            summary_data: Response from Wikipedia summary API
        
        Returns:
            Image URL or None
        """
        try:
            thumbnail = summary_data.get('thumbnail', {})
            return thumbnail.get('source')
        except (KeyError, TypeError):
            return None
    
    def extract_url(self, summary_data: Dict) -> Optional[str]:
        """
        Extract Wikipedia article URL from summary data.
        
        Args:
            summary_data: Response from Wikipedia summary API
        
        Returns:
            Full Wikipedia URL or None
        """
        try:
            content_urls = summary_data.get('content_urls', {})
            return content_urls.get('desktop', {}).get('page')
        except (KeyError, TypeError):
            return None
    
    def get_enriched_data(self, title: str) -> Dict[str, Any]:
        """
        Get all enriched data for a Wikipedia article.
        
        Returns:
            Dictionary with:
            - title: Article title
            - extract: Article summary/abstract
            - image_url: Thumbnail image URL
            - url: Direct link to Wikipedia article
        """
        result = {
            'title': title,
            'extract': None,
            'image_url': None,
            'url': None
        }
        
        summary_data = self.get_summary(title)
        if not summary_data:
            return result
        
        result['extract'] = self.extract_extract(summary_data)
        result['image_url'] = self.extract_image_url(summary_data)
        result['url'] = self.extract_url(summary_data)
        
        return result


# Singleton instance
_wikipedia_service = None

def get_wikipedia_service() -> WikipediaService:
    """Get or create the singleton WikipediaService instance"""
    global _wikipedia_service
    if _wikipedia_service is None:
        _wikipedia_service = WikipediaService()
    return _wikipedia_service
