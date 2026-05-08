"""Entity blueprint for entity pages"""

from flask import Blueprint, render_template, abort
from app import get_graphdb_service

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
    
    return render_template("entity.html", entity=entity_data, breadcrumb=breadcrumb)
