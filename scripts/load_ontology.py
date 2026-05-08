#!/usr/bin/env python3
"""Load MEADiverto ontology into GraphDB"""

import requests
import os
from pathlib import Path

# Configuration
GRAPHDB_BASE_URL = "http://localhost:7200"
REPOSITORY_ID = "meadiverto"
ONTOLOGY_FILE = Path(__file__).parent.parent / "ontology" / "MEADiverto.ttl"

def load_ontology():
    """Upload the MEADiverto ontology to GraphDB repository"""
    
    if not ONTOLOGY_FILE.exists():
        print(f"Error: Ontology file not found at {ONTOLOGY_FILE}")
        return False
    
    # Read the TTL file
    with open(ONTOLOGY_FILE, 'r', encoding='utf-8') as f:
        rdf_data = f.read()
    
    # Upload endpoint
    upload_url = f"{GRAPHDB_BASE_URL}/repositories/{REPOSITORY_ID}/statements"
    
    headers = {
        "Content-Type": "application/x-turtle",
    }
    
    try:
        print(f"Uploading ontology from {ONTOLOGY_FILE}...")
        response = requests.post(upload_url, data=rdf_data, headers=headers)
        
        if response.status_code in [200, 204]:
            print(f"✓ Successfully loaded ontology into GraphDB repository '{REPOSITORY_ID}'")
            print(f"  Status: {response.status_code}")
            return True
        else:
            print(f"✗ Failed to upload ontology")
            print(f"  Status: {response.status_code}")
            print(f"  Response: {response.text}")
            return False
    
    except requests.exceptions.ConnectionError:
        print(f"✗ Error: Could not connect to GraphDB at {GRAPHDB_BASE_URL}")
        print(f"  Make sure GraphDB is running on port 7200")
        return False
    except Exception as e:
        print(f"✗ Error uploading ontology: {e}")
        return False

def check_repository():
    """Check if repository exists and has data"""
    try:
        # Check if repository exists
        repos_url = f"{GRAPHDB_BASE_URL}/repositories"
        resp = requests.get(repos_url)
        if resp.status_code != 200:
            print(f"✗ Could not connect to GraphDB")
            return False
        
        # Count triples
        sparql_url = f"{GRAPHDB_BASE_URL}/repositories/{REPOSITORY_ID}"
        query = "SELECT (COUNT(*) as ?count) WHERE { ?s ?p ?o }"
        
        resp = requests.get(sparql_url, params={
            "query": query,
            "format": "json"
        })
        
        if resp.status_code == 200:
            data = resp.json()
            if data.get("results", {}).get("bindings"):
                count = data["results"]["bindings"][0].get("count", {}).get("value", "0")
                print(f"✓ Repository has {count} triples")
                return int(count) > 0
        
        return False
    except Exception as e:
        print(f"✗ Error checking repository: {e}")
        return False

if __name__ == "__main__":
    print("MEADiverto Ontology Loader")
    print("-" * 50)
    
    print("\n1. Checking GraphDB connection...")
    has_data = check_repository()
    
    if has_data:
        print("\n✓ Repository already has data!")
    else:
        print("\n2. Loading ontology into GraphDB...")
        if load_ontology():
            print("\n3. Verifying load...")
            if check_repository():
                print("\n✓ Ontology successfully loaded!")
            else:
                print("\n⚠ Ontology uploaded but verification failed")
        else:
            print("\n✗ Failed to load ontology")
