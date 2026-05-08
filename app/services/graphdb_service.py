"""GraphDB SPARQL Query Service"""

from SPARQLWrapper import SPARQLWrapper, JSON
import logging

logger = logging.getLogger(__name__)

class GraphDBService:
    """Service for querying GraphDB via SPARQL"""
    
    def __init__(self, endpoint_url):
        """
        Initialize GraphDB service
        
        Args:
            endpoint_url: GraphDB SPARQL endpoint URL
        """
        self.endpoint_url = endpoint_url
        self.sparql = SPARQLWrapper(endpoint_url)
        self.sparql.setReturnFormat(JSON)
    
    def run_query(self, query):
        """
        Execute a SPARQL query
        
        Args:
            query: SPARQL query string
            
        Returns:
            dict: Query results in JSON format
        """
        try:
            self.sparql.setQuery(query)
            results = self.sparql.query().convert()
            return results
        except Exception as e:
            logger.error(f"SPARQL query failed: {e}")
            raise
    
    def get_entity_by_label(self, label):
        """
        Retrieve entity by label
        
        Args:
            label: Entity label to search for
            
        Returns:
            dict: Entity data including label, comment, and properties
        """
        query = f"""
        SELECT DISTINCT ?entity ?label ?comment ?type
        WHERE {{
            ?entity rdfs:label ?label .
            OPTIONAL {{ ?entity rdfs:comment ?comment . }}
            OPTIONAL {{ ?entity rdf:type ?type . }}
            FILTER(STRENDS(STR(?entity), "{label}") || STR(?label) = "{label}")
        }}
        ORDER BY DESC(STR(?label) = "{label}")
        LIMIT 1
        """
        
        results = self.run_query(query)
        
        if results["results"]["bindings"]:
            binding = results["results"]["bindings"][0]
            entity_uri = binding.get("entity", {}).get("value")
            
            if entity_uri:
                return self._build_entity_data(entity_uri)
        
        return None
    
    def _build_entity_data(self, entity_uri):
        """
        Build complete entity data from URI
        
        Args:
            entity_uri: Full URI of the entity
            
        Returns:
            dict: Complete entity data
        """
        # Get label, comment, and type
        entity_info_query = f"""
        SELECT ?label ?comment ?type
        WHERE {{
            <{entity_uri}> rdfs:label ?label .
            OPTIONAL {{ <{entity_uri}> rdfs:comment ?comment . }}
            OPTIONAL {{ <{entity_uri}> rdf:type ?type . }}
        }}
        """
        
        info_results = self.run_query(entity_info_query)
        
        entity_data = {
            "uri": entity_uri,
            "label": None,
            "comment": None,
            "type": None,
            "data_properties": {},
            "object_properties": {},
            "parent_classes": [],
            "child_classes": []
        }
        
        if info_results["results"]["bindings"]:
            binding = info_results["results"]["bindings"][0]
            entity_data["label"] = binding.get("label", {}).get("value")
            entity_data["comment"] = binding.get("comment", {}).get("value")
            entity_data["type"] = binding.get("type", {}).get("value")
        
        # Get all properties
        # First, get properties with their immediate types
        properties_query = f"""
        SELECT DISTINCT ?property ?value ?isObject ?valueLabel
        WHERE {{
            <{entity_uri}> ?property ?value .
            BIND(IF(isIRI(?value), true, false) AS ?isObject)
            OPTIONAL {{ ?value rdfs:label ?valueLabel . }}
            FILTER(?property NOT IN (rdf:type, rdfs:label, rdfs:comment, rdfs:subClassOf, rdfs:seeAlso, owl:topObjectProperty, owl:topDataProperty))
        }}
        """
        
        prop_results = self.run_query(properties_query)
        
        for binding in prop_results["results"]["bindings"]:
            prop_name = binding.get("property", {}).get("value", "").split("#")[-1]
            prop_value = binding.get("value", {}).get("value")
            is_object = binding.get("isObject", {}).get("value") == "true"
            value_label = binding.get("valueLabel", {}).get("value")
            
            # For object properties, get their most meaningful type
            if is_object:
                # Get all types for this value and select the most meaningful one
                type_query = f"""
                SELECT ?type ?typeLabel
                WHERE {{
                    <{prop_value}> rdf:type ?type .
                    OPTIONAL {{ ?type rdfs:label ?typeLabel . }}
                }}
                ORDER BY ?typeLabel
                """
                
                type_results = self.run_query(type_query)
                group_key = "Other"
                
                if type_results["results"]["bindings"]:
                    # Collect all semantic types (non-OWL, non-generic)
                    semantic_types = []
                    for type_binding in type_results["results"]["bindings"]:
                        type_uri = type_binding.get("type", {}).get("value", "")
                        type_label = type_binding.get("typeLabel", {}).get("value") or type_uri.split("#")[-1]
                        
                        # Skip OWL generic types and Resource
                        if type_label and type_label not in ["Resource", "NamedIndividual", "Ingredient"] and not type_label.startswith("node") and not type_uri.startswith("http://www.w3.org/"):
                            semantic_types.append(type_label)
                    
                    # Prioritize specific types - prefer shorter, more specific labels
                    # Also prefer types that match common semantic classifications
                    priority_types = ["Hop", "Malt", "Country", "Fermented Alcoholic Beverage"]
                    
                    group_key = "Other"
                    if semantic_types:
                        # First try to find priority types
                        for ptype in priority_types:
                            if ptype in semantic_types:
                                group_key = ptype
                                break
                        # If no priority match, use the first semantic type
                        if group_key == "Other":
                            group_key = semantic_types[0]
                    elif type_results["results"]["bindings"]:
                        # Fallback to first non-OWL type
                        for type_binding in type_results["results"]["bindings"]:
                            type_uri = type_binding.get("type", {}).get("value", "")
                            type_label = type_binding.get("typeLabel", {}).get("value") or type_uri.split("#")[-1]
                            if type_label and not type_uri.startswith("http://www.w3.org/"):
                                group_key = type_label
                                break
                
                if prop_name not in entity_data["object_properties"]:
                    entity_data["object_properties"][prop_name] = {}
                
                if group_key not in entity_data["object_properties"][prop_name]:
                    entity_data["object_properties"][prop_name][group_key] = []
                
                entity_data["object_properties"][prop_name][group_key].append({
                    "uri": prop_value,
                    "label": value_label or prop_value.split("#")[-1]
                })
            else:
                # For data properties, store as list too for consistency
                if prop_name not in entity_data["data_properties"]:
                    entity_data["data_properties"][prop_name] = []
                entity_data["data_properties"][prop_name].append(prop_value)
        
        # Get parent classes (excluding self-references)
        parent_query = f"""
        SELECT ?parent ?parentLabel
        WHERE {{
            <{entity_uri}> rdfs:subClassOf ?parent .
            OPTIONAL {{ ?parent rdfs:label ?parentLabel . }}
            FILTER(?parent != <{entity_uri}>)
        }}
        """
        
        parent_results = self.run_query(parent_query)
        
        for binding in parent_results["results"]["bindings"]:
            parent_uri = binding.get("parent", {}).get("value")
            if parent_uri == entity_uri:  # Double-check to skip self
                continue
            parent_label = binding.get("parentLabel", {}).get("value") or parent_uri.split("#")[-1]
            # Skip blank nodes (node1, node2, etc.) and Resource
            if parent_label and not parent_label.startswith("node") and parent_label != "Resource":
                entity_data["parent_classes"].append({
                    "uri": parent_uri,
                    "label": parent_label
                })
        
        # Get child classes (excluding self-references)
        child_query = f"""
        SELECT ?child ?childLabel
        WHERE {{
            ?child rdfs:subClassOf <{entity_uri}> .
            OPTIONAL {{ ?child rdfs:label ?childLabel . }}
            FILTER(?child != <{entity_uri}>)
        }}
        """
        
        child_results = self.run_query(child_query)
        
        for binding in child_results["results"]["bindings"]:
            child_uri = binding.get("child", {}).get("value")
            if child_uri == entity_uri:  # Double-check to skip self
                continue
            child_label = binding.get("childLabel", {}).get("value") or child_uri.split("#")[-1]
            # Skip blank nodes (node1, node2, etc.) and Resource
            if child_label and not child_label.startswith("node") and child_label != "Resource":
                entity_data["child_classes"].append({
                    "uri": child_uri,
                    "label": child_label
                })
        
        return entity_data
    
    def get_breadcrumb_hierarchy(self, entity_uri):
        """
        Get breadcrumb hierarchy from root parent to current entity.
        For individuals (instances), finds their rdf:type and shows the class hierarchy.
        For classes, shows the class hierarchy via rdfs:subClassOf.
        Filters out Resource and blank nodes from the path.
        
        Args:
            entity_uri: Full URI of the entity
            
        Returns:
            list: Breadcrumb path of entities
        """
        def get_parents(uri, visited=None, is_instance=False):
            if visited is None:
                visited = set()
            
            if uri in visited:
                return []
            visited.add(uri)
            
            # For instances, use rdf:type; for classes, use rdfs:subClassOf
            if is_instance:
                parent_query = f"""
                SELECT ?parent ?parentLabel
                WHERE {{
                    <{uri}> rdf:type ?parent .
                    OPTIONAL {{ ?parent rdfs:label ?parentLabel . }}
                    FILTER(?parent != <{uri}>)
                }}
                """
            else:
                parent_query = f"""
                SELECT ?parent ?parentLabel
                WHERE {{
                    <{uri}> rdfs:subClassOf ?parent .
                    OPTIONAL {{ ?parent rdfs:label ?parentLabel . }}
                    FILTER(?parent != <{uri}>)
                }}
                """
            
            results = self.run_query(parent_query)
            
            if results["results"]["bindings"]:
                # Collect all valid parents (exclude Resource and blank nodes)
                candidates = []
                for binding in results["results"]["bindings"]:
                    parent_uri = binding.get("parent", {}).get("value")
                    parent_label = binding.get("parentLabel", {}).get("value") or parent_uri.split("#")[-1]
                    
                    # Skip Resource and blank nodes
                    if parent_label and parent_label != "Resource" and not parent_label.startswith("node"):
                        candidates.append({"uri": parent_uri, "label": parent_label})
                
                if candidates:
                    # Prefer more specific parents: try each and pick the one with longest chain
                    best_parent = None
                    best_chain_length = -1
                    
                    for candidate in candidates:
                        # Use a copy of visited to explore each branch independently
                        # After first rdf:type, all parents are classes, so use rdfs:subClassOf
                        chain = get_parents(candidate["uri"], visited.copy(), is_instance=False)
                        if len(chain) > best_chain_length:
                            best_chain_length = len(chain)
                            best_parent = candidate
                    
                    if best_parent:
                        # Recursively get grandparents
                        parents = get_parents(best_parent["uri"], visited, is_instance=False)
                        parents.append(best_parent)
                        return parents
            
            return []
        
        # First check if this is an instance (has rdf:type) or a class (has rdfs:subClassOf)
        type_check_query = f"""
        SELECT ?subclass ?type
        WHERE {{
            OPTIONAL {{ <{entity_uri}> rdfs:subClassOf ?subclass . }}
            OPTIONAL {{ <{entity_uri}> rdf:type ?type . }}
        }}
        LIMIT 1
        """
        
        type_check = self.run_query(type_check_query)
        is_instance = False
        
        if type_check["results"]["bindings"]:
            binding = type_check["results"]["bindings"][0]
            has_subclass = bool(binding.get("subclass", {}).get("value"))
            # Only treat as instance if it doesn't have rdfs:subClassOf (i.e., it's not a class)
            # Classes have rdfs:subClassOf; instances don't
            is_instance = not has_subclass
        
        breadcrumb = get_parents(entity_uri, is_instance=is_instance)
        return breadcrumb
    
    def search_entities(self, search_term):
        """
        Search for entities by label or comment
        
        Args:
            search_term: Search term to match
            
        Returns:
            list: List of matching entities
        """
        search_term_lower = search_term.lower()
        query = f"""
        SELECT ?entity ?label ?comment
        WHERE {{
            ?entity rdfs:label ?label .
            OPTIONAL {{ ?entity rdfs:comment ?comment . }}
            FILTER(
                CONTAINS(LCASE(STR(?label)), "{search_term_lower}") ||
                CONTAINS(LCASE(STR(?comment)), "{search_term_lower}")
            )
        }}
        LIMIT 20
        """
        
        results = self.run_query(query)
        entities = []
        
        for binding in results["results"]["bindings"]:
            entities.append({
                "uri": binding.get("entity", {}).get("value"),
                "label": binding.get("label", {}).get("value"),
                "comment": binding.get("comment", {}).get("value")
            })
        
        return entities
    
    def get_all_entities(self):
        """
        Get all entities in the ontology
        
        Returns:
            list: All entities with labels
        """
        query = """
        SELECT DISTINCT ?entity ?label
        WHERE {
            ?entity rdfs:label ?label .
        }
        ORDER BY ?label
        LIMIT 100
        """
        
        results = self.run_query(query)
        entities = []
        
        for binding in results["results"]["bindings"]:
            entities.append({
                "uri": binding.get("entity", {}).get("value"),
                "label": binding.get("label", {}).get("value")
            })
        
        return entities
