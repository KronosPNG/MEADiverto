"""
Wikidata enrichment service for MEADiverto semantic wiki.
Retrieves images, descriptions, and metadata from Wikidata.
"""

import requests
import logging
import re
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

WIKIDATA_API = "https://www.wikidata.org/wiki/Special:EntityData"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"


class WikidataService:
    """Service for retrieving and enriching data from Wikidata"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'MEADiverto-WikiBot/1.0'
        })
    
    @staticmethod
    def extract_qid_from_url(url: str) -> Optional[str]:
        """
        Extract Wikidata QID from a Wikidata URL.
        
        Examples:
            https://www.wikidata.org/wiki/Q44 -> Q44
            https://www.wikidata.org/entity/Q44 -> Q44
        """
        if not url:
            return None
        
        match = re.search(r'(Q\d+)', str(url))
        if match:
            return match.group(1)
        return None
    
    def get_entity(self, qid: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve Wikidata entity data by QID.
        
        Args:
            qid: Wikidata ID (e.g., "Q44" for beer)
        
        Returns:
            Dictionary with entity data or None if not found
        """
        if not qid:
            return None
        
        try:
            url = f"{WIKIDATA_API}/{qid}.json"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.warning(f"Error retrieving Wikidata entity {qid}: {e}")
            return None
    
    def extract_english_label(self, entity_data: Dict) -> Optional[str]:
        """Extract English label from Wikidata entity data"""
        try:
            labels = entity_data.get('entities', {}).get(list(entity_data.get('entities', {}).keys())[0], {}).get('labels', {})
            return labels.get('en', {}).get('value')
        except (KeyError, IndexError):
            return None
    
    def extract_english_description(self, entity_data: Dict) -> Optional[str]:
        """Extract English description from Wikidata entity data"""
        try:
            entity_id = list(entity_data.get('entities', {}).keys())[0]
            descriptions = entity_data.get('entities', {}).get(entity_id, {}).get('descriptions', {})
            return descriptions.get('en', {}).get('value')
        except (KeyError, IndexError):
            return None
    
    def extract_image_url(self, entity_data: Dict) -> Optional[str]:
        """
        Extract image URL from Wikidata entity (P18 = image property).
        Returns full Wikimedia Commons URL for the image.
        """
        try:
            entity_id = list(entity_data.get('entities', {}).keys())[0]
            claims = entity_data.get('entities', {}).get(entity_id, {}).get('claims', {})
            
            # P18 is the image property
            image_claims = claims.get('P18', [])
            if not image_claims:
                return None
            
            # Get the first image
            image_claim = image_claims[0]
            image_name = image_claim.get('mainsnak', {}).get('datavalue', {}).get('value')
            
            if not image_name:
                return None
            
            # Convert image name to Wikimedia Commons URL
            return self._build_commons_url(image_name)
        
        except (KeyError, IndexError, TypeError):
            return None
    
    @staticmethod
    def _build_commons_url(image_name: str) -> str:
        """
        Build Wikimedia Commons image URL from image name.
        
        Example:
            "Wikipedia-logo-v2.png" -> 
            "https://commons.wikimedia.org/wiki/Special:FilePath/Wikipedia-logo-v2.png"
        """
        # URL encode the image name
        encoded_name = image_name.replace(' ', '_')
        return f"https://commons.wikimedia.org/wiki/Special:FilePath/{encoded_name}"
    
    def extract_wikipedia_title(self, entity_data: Dict) -> Optional[str]:
        """
        Extract English Wikipedia article title from Wikidata entity.
        """
        try:
            entity_id = list(entity_data.get('entities', {}).keys())[0]
            sitelinks = entity_data.get('entities', {}).get(entity_id, {}).get('sitelinks', {})
            wikipedia_data = sitelinks.get('enwiki', {})
            return wikipedia_data.get('title')
        except (KeyError, IndexError):
            return None
    
    def get_enriched_data(self, qid: str) -> Dict[str, Any]:
        """
        Get all enriched data for a Wikidata entity.
        
        Returns:
            Dictionary with:
            - qid: Wikidata ID
            - label: English label
            - description: English description
            - image_url: URL to image on Wikimedia Commons
            - wikipedia_title: English Wikipedia article title
            - wikidata_url: Direct link to Wikidata entity
        """
        result = {
            'qid': qid,
            'label': None,
            'description': None,
            'image_url': None,
            'wikipedia_title': None,
            'wikidata_url': f'https://www.wikidata.org/wiki/{qid}'
        }
        
        entity_data = self.get_entity(qid)
        if not entity_data:
            return result
        
        result['label'] = self.extract_english_label(entity_data)
        result['description'] = self.extract_english_description(entity_data)
        result['image_url'] = self.extract_image_url(entity_data)
        result['wikipedia_title'] = self.extract_wikipedia_title(entity_data)
        
        return result


# Singleton instance
_wikidata_service = None

def get_wikidata_service() -> WikidataService:
    """Get or create the singleton WikidataService instance"""
    global _wikidata_service
    if _wikidata_service is None:
        _wikidata_service = WikidataService()
    return _wikidata_service
