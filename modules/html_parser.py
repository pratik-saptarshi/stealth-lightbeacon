"""
html_parser.py — Unified HTML Parser and Node Adapter supporting BeautifulSoup and Selectolax.
Provides standard BeautifulSoup-like APIs (find, find_all, get_text, get, string, parents, decompose)
with transparent performance boost using Selectolax if available.
"""

import re
import logging
from typing import Union, List, Dict, Any, Optional, Generator

logger = logging.getLogger("html_parser")

# --- Try Selectolax Imports ---
try:
    from selectolax.parser import HTMLParser as SelectolaxParser
    from selectolax.parser import Node as SelectolaxNode
    SELECTOLAX_AVAILABLE = True
except ImportError:
    SELECTOLAX_AVAILABLE = False

# --- BS4 Imports ---
from bs4 import BeautifulSoup, Tag

# --- Global Backend Configuration ---
# By default, use selectolax if available, else fallback to bs4.
BACKEND = "selectolax" if SELECTOLAX_AVAILABLE else "bs4"

def force_backend(name: str):
    """
    Forces the parser to use a specific backend: 'selectolax' or 'bs4'.
    """
    global BACKEND
    if name == "selectolax" and not SELECTOLAX_AVAILABLE:
        logger.warning("Selectolax is not installed. Falling back to bs4.")
        BACKEND = "bs4"
    elif name in ["selectolax", "bs4"]:
        BACKEND = name
    else:
        raise ValueError(f"Unknown backend: {name}")

# --- Python-side Element Filtering Heuristics ---
def _matches_filter(node: Any, name: Any = None, attrs: Optional[Dict[str, Any]] = None, **kwargs) -> bool:
    """
    Helper to filter nodes using standard BeautifulSoup search semantics.
    """
    # 1. Match tag name
    if name:
        if isinstance(name, list):
            if node.name not in name:
                return False
        elif hasattr(name, "search") or hasattr(name, "match"):  # Regex
            if not name.search(node.name):
                return False
        elif node.name != name:
            return False

    # 2. Match attrs dictionary
    if attrs:
        for k, v in attrs.items():
            if k not in node.attrs:
                return False
            actual_val = node.attrs[k]
            if v is True:  # Attribute presence check
                continue
            if isinstance(v, list):
                actual_list = actual_val if isinstance(actual_val, list) else str(actual_val).split()
                if not all(item in actual_list for item in v):
                    return False
            elif actual_val != v:
                return False

    # 3. Match kwargs (attributes and special keywords like class_)
    for k, v in kwargs.items():
        real_k = "class" if k == "class_" else k
        # Strip trailing underscore (e.g. property_ -> property)
        if real_k.endswith("_") and real_k != "class":
            real_k = real_k[:-1]
            
        if real_k not in node.attrs:
            return False
        if v is True:
            continue
            
        actual_val = node.attrs[real_k]
        if real_k == "class" and isinstance(v, str):
            actual_list = actual_val if isinstance(actual_val, list) else str(actual_val).split()
            if v not in actual_list:
                return False
        elif actual_val != v:
            return False

    return True

def _selector_for_query(name: Any = None, attrs: Optional[Dict[str, Any]] = None, **kwargs) -> str:
    """
    Generates a candidate CSS selector for the query to speed up Selectolax lookups.
    """
    if not name:
        return "*"
    if isinstance(name, list):
        return ", ".join(name)
    if hasattr(name, "search") or hasattr(name, "match"):  # Regex tag name
        return "*"
    return name


# ==============================================================================
# BeautifulSoup Backend Implementation
# ==============================================================================
class BS4NodeWrapper:
    def __init__(self, node: Tag):
        self._node = node

    @property
    def name(self) -> str:
        return self._node.name

    @property
    def text(self) -> str:
        return self._node.get_text()

    def get_text(self) -> str:
        return self._node.get_text()

    @property
    def string(self) -> Optional[str]:
        return self._node.string

    @property
    def attrs(self) -> Dict[str, Any]:
        return self._node.attrs

    def get(self, key: str, default: Any = None) -> Any:
        return self._node.get(key, default)

    def __getitem__(self, key: str) -> Any:
        return self._node[key]

    def __contains__(self, key: str) -> bool:
        return key in self._node.attrs

    def __str__(self) -> str:
        return str(self._node)

    @property
    def parents(self) -> Generator['BS4NodeWrapper', None, None]:
        for p in self._node.parents:
            if isinstance(p, Tag):
                yield BS4NodeWrapper(p)

    def find_parent(self, name: str) -> Optional['BS4NodeWrapper']:
        p = self._node.find_parent(name)
        return BS4NodeWrapper(p) if p else None

    def find_next(self, name: str = None, **kwargs) -> Optional['BS4NodeWrapper']:
        res = self._node.find_next(name, **kwargs)
        return BS4NodeWrapper(res) if res else None

    def decompose(self):
        self._node.decompose()

    def find(self, name=None, attrs=None, **kwargs) -> Optional['BS4NodeWrapper']:
        res = self._node.find(name, attrs, **kwargs)
        return BS4NodeWrapper(res) if res else None

    def find_all(self, name=None, attrs=None, **kwargs) -> List['BS4NodeWrapper']:
        res = self._node.find_all(name, attrs, **kwargs)
        return [BS4NodeWrapper(x) for x in res]


