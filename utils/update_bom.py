"""
update_bom.py — Core utility to automatically update the Bill of Materials (BOM).
Parses requirements.txt and updates library versions dynamically inside bill-of-material.md.
"""

import os
import re

# Standard Descriptions catalog for core dependencies
DESCRIPTIONS = {
    "requests": "Fallback synchronous HTTP client.",
    "beautifulsoup4": "Fallback static HTML parser.",
    "lxml": "Fast XML and HTML parsing backend.",
    "Jinja2": "Autoescaped layout templating engine.",
    "colorama": "Terminal colors compatibility support.",
    "python-dotenv": "Environment variables loader.",
    "tldextract": "Accurate domain and subdomain parser.",
    "rich": "Rich formatting and console output tables.",
    "httpx": "Non-blocking asynchronous HTTP/2 client.",
    "typer": "High-fidelity command-line interface.",
    "pytest": "Core unit and integration testing engine.",
    "pytest-asyncio": "Asynchronous loop fixtures decorator.",
    "selectolax": "High-performance HTML parsing backend.",
    "pytest-benchmark": "Performance and benchmarking suite.",
    "rich-click": "Beautiful rich-click CLI help formatting."
}

def parse_requirements(filepath: str):
    """
    Parses library names and exact version specifiers from a requirements file.
    """
    libraries = []
    if not os.path.exists(filepath):
        return libraries
        
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # Parse library and specifier (e.g. requests>=2.31.0)
            match = re.match(r"^([a-zA-Z0-9_\-]+)\s*(>=|==|>|<|<=)?\s*([0-9\.\*a-zA-Z]+)?", line)
            if match:
                name = match.group(1)
                specifier = match.group(2) or ""
                version = match.group(3) or ""
                libraries.append((name, specifier + version))
    return libraries

def update_bom(bom_path: str, req_path: str):
    """
    Locates comment anchors in the BOM file and updates the dependency list.
    """
    if not os.path.exists(bom_path):
        print(f"Error: BOM file not found at {bom_path}")
        return False
        
    libraries = parse_requirements(req_path)
    if not libraries:
        print(f"Warning: No libraries parsed from {req_path}")
        return False
        
    # Build the new markdown block
    lines = []
    for name, version in libraries:
        # Resolve clean casing matching description catalogue keys
        desc_key = next((k for k in DESCRIPTIONS if k.lower() == name.lower()), name)
        desc = DESCRIPTIONS.get(desc_key, "Dynamic software dependency.")
        lines.append(f"* **{desc_key}** (`{version}`): {desc}")
        
    new_block = "<!-- LIBRARIES_START -->\n" + "\n".join(lines) + "\n<!-- LIBRARIES_END -->"
    
    with open(bom_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    # Search and replace between tags
    pattern = r"<!-- LIBRARIES_START -->.*?<!-- LIBRARIES_END -->"
    updated_content, count = re.subn(pattern, new_block, content, flags=re.DOTALL)
    
    if count > 0:
        with open(bom_path, "w", encoding="utf-8") as f:
            f.write(updated_content)
        print(f"✔ Successfully synchronized {len(libraries)} dependencies inside {bom_path}.")
        return True
    else:
        print("Error: Could not find <!-- LIBRARIES_START --> / <!-- LIBRARIES_END --> anchors.")
        return False

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    bom_file = os.path.join(base_dir, "bill-of-material.md")
    req_file = os.path.join(base_dir, "requirements.txt")
    update_bom(bom_file, req_file)
