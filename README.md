# MEADiverto — Semantic Wiki for Fermented Alcoholic Beverages

MEADiverto is a semantic wiki that presents an OWL ontology of fermented alcoholic beverages (beers, wines, meads, ciders, sake) as a browsable, wiki-style website. Local RDF knowledge is displayed first and is automatically enriched with images and summaries pulled live from Wikidata and Wikipedia.

## How it works

```
Protégé  →  MEADiverto.ttl (OWL/Turtle ontology)  →  GraphDB (triple store)
                                                          ↓
                                                  Flask application
                                        ┌───────────┬────────────┬─────────────┐
                                   SPARQL/RDF   Wikidata      Wikipedia     HTML
                                     layer      enrichment    enrichment   rendering
                                                          ↓
                                            Browsable semantic wiki
```

1. The ontology is authored in Protégé and stored as Turtle (`ontology/MEADiverto.ttl`).
2. It is loaded into a GraphDB repository, which the Flask app queries live via SPARQL.
3. Each entity page shows its local RDF data (comment, data properties, relationships, class hierarchy) first.
4. If the entity has an `rdfs:seeAlso` link to Wikidata, the app fetches a description and image from Wikidata, and a summary/fallback image from Wikipedia.
5. Everything is rendered as HTML wiki pages with breadcrumb navigation and clickable relationships.

## Tech stack

| Layer | Technology |
|---|---|
| Ontology editing | Protégé (OWL/Turtle) |
| Triple store | GraphDB (SPARQL endpoint) |
| Backend | Flask (Python) |
| RDF querying | `SPARQLWrapper` |
| RDF parsing | `rdflib` |
| External enrichment | Wikidata Entity Data API, Wikipedia REST Summary API |
| Frontend | Jinja2 templates + Bootstrap 5 |

## Project structure

```
app.py                      Flask entry point
config.py                   Environment-based configuration (dev/prod/test)
app/
  __init__.py                Application factory, registers blueprints & GraphDB service
  routes/
    main_bp.py                Home page (hierarchy tree) and search
    entity_bp.py               Entity page: RDF data + Wikidata/Wikipedia enrichment
  services/
    graphdb_service.py         SPARQL queries: entity lookup, hierarchy, breadcrumbs, search
    wikidata_service.py        Wikidata entity fetch, QID extraction, image/description parsing
    wikipedia_service.py       Wikipedia summary fetch, thumbnail/URL extraction
  templates/                  Jinja2 templates (base, index, entity, search, tree_node)
  static/css/                 Custom stylesheet
ontology/
  MEADiverto.ttl              The OWL ontology (39 classes, 136 named individuals)
  catalog-v001.xml            Protégé catalog file
scripts/
  load_ontology.py            Uploads MEADiverto.ttl into a GraphDB repository
requirements.txt
```

## The ontology

`MEADiverto.ttl` models the domain of fermented alcoholic beverages:

- **Beverage taxonomy**: `FermentedAlcoholicBeverage` → `Beer` (`Ale`/`Lager`, plus colour-based anonymous subclasses like `PaleBeer`, `AmberBeer`, `DarkBeer`), `Wine` (`RedWine`, `WhiteWine`, `SparklingWine`, `DessertWine`, `SpicedWine`), `Mead` (`Melomel`, `Metheglin`), `Cider`, `Sake`.
- **Ingredients**: `Ingredient` → `SugarSource` (`Malt`, `Honey`, `Fruit` → `Grape`/`Apple`, `Rice`) and `Botanical` (hops, spices).
- **Geography**: `Country` individuals linked via `originatesFrom`, `isFarmedIn`, `cultivates`.
- **Object properties**: `hasIngredient`/`isUsedIn`, `originatesFrom`/`hasBeverage`, `isFarmedIn`/`cultivates`, `isSimilarTo`, `hasColour`.
- **Data properties**: `colour`, `flavour`, `minABV`, `maxABV`.
- Every class/individual carries `rdfs:label`, `rdfs:comment`, and (where applicable) an `rdfs:seeAlso` link to its Wikidata entity, which drives the enrichment pipeline.

## Setup

### 1. Prerequisites

- Python 3.10+
- [GraphDB](https://graphdb.ontotext.com/) (Community Edition is enough), running locally

### 2. Install dependencies

```bash
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

### 3. Configure environment

Create a `.env` file in the project root:

```env
FLASK_ENV=development
GRAPHDB_ENDPOINT=http://localhost:7200/repositories/meadiverto
```

### 4. Create the GraphDB repository and load the ontology

1. Start GraphDB and create a repository named `meadiverto` (OWL reasoning recommended).
2. Load the ontology into it:

```bash
python scripts/load_ontology.py
```

This checks whether the repository already has data, and if not, uploads `ontology/MEADiverto.ttl` via GraphDB's REST API.

### 5. Run the app

```bash
python app.py
```

Visit `http://127.0.0.1:5000`.

## Features

- **Home page** — hierarchical tree view of the beverage taxonomy.
- **Search** — full-text search over entity labels and comments.
- **Entity pages** (`/entity/<name>`) — label, description, data properties (ABV, colour, flavour), grouped object-property relationships (ingredients, origin, similar beverages), parent/child classes, individuals, and breadcrumb navigation up the class hierarchy.
- **External enrichment** — automatic Wikidata QID extraction from `rdfs:seeAlso`, followed by Wikidata image/description lookup and Wikipedia summary lookup, with image fallback: Wikidata image → Wikipedia thumbnail → none.