class BS4ParserWrapper:
    def __init__(self, html: str):
        self.soup = BeautifulSoup(html, "lxml")

    def find(self, name=None, attrs=None, **kwargs) -> Optional[BS4NodeWrapper]:
        res = self.soup.find(name, attrs, **kwargs)
        return BS4NodeWrapper(res) if res else None

    def find_all(self, name=None, attrs=None, **kwargs) -> List[BS4NodeWrapper]:
        res = self.soup.find_all(name, attrs, **kwargs)
        return [BS4NodeWrapper(x) for x in res]

    def get_text(self) -> str:
        return self.soup.get_text()


# ==============================================================================
# Selectolax Backend Implementation
# ==============================================================================
if SELECTOLAX_AVAILABLE:
    class SelectolaxNodeWrapper:
        def __init__(self, node: SelectolaxNode):
            self._node = node

        @property
        def name(self) -> str:
            # Special case for Selectolax tag names
            tag = self._node.tag
            if tag == "-text":
                return "#text"
            return tag

        @property
        def text(self) -> str:
            return self._node.text(deep=True)

        def get_text(self) -> str:
            return self._node.text(deep=True)

        @property
        def string(self) -> Optional[str]:
            child = self._node.child
            has_element_child = False
            while child is not None:
                if child.tag not in ["-text", "-comment"]:
                    has_element_child = True
                    break
                child = child.next

            if has_element_child:
                return None

            val = self._node.text(deep=False)
            return val if val else None

        @property
        def attrs(self) -> Dict[str, Any]:
            # BS4 attributes lists classes as list, selectolax is a raw string.
            attrs_dict = dict(self._node.attributes)
            if "class" in attrs_dict and isinstance(attrs_dict["class"], str):
                attrs_dict["class"] = attrs_dict["class"].split()
            return attrs_dict

        def get(self, key: str, default: Any = None) -> Any:
            attrs_dict = self.attrs
            return attrs_dict.get(key, default)

        def __getitem__(self, key: str) -> Any:
            attrs_dict = self.attrs
            if key not in attrs_dict:
                raise KeyError(key)
            return attrs_dict[key]

        def __contains__(self, key: str) -> bool:
            return key in self._node.attributes

        def __str__(self) -> str:
            return self._node.html or ""

        @property
        def parents(self) -> Generator['SelectolaxNodeWrapper', None, None]:
            p = self._node.parent
            while p is not None:
                if p.tag not in ["-html", "-root"]:
                    yield SelectolaxNodeWrapper(p)
                p = p.parent

        def find_parent(self, name: str) -> Optional['SelectolaxNodeWrapper']:
            p = self._node.parent
            while p is not None:
                if p.tag == name:
                    return SelectolaxNodeWrapper(p)
                p = p.parent
            return None

        def find_next(self, name: str = None, **kwargs) -> Optional['SelectolaxNodeWrapper']:
            # Document order next node traversal:
            curr = self._node
            while curr:
                if curr.child:
                    curr = curr.child
                elif curr.next:
                    curr = curr.next
                else:
                    parent = curr.parent
                    while parent and not parent.next:
                        parent = parent.parent
                    curr = parent.next if parent else None

                if curr and curr.tag not in ["-text", "-comment", "-root"]:
                    wrapper = SelectolaxNodeWrapper(curr)
                    if _matches_filter(wrapper, name, **kwargs):
                        return wrapper
            return None

        def decompose(self):
            # Selectolax strip() or decompose()
            if hasattr(self._node, "decompose"):
                self._node.decompose()
            elif hasattr(self._node, "strip"):
                self._node.strip()

        def find(self, name=None, attrs=None, **kwargs) -> Optional['SelectolaxNodeWrapper']:
            selector = _selector_for_query(name, attrs, **kwargs)
            candidates = self._node.css(selector)
            for c in candidates:
                wrapper = SelectolaxNodeWrapper(c)
                if _matches_filter(wrapper, name, attrs, **kwargs):
                    return wrapper
            return None

        def find_all(self, name=None, attrs=None, **kwargs) -> List['SelectolaxNodeWrapper']:
            selector = _selector_for_query(name, attrs, **kwargs)
            candidates = self._node.css(selector)
            results = []
            for c in candidates:
                wrapper = SelectolaxNodeWrapper(c)
                if _matches_filter(wrapper, name, attrs, **kwargs):
                    results.append(wrapper)
            return results


    class SelectolaxParserWrapper:
        def __init__(self, html: str):
            self.tree = SelectolaxParser(html)

        def find(self, name=None, attrs=None, **kwargs) -> Optional[SelectolaxNodeWrapper]:
            selector = _selector_for_query(name, attrs, **kwargs)
            candidates = self.tree.css(selector)
            for c in candidates:
                wrapper = SelectolaxNodeWrapper(c)
                if _matches_filter(wrapper, name, attrs, **kwargs):
                    return wrapper
            return None

        def find_all(self, name=None, attrs=None, **kwargs) -> List[SelectolaxNodeWrapper]:
            selector = _selector_for_query(name, attrs, **kwargs)
            candidates = self.tree.css(selector)
            results = []
            for c in candidates:
                wrapper = SelectolaxNodeWrapper(c)
                if _matches_filter(wrapper, name, attrs, **kwargs):
                    results.append(wrapper)
            return results

        def get_text(self) -> str:
            if self.tree.root:
                return self.tree.root.text(deep=True)
            return ""


