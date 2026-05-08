"""Main blueprint for home and search routes"""

from flask import Blueprint, render_template, request
from app import get_graphdb_service

bp = Blueprint("main", __name__)

@bp.route("/")
def home():
    """Home page with entity listing"""
    graphdb = get_graphdb_service()
    entities = graphdb.get_all_entities()
    return render_template("index.html", entities=entities)

@bp.route("/search")
def search():
    """Search for entities"""
    graphdb = get_graphdb_service()
    query = request.args.get("q", "").strip()
    
    results = []
    if query:
        results = graphdb.search_entities(query)
    
    return render_template("search.html", query=query, results=results)
