"""Entity blueprint for entity pages"""

from flask import Blueprint, render_template, abort
from app import get_graphdb_service
from app.services.wikidata_service import get_wikidata_service, WikidataService
from app.services.wikipedia_service import get_wikipedia_service

bp = Blueprint("entity", __name__, url_prefix="/entity")

@bp.route("/<name>")
def entity(name):
    """Display entity page"""
    graphdb = get_graphdb_service()
    entity_data = graphdb.get_entity_by_label(name)
    
    if not entity_data:
        abort(404)
    
    # Get breadcrumb hierarchy
    breadcrumb = graphdb.get_breadcrumb_hierarchy(entity_data["uri"])
    
    # Get Wikidata enrichment
    wikidata_service = get_wikidata_service()
    wikidata_data = None
    wikipedia_data = None
    
    # Extract Wikidata QID from external links
    if entity_data.get("external_links"):
        for link in entity_data["external_links"]:
            qid = WikidataService.extract_qid_from_url(link)
            if qid:
                wikidata_data = wikidata_service.get_enriched_data(qid)
                
                # Try to get Wikipedia data using the title from Wikidata
                if wikidata_data.get("wikipedia_title"):
                    wikipedia_service = get_wikipedia_service()
                    wikipedia_data = wikipedia_service.get_enriched_data(wikidata_data["wikipedia_title"])
                
                break
    
    # Determine which image to display (fallback logic)
    # Priority: Wikidata image > Wikipedia image > None
    display_image = None
    if wikidata_data and wikidata_data.get("image_url"):
        display_image = wikidata_data["image_url"]
    elif wikipedia_data and wikipedia_data.get("image_url"):
        display_image = wikipedia_data["image_url"]
    
    return render_template(
        "entity.html", 
        entity=entity_data, 
        breadcrumb=breadcrumb, 
        wikidata=wikidata_data,
        wikipedia=wikipedia_data,
        display_image=display_image
    )
