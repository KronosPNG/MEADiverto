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
            "child_classes": [],
            "individuals": []
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
        
        # Get individuals (instances) of this class
        individuals_query = f"""
        SELECT ?individual ?individualLabel
        WHERE {{
            ?individual rdf:type <{entity_uri}> .
            OPTIONAL {{ ?individual rdfs:label ?individualLabel . }}
            FILTER NOT EXISTS {{ ?individual rdfs:subClassOf ?parent . }}
        }}
        ORDER BY ?individualLabel
        """
        
        individuals_results = self.run_query(individuals_query)
        
        for binding in individuals_results["results"]["bindings"]:
            individual_uri = binding.get("individual", {}).get("value")
            individual_label = binding.get("individualLabel", {}).get("value") or individual_uri.split("#")[-1]
            if individual_label and not individual_label.startswith("node"):
                entity_data["individuals"].append({
                    "uri": individual_uri,
                    "label": individual_label
                })
        
        # Get external links (rdfs:seeAlso)
        seeAlso_query = f"""
        SELECT ?link
        WHERE {{
            <{entity_uri}> rdfs:seeAlso ?link .
        }}
        """
        
        seeAlso_results = self.run_query(seeAlso_query)
        entity_data["external_links"] = []
        
        for binding in seeAlso_results["results"]["bindings"]:
            link = binding.get("link", {}).get("value")
            if link:
                entity_data["external_links"].append(link)
        
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
    
    def get_hierarchical_entities(self):
        """
        Get entities organized hierarchically.
        Gets main category roots and builds trees under each one.
        Filters out entities that appear as both direct children and descendants.
        
        Returns:
            list: Root level entities with nested children
        """
        def get_all_descendants(uri):
            """Get all descendants of a URI recursively"""
            descendants = set()
            
            def traverse(current_uri, visited=None):
                if visited is None:
                    visited = set()
                if current_uri in visited:
                    return
                visited.add(current_uri)
                
                subclass_query = f"""
                SELECT ?child
                WHERE {{
                    ?child rdfs:subClassOf <{current_uri}> .
                    FILTER(?child != <{current_uri}>)
                }}
                """
                
                results = self.run_query(subclass_query)
                for binding in results["results"]["bindings"]:
                    child_uri = binding.get("child", {}).get("value")
                    if child_uri:
                        descendants.add(child_uri)
                        traverse(child_uri, visited)
            
            traverse(uri)
            return descendants
        
        def build_tree(uri, visited=None, depth=0):
            if visited is None:
                visited = set()
            if uri in visited or depth > 5:
                return None
            visited.add(uri)
            
            # Get label
            label_query = f"""
            SELECT ?label
            WHERE {{
                <{uri}> rdfs:label ?label .
            }}
            LIMIT 1
            """
            label_results = self.run_query(label_query)
            label = None
            if label_results["results"]["bindings"]:
                label = label_results["results"]["bindings"][0].get("label", {}).get("value")
            
            if not label:
                return None
            
            node = {
                "uri": uri,
                "label": label,
                "children": []
            }
            
            # Get direct subclasses
            subclass_query = f"""
            SELECT ?child ?childLabel
            WHERE {{
                ?child rdfs:subClassOf <{uri}> .
                ?child rdfs:label ?childLabel .
                FILTER(?child != <{uri}>)
            }}
            ORDER BY ?childLabel
            """
            
            subclass_results = self.run_query(subclass_query)
            direct_children = []
            for binding in subclass_results["results"]["bindings"]:
                child_uri = binding.get("child", {}).get("value")
                child_label = binding.get("childLabel", {}).get("value")
                if child_label and not child_label.startswith("node") and child_label != "Resource":
                    direct_children.append((child_uri, child_label))
            
            # Build set of all descendants through children
            descendants_through_children = set()
            for child_uri, _ in direct_children:
                descendants_through_children.update(get_all_descendants(child_uri))
            
            # Only add direct children that are NOT descendants through other paths
            for child_uri, child_label in direct_children:
                # Skip if this child is a descendant through another child
                if child_uri in descendants_through_children:
                    continue
                    
                child_node = build_tree(child_uri, visited.copy(), depth + 1)
                if child_node:
                    node["children"].append(child_node)
            
            return node
        
        # First get known root categories by finding entities with many children
        root_query = """
        SELECT ?class ?label (COUNT(?child) as ?childCount)
        WHERE {
            ?class rdfs:label ?label .
            OPTIONAL { ?child rdfs:subClassOf ?class . }
            FILTER(?label NOT IN ("Resource", "NamedIndividual", "Class", "Ingredient", "Thing"))
            FILTER NOT EXISTS { ?class rdf:type rdf:Property }
        }
        GROUP BY ?class ?label
        HAVING (COUNT(?child) >= 2)
        ORDER BY DESC(COUNT(?child))
        LIMIT 15
        """
        
        root_results = self.run_query(root_query)
        hierarchy = []
        seen_uris = set()
        
        for binding in root_results["results"]["bindings"]:
            class_uri = binding.get("class", {}).get("value")
            if class_uri and class_uri not in seen_uris:
                node = build_tree(class_uri)
                if node and node.get("children"):  # Only add if has children
                    hierarchy.append(node)
                    seen_uris.add(class_uri)
        
        return hierarchy
    
    def get_individuals_for_class(self, class_uri):
        """
        Get all individuals (instances) of a given class
        
        Args:
            class_uri: Full URI of the class
            
        Returns:
            list: List of individuals with label and uri
        """
        query = f"""
        SELECT ?individual ?label
        WHERE {{
            ?individual rdf:type <{class_uri}> .
            ?individual rdfs:label ?label .
            FILTER NOT EXISTS {{ ?individual rdfs:subClassOf ?parent . }}
        }}
        ORDER BY ?label
        """
        
        results = self.run_query(query)
        individuals = []
        
        for binding in results["results"]["bindings"]:
            individuals.append({
                "uri": binding.get("individual", {}).get("value"),
                "label": binding.get("label", {}).get("value")
            })
        
        return individuals