# ==============================================================================
# Unified Public Interface
# ==============================================================================
class HtmlNode:
    """
    Unified Node class exposed to the application.
    Conforms to the BeautifulSoup element protocol.
    """
    def __init__(self, wrapped_node: Any):
        self._wrapped = wrapped_node

    @property
    def name(self) -> str:
        return self._wrapped.name

    @property
    def text(self) -> str:
        return self._wrapped.text

    def get_text(self) -> str:
        return self._wrapped.get_text()

    @property
    def string(self) -> Optional[str]:
        return self._wrapped.string

    @property
    def attrs(self) -> Dict[str, Any]:
        return self._wrapped.attrs

    def get(self, key: str, default: Any = None) -> Any:
        return self._wrapped.get(key, default)

    def __getitem__(self, key: str) -> Any:
        return self._wrapped[key]

    def __contains__(self, key: str) -> bool:
        return key in self._wrapped

    def __str__(self) -> str:
        return str(self._wrapped)

    @property
    def parents(self) -> Generator['HtmlNode', None, None]:
        for p in self._wrapped.parents:
            yield HtmlNode(p)

    def find_parent(self, name: str) -> Optional['HtmlNode']:
        p = self._wrapped.find_parent(name)
        return HtmlNode(p) if p else None

    def find_next(self, name: str = None, **kwargs) -> Optional['HtmlNode']:
        p = self._wrapped.find_next(name, **kwargs)
        return HtmlNode(p) if p else None

    def decompose(self):
        self._wrapped.decompose()

    def find(self, name=None, attrs=None, **kwargs) -> Optional['HtmlNode']:
        p = self._wrapped.find(name, attrs, **kwargs)
        return HtmlNode(p) if p else None

    def find_all(self, name=None, attrs=None, **kwargs) -> List['HtmlNode']:
        res = self._wrapped.find_all(name, attrs, **kwargs)
        return [HtmlNode(x) for x in res]


class HtmlParser:
    """
    Unified Document Parser class exposed to the application.
    """
    def __init__(self, html: str):
        if BACKEND == "selectolax" and SELECTOLAX_AVAILABLE:
            self._parser = SelectolaxParserWrapper(html)
        else:
            self._parser = BS4ParserWrapper(html)

    def find(self, name=None, attrs=None, **kwargs) -> Optional[HtmlNode]:
        p = self._parser.find(name, attrs, **kwargs)
        return HtmlNode(p) if p else None

    def find_all(self, name=None, attrs=None, **kwargs) -> List[HtmlNode]:
        res = self._parser.find_all(name, attrs, **kwargs)
        return [HtmlNode(x) for x in res]

    def __call__(self, name=None, attrs=None, **kwargs) -> List[HtmlNode]:
        return self.find_all(name, attrs, **kwargs)

    def get_text(self) -> str:
        return self._parser.get_text()
