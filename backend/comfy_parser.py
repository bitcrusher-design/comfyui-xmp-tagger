import json
import re
import os
from typing import Dict, List, Any, Optional, Set
from PIL import Image
import xml.etree.ElementTree as ET

def extract_existing_tags_from_xmp(xmp_str: str) -> List[str]:
    """
    Extracts all existing tags (keywords) from an XMP XML string.
    Only matches tag/keyword specific containers (subject, tags, keywords)
    to avoid false positives from other metadata list elements (creator, dates, etc.).
    """
    if not xmp_str or not isinstance(xmp_str, str):
        return []
    tags = []
    try:
        cleaned_xml = re.sub(r'<\?xpacket.*?\?>', '', xmp_str, flags=re.DOTALL).strip()
        if not cleaned_xml:
            return []
        root = ET.fromstring(cleaned_xml)
        
        RDF_NS = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
        descriptions = root.findall(f".//{{{RDF_NS}}}Description")
        
        for desc in descriptions:
            for child in list(desc):
                tag_name_lower = child.tag.lower()
                if any(bad in tag_name_lower for bad in ["subject", "tags", "keyword"]):
                    # Extract list items if present
                    li_elements = child.findall(f".//{{{RDF_NS}}}li")
                    if li_elements:
                        for li in li_elements:
                            if li.text and li.text.strip():
                                tags.append(li.text.strip())
                    elif child.text and child.text.strip():
                        tags.append(child.text.strip())
    except Exception:
        pass
    return list(dict.fromkeys(tags))

def extract_all_xmp_properties(xmp_str: str) -> Dict[str, str]:
    """
    Extracts all metadata properties and values from an XMP XML string.
    Maps common namespaces to clean prefixes and returns a dictionary.
    """
    if not xmp_str or not isinstance(xmp_str, str):
        return {}
    
    properties = {}
    try:
        # Strip packet headers if present
        xml_content = xmp_str.strip()
        if xml_content.startswith("<?xpacket"):
            start_idx = xml_content.find("<x:xmpmeta")
            if start_idx == -1:
                start_idx = xml_content.find("<rdf:RDF")
            if start_idx != -1:
                xml_content = xml_content[start_idx:]
                end_packet = xml_content.find("<?xpacket end")
                if end_packet != -1:
                    xml_content = xml_content[:end_packet]
            xml_content = xml_content.strip()

        root = ET.fromstring(xml_content)
        
        RDF_NS = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
        descriptions = root.findall(f".//{{{RDF_NS}}}Description")
        if not descriptions:
            descriptions = [elem for elem in root.iter() if elem.tag.endswith("Description")]
            
        for desc in descriptions:
            # First check attributes on rdf:Description itself
            for attr_name, attr_val in desc.attrib.items():
                if attr_val and attr_val.strip():
                    if attr_name.startswith("{"):
                        ns, local = attr_name[1:].split("}")
                        prefix = ns.split("/")[-1].split("#")[0]
                        properties[f"{prefix}:{local}"] = attr_val.strip()
                    else:
                        properties[attr_name] = attr_val.strip()
                    
            # Next check all child elements
            for child in desc:
                tag_name = child.tag
                if tag_name.startswith("{"):
                    ns, local = tag_name[1:].split("}")
                    ns_map = {
                        "http://ns.adobe.com/xap/1.0/": "xmp",
                        "http://ns.adobe.com/tiff/1.0/": "tiff",
                        "http://purl.org/dc/elements/1.1/": "dc",
                        "http://ns.adobe.com/exif/1.0/": "exif",
                        "http://ns.adobe.com/lightroom/1.0/": "lr",
                        "http://www.digikam.org/ns/1.0/": "digiKam",
                        "http://ns.adobe.com/xap/1.0/rights/": "xmpRights"
                    }
                    prefix = ns_map.get(ns, ns.split("/")[-1].split("#")[0])
                    key = f"{prefix}:{local}"
                else:
                    key = child.tag
                
                val = ""
                container = None
                for c_tag in ["Bag", "Seq", "Alt"]:
                    container = child.find(f".//{{{RDF_NS}}}{c_tag}")
                    if container is not None:
                        break
                if container is None:
                    for sub in child:
                        if sub.tag.endswith("Bag") or sub.tag.endswith("Seq") or sub.tag.endswith("Alt"):
                            container = sub
                            break
                            
                if container is not None:
                    items = []
                    for li in container:
                        if li.text and li.text.strip():
                            items.append(li.text.strip())
                    if items:
                        val = ", ".join(items)
                else:
                    if child.text and child.text.strip():
                        val = child.text.strip()
                
                if val:
                    properties[key] = val
    except Exception as e:
        print(f"Error parsing XMP properties: {e}")
        
    return properties


class ComfyMetadata:
    def __init__(self):
        self.width: Optional[int] = None
        self.height: Optional[int] = None
        self.megapixels: Optional[float] = None
        self.checkpoints: List[str] = []
        self.loras: List[str] = []
        self.samplers: List[str] = []
        self.schedulers: List[str] = []
        self.steps: Optional[int] = None
        self.cfg: Optional[float] = None
        self.positive_prompts: List[str] = []
        self.positive_prompts_sources: Dict[str, str] = {}
        self.prompt_tags: List[str] = []
        self.raw_prompt_json: Optional[Dict[str, Any]] = None
        self.raw_workflow_json: Optional[Dict[str, Any]] = None
        self.has_existing_xmp: bool = False
        self.existing_xmp_tags: List[str] = []
        self.existing_xmp_properties: Dict[str, str] = {}
        self.raw_xmp_str: Optional[str] = None
        self.creation_date: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "width": self.width,
            "height": self.height,
            "megapixels": self.megapixels,
            "checkpoints": self.checkpoints,
            "loras": self.loras,
            "samplers": self.samplers,
            "schedulers": self.schedulers,
            "steps": self.steps,
            "cfg": self.cfg,
            "positive_prompts": self.positive_prompts,
            "prompt_tags": self.prompt_tags,
            "has_existing_xmp": self.has_existing_xmp,
            "existing_xmp_tags": self.existing_xmp_tags,
        }

def clean_tag(tag: str) -> str:
    """Cleans a single prompt tag (removes weights, bracket syntax, extra spaces)."""
    tag = re.sub(r'^\(+|\)+$', '', tag)
    tag = re.sub(r'^\[+|\]+$', '', tag)
    tag = re.sub(r':\d+(\.\d+)?$', '', tag)
    if tag.startswith('<') and tag.endswith('>'):
        return ""
    tag = tag.strip()
    return tag

def is_pure_numeric(tag: str) -> bool:
    """Checks if a string is purely numeric (integer or float) e.g., '84729183749', '1024', '1.5'."""
    cleaned = tag.strip()
    if not cleaned:
        return False
    return bool(re.match(r'^\d+(\.\d+)?$', cleaned))

DEFAULT_STOP_WORDS = {
    "with", "from", "about", "under", "over", "this", "that", "they", "them", "their", 
    "were", "have", "been", "your", "yours", "each", "both", "some", "other", "than", 
    "then", "into", "onto", "down", "through", "what", "when", "where", "which", "while", 
    "whose", "here", "there", "these", "those", "will", "would", "shall", "should", 
    "could", "must", "very", "much", "more", "most", "many", "also", "only", "just", 
    "same", "such"
}

CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config")
STOPWORDS_FILE = os.path.join(CONFIG_DIR, "stopwords.txt")

def get_stopwords_file_path() -> str:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    if not os.path.exists(STOPWORDS_FILE):
        # Initialize with DEFAULT_STOP_WORDS
        try:
            sorted_words = sorted(list(DEFAULT_STOP_WORDS))
            with open(STOPWORDS_FILE, "w", encoding="utf-8") as f:
                for w in sorted_words:
                    f.write(f"{w}\n")
        except Exception as e:
            print(f"Error initializing stopwords.txt: {e}")
    return STOPWORDS_FILE

def load_custom_stop_words() -> Set[str]:
    filepath = get_stopwords_file_path()
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                words = {line.strip().lower() for line in f if line.strip()}
                if words:
                    return words
        except Exception as e:
            print(f"Error loading stopwords.txt: {e}")
    return DEFAULT_STOP_WORDS

DEFAULT_SHORT_WORDS = {
    "cat", "dog", "boy", "man", "car", "red", "hat", "gun", "sea", "sky", "sun", "bag", "wet", "old", "sad", "cup", "fox", "cow", "pig", "hen", "owl", "rat", "bat", "bee", "fly", "toy", "bed", "fan", "mug", "pot", "bar", "art", "ink", "oil", "gas", "ice", "mud", "fog", "fur", "lip", "leg", "eye", "ear", "arm", "toe", "rib", "jaw", "run", "cry", "hug", "fig", "oak", "ivy", "gpu", "cpu", "raw", "fat"
}
SHORT_WORDS_FILE = os.path.join(CONFIG_DIR, "short_words.txt")

def get_short_words_file_path() -> str:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    if not os.path.exists(SHORT_WORDS_FILE):
        try:
            sorted_words = sorted(list(DEFAULT_SHORT_WORDS))
            with open(SHORT_WORDS_FILE, "w", encoding="utf-8") as f:
                for w in sorted_words:
                    f.write(f"{w}\n")
        except Exception as e:
            print(f"Error initializing short_words.txt: {e}")
    return SHORT_WORDS_FILE

def load_custom_short_words() -> Set[str]:
    filepath = get_short_words_file_path()
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                words = {line.strip().lower() for line in f if line.strip()}
                if words:
                    return words
        except Exception as e:
            print(f"Error loading short_words.txt: {e}")
    return DEFAULT_SHORT_WORDS

DEFAULT_ADJECTIVES = {
    "dirty", "clean", "large", "small", "naughty", "skimpy", "torn", "colorfull", "colorful", 
    "high", "low", "dark", "light", "muddy", "moist", "wet", "dry", "long", "short", "big", 
    "huge", "beautiful", "cute", "pretty", "gorgeous", "sexy", "hot", "young", "old", "new", 
    "thick", "thin", "heavy", "lightweight", "soft", "hard", "rough", "smooth", "shiny", 
    "matte", "bright", "pale", "deep", "shallow", "wide", "narrow", "tall", "short", 
    "blue", "red", "green", "yellow", "orange", "purple", "pink", "black", "white", 
    "grey", "gray", "brown", "blonde", "golden", "silver", "unkempt", "curvy", "decrepit"
}

ADJECTIVES_FILE = os.path.join(CONFIG_DIR, "adjectives.txt")

def get_adjectives_file_path() -> str:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    if not os.path.exists(ADJECTIVES_FILE):
        try:
            sorted_words = sorted(list(DEFAULT_ADJECTIVES))
            with open(ADJECTIVES_FILE, "w", encoding="utf-8") as f:
                for w in sorted_words:
                    f.write(f"{w}\n")
        except Exception as e:
            print(f"Error initializing adjectives.txt: {e}")
    return ADJECTIVES_FILE

def load_custom_adjectives() -> Set[str]:
    filepath = get_adjectives_file_path()
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                words = {line.strip().lower() for line in f if line.strip()}
                if words:
                    return words
        except Exception as e:
            print(f"Error loading adjectives.txt: {e}")
    return DEFAULT_ADJECTIVES

WHITELIST_FILE = os.path.join(CONFIG_DIR, "whitelist.txt")

def get_whitelist_file_path() -> str:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    if not os.path.exists(WHITELIST_FILE):
        try:
            with open(WHITELIST_FILE, "w", encoding="utf-8") as f:
                f.write("# ComfyUI PNG Image Tagger - Whitelist File\n")
                f.write("# Add one tag or pattern per line. Lines starting with '#' are ignored.\n")
                f.write("# Example:\n")
                f.write("# 1girl\n")
                f.write("# realistic\n")
        except Exception as e:
            print(f"Error initializing whitelist.txt: {e}")
    return WHITELIST_FILE

def load_custom_whitelist() -> Set[str]:
    filepath = get_whitelist_file_path()
    words = set()
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    line_strip = line.strip()
                    if line_strip and not line_strip.startswith("#"):
                        words.add(line_strip.lower())
        except Exception as e:
            print(f"Error loading whitelist.txt: {e}")
    return words

BLACKLIST_FILE = os.path.join(CONFIG_DIR, "blacklist.txt")

def get_blacklist_file_path() -> str:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    if not os.path.exists(BLACKLIST_FILE):
        try:
            with open(BLACKLIST_FILE, "w", encoding="utf-8") as f:
                f.write("# ComfyUI PNG Image Tagger - Blacklist File\n")
                f.write("# Add one tag or pattern to ignore per line. Lines starting with '#' are ignored.\n")
                f.write("# Example:\n")
                f.write("# bad quality\n")
                f.write("# watermark\n")
        except Exception as e:
            print(f"Error initializing blacklist.txt: {e}")
    return BLACKLIST_FILE

def load_custom_blacklist() -> Set[str]:
    filepath = get_blacklist_file_path()
    words = set()
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    line_strip = line.strip()
                    if line_strip and not line_strip.startswith("#"):
                        words.add(line_strip.lower())
        except Exception as e:
            print(f"Error loading blacklist.txt: {e}")
    return words

def extract_prompt_tags(
    text: str,
    blacklist: Optional[Set[str]] = None,
    whitelist: Optional[Set[str]] = None,
    ignore_numeric: bool = True,
    max_tag_length: int = 50,
    word_based: bool = False,
    stop_words: Optional[Set[str]] = None,
    adjectives: Optional[Set[str]] = None,
    short_words: Optional[Set[str]] = None,
    lowercase_prompt_tags: bool = False
) -> List[str]:
    """
    Splits a prompt text into cleaned tags.
    If whitelist is provided and non-empty, only tags matching a whitelist entry are included.
    If blacklist is provided, matching tags are skipped.
    If ignore_numeric is True, pure numeric tags (e.g. seeds) are skipped.
    If max_tag_length > 0, tags exceeding max_tag_length characters are skipped.
    If word_based is True, splits by whitespace/punctuation, filters stop words and requires length > 3.
    """
    if not text or not isinstance(text, str):
        return []
    
    clean_black = {b.strip().lower() for b in blacklist if b.strip()} if blacklist else set()
    clean_white = {w.strip().lower() for w in whitelist if w.strip()} if whitelist else set()
    
    current_stop_words = stop_words if stop_words is not None else DEFAULT_STOP_WORDS
    current_adjectives = adjectives if adjectives is not None else DEFAULT_ADJECTIVES
    current_short_words = short_words if short_words is not None else DEFAULT_SHORT_WORDS
    
    if word_based:
        # Split by non-alphanumeric characters (except dashes and underscores)
        raw_parts = re.split(r'[^a-zA-Z0-9_-]+', text)
    else:
        raw_parts = re.split(r'[,\n]', text)
        
    def is_breaker(word_clean: str) -> bool:
        w_lower = word_clean.lower()
        if w_lower in current_stop_words:
            return True
        if len(word_clean) <= 3 and w_lower not in current_short_words:
            return True
        if ignore_numeric and is_pure_numeric(word_clean):
            return True
        return False

    tags = []
    seen = set()
    
    def try_append_tag(tag_val: str):
        cleaned = clean_tag(tag_val.strip())
        if cleaned:
            if max_tag_length > 0 and len(cleaned) > max_tag_length:
                return
            clean_lower = cleaned.lower()
            if clean_lower in clean_black:
                return
            if clean_white:
                matches_white = False
                for w in clean_white:
                    if w == clean_lower or w in clean_lower or clean_lower in w:
                        matches_white = True
                        break
                if not matches_white:
                    return
            if clean_lower not in seen:
                seen.add(clean_lower)
                # Apply lowercase normalization if enabled (only affects prompt tags)
                tags.append(clean_lower if lowercase_prompt_tags else cleaned)

    if word_based:
        adjective_accumulator = []
        for part in raw_parts:
            part_clean = part.strip()
            if not part_clean:
                continue
            
            if is_breaker(part_clean):
                for adj in adjective_accumulator:
                    try_append_tag(adj)
                adjective_accumulator.clear()
            elif part_clean.lower() in current_adjectives:
                adjective_accumulator.append(part_clean)
            else:
                if adjective_accumulator:
                    combined = f"{' '.join(adjective_accumulator)} {part_clean}"
                    try_append_tag(combined)
                    adjective_accumulator.clear()
                else:
                    try_append_tag(part_clean)
                    
        for adj in adjective_accumulator:
            try_append_tag(adj)
    else:
        for part in raw_parts:
            cleaned = clean_tag(part.strip())
            if cleaned and len(cleaned) >= 2:
                try_append_tag(cleaned)
            
    return tags

def clean_model_name(name: str) -> str:
    """Strips file extensions and path directories from model names."""
    if not name:
        return ""
    base = os.path.basename(str(name))
    for ext in ['.safetensors', '.ckpt', '.pt', '.bin', '.pth', '.onnx']:
        if base.lower().endswith(ext):
            base = base[:-len(ext)]
            break
    return base

DEFAULT_PROMPT_KEYS = [
    "text", "text_0", "text_1", "text_positive", "positive", "prompt",
    "text_g", "text_l", "prompt_text", "wildcard", "wildcard_text", "string"
]



def extract_widgets_strings(widgets_values: Any) -> List[str]:
    """Recursively extracts all strings from widget value structures."""
    strings = []
    if isinstance(widgets_values, list):
        for item in widgets_values:
            strings.extend(extract_widgets_strings(item))
    elif isinstance(widgets_values, str):
        if widgets_values.strip():
            strings.append(widgets_values.strip())
    return strings

def _extract_exif_date(img) -> Optional[str]:
    try:
        exif = img.getexif()
        if not exif:
            return None
        # Check standard EXIF tags (306 = DateTime, 36867 = DateTimeOriginal, 36868 = DateTimeDigitized)
        for tag in [36867, 36868, 306]:
            if tag in exif and exif[tag]:
                val = str(exif[tag]).strip()
                if val:
                    return val
        # Check Exif sub-IFD (0x8769)
        sub_ifd = exif.get_ifd(0x8769)
        if sub_ifd:
            for tag in [36867, 36868, 306]:
                if tag in sub_ifd and sub_ifd[tag]:
                    val = str(sub_ifd[tag]).strip()
                    if val:
                        return val
    except Exception:
        pass
    return None

def _normalize_exif_date(date_str: str) -> Optional[str]:
    date_str = date_str.strip()
    # YYYY:MM:DD HH:MM:SS
    m = re.match(r"^(\d{4}):(\d{2}):(\d{2})\s+(\d{2}):(\d{2}):(\d{2})", date_str)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}T{m.group(4)}:{m.group(5)}:{m.group(6)}"
    m2 = re.match(r"^(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2}):(\d{2})", date_str)
    if m2:
        return f"{m2.group(1)}-{m2.group(2)}-{m2.group(3)}T{m2.group(4)}:{m2.group(5)}:{m2.group(6)}"
    if re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", date_str):
        return date_str[:19]
    return None

def parse_comfy_png(
    image_path: str,
    min_lora_strength: float = 0.01,
    ignore_inactive_nodes: bool = True,
    blacklist_tags: Optional[Set[str]] = None,
    whitelist_tags: Optional[Set[str]] = None,
    custom_prompt_keys: Optional[List[str]] = None,
    ignore_numeric_tags: bool = True,
    max_tag_length: int = 50,
    word_based_tagging: bool = False,
    stop_words: Optional[Set[str]] = None,
    adjectives: Optional[Set[str]] = None,
    short_words: Optional[Set[str]] = None,
    lowercase_prompt_tags: bool = False
) -> Optional[ComfyMetadata]:
    """
    Parses a PNG file for image dimensions and ComfyUI metadata.
    """
    if not os.path.exists(image_path):
        return None

    meta = ComfyMetadata()

    try:
        with Image.open(image_path) as img:
            meta.width, meta.height = img.size
            meta.megapixels = round((meta.width * meta.height) / 1000000.0, 2)
            info = img.info
            
            # 1. Try to read Date from embedded EXIF
            exif_date_raw = _extract_exif_date(img)
            if exif_date_raw:
                meta.creation_date = _normalize_exif_date(exif_date_raw)
            
            if "XML:com.adobe.xmp" in info:
                meta.raw_xmp_str = info["XML:com.adobe.xmp"]
                meta.existing_xmp_tags = extract_existing_tags_from_xmp(meta.raw_xmp_str)
                meta.has_existing_xmp = bool(meta.existing_xmp_tags)
                meta.existing_xmp_properties = extract_all_xmp_properties(meta.raw_xmp_str)
                
                # 2. Try to get Date from embedded XMP properties if not set by EXIF
                if not meta.creation_date and "xmp:CreateDate" in meta.existing_xmp_properties:
                    meta.creation_date = meta.existing_xmp_properties["xmp:CreateDate"].strip()
    except Exception:
        return None

    # Load from sidecar if needed (or if sidecar properties should be merged)
    if os.path.exists(image_path + ".xmp"):
        try:
            with open(image_path + ".xmp", "r", encoding="utf-8", errors="ignore") as f:
                sidecar_xmp = f.read()
                if sidecar_xmp:
                    if not meta.raw_xmp_str:
                        meta.raw_xmp_str = sidecar_xmp
                    ex_tags = extract_existing_tags_from_xmp(sidecar_xmp)
                    if ex_tags:
                        meta.existing_xmp_tags = list(dict.fromkeys(meta.existing_xmp_tags + ex_tags))
                        meta.has_existing_xmp = True
                    props = extract_all_xmp_properties(sidecar_xmp)
                    if props:
                        meta.existing_xmp_properties.update(props)
        except Exception:
            pass

    # 3. Fallback: check if sidecar XMP had a CreateDate
    if not meta.creation_date and "xmp:CreateDate" in meta.existing_xmp_properties:
        meta.creation_date = meta.existing_xmp_properties["xmp:CreateDate"].strip()

    # 4. Fallback: use filesystem ctime if no metadata date exists
    if not meta.creation_date:
        try:
            import datetime
            creation_timestamp = os.path.getctime(image_path)
            creation_dt = datetime.datetime.fromtimestamp(creation_timestamp)
            meta.creation_date = creation_dt.strftime("%Y-%m-%dT%H:%M:%S")
        except Exception:
            pass

    prompt_data = None
    workflow_data = None

    if "prompt" in info:
        try:
            prompt_data = json.loads(info["prompt"])
        except Exception:
            pass

    if "workflow" in info:
        try:
            workflow_data = json.loads(info["workflow"])
        except Exception:
            pass

    if not prompt_data and not workflow_data:
        return None

    inactive_node_ids: Set[str] = set()
    negative_node_ids: Set[str] = set()
    matched_prompt_node_ids: Set[str] = set()
    explicit_prompts_found = []

    prompt_keys = custom_prompt_keys if custom_prompt_keys else DEFAULT_PROMPT_KEYS

    if workflow_data and isinstance(workflow_data, dict):
        nodes = workflow_data.get("nodes", [])
        if isinstance(nodes, list):
            for node in nodes:
                if isinstance(node, dict):
                    node_id = str(node.get("id", ""))
                    
                    # Track muted/bypassed nodes
                    mode = node.get("mode", 0)
                    if mode in (2, 4):
                        inactive_node_ids.add(node_id)
                        continue

                    title = str(node.get("title", "")).lower()
                    node_type = str(node.get("type", "")).lower()

                    # 1. Identify negative prompt nodes (ignore their outputs for positive prompts)
                    if any(bad in title for bad in ["negative", "negativ", "neg", "nans"]):
                        negative_node_ids.add(node_id)
                    elif any(bad in node_type for bad in ["negative", "negativ", "neg"]):
                        negative_node_ids.add(node_id)

                    # 2. Check if this node matches custom prompt key definitions
                    is_match = False
                    node_str = json.dumps(node)
                    for pk in prompt_keys:
                        pk_clean = pk.strip()
                        if not pk_clean:
                            continue
                        if pk_clean.isdigit():
                            if node_id == pk_clean:
                                is_match = True
                                break
                        elif pk_clean.lower() in title or pk_clean.lower() in node_type or pk_clean in node_str:
                            is_match = True
                            break

                    if is_match and node_id not in negative_node_ids and node_id not in inactive_node_ids:
                        matched_prompt_node_ids.add(node_id)
                        widgets_values = node.get("widgets_values", [])
                        extracted_strs = extract_widgets_strings(widgets_values)
                        for s in extracted_strs:
                            if not any(bad in s.lower()[:30] for bad in ["blurry", "low quality", "worst quality", "bad anatomy", "deformed"]):
                                explicit_prompts_found.append((node_id, s))

    meta.raw_prompt_json = prompt_data
    meta.raw_workflow_json = workflow_data

    if prompt_data and isinstance(prompt_data, dict):
        _parse_api_prompt(
            prompt_data, meta, inactive_node_ids, negative_node_ids,
            matched_prompt_node_ids, min_lora_strength, prompt_keys
        )
        
    if workflow_data and isinstance(workflow_data, dict) and "nodes" in workflow_data:
        _parse_ui_workflow(workflow_data, meta, inactive_node_ids, min_lora_strength)

    # Prioritize prompts extracted directly from workflow widgets_values (since API prompt can be out-of-sync)
    if explicit_prompts_found:
        for node_id, s in explicit_prompts_found:
            s_clean = s.strip()
            if s_clean:
                meta.positive_prompts.append(s_clean)
                meta.positive_prompts_sources[s_clean] = f"ID: {node_id}"

    meta.checkpoints = list(dict.fromkeys([c for c in meta.checkpoints if c]))
    meta.loras = list(dict.fromkeys([l for l in meta.loras if l]))
    meta.samplers = list(dict.fromkeys([s for s in meta.samplers if s]))
    meta.schedulers = list(dict.fromkeys([sc for sc in meta.schedulers if sc]))
    meta.positive_prompts = list(dict.fromkeys([p for p in meta.positive_prompts if p]))

    # Apply global blacklist filtering (substring match)
    if blacklist_tags:
        clean_black = {b.strip().lower() for b in blacklist_tags if b.strip()}
        if clean_black:
            meta.checkpoints = [c for c in meta.checkpoints if not any(bad in c.lower() for bad in clean_black)]
            meta.loras = [l for l in meta.loras if not any(bad in l.lower() for bad in clean_black)]
            meta.samplers = [s for s in meta.samplers if not any(bad in s.lower() for bad in clean_black)]
            meta.schedulers = [sc for sc in meta.schedulers if not any(bad in sc.lower() for bad in clean_black)]

    if word_based_tagging:
        if stop_words is None:
            stop_words = load_custom_stop_words()
        if adjectives is None:
            adjectives = load_custom_adjectives()
        if short_words is None:
            short_words = load_custom_short_words()

    all_tags = []
    seen_tags = set()
    for prompt_text in meta.positive_prompts:
        extracted = extract_prompt_tags(
            prompt_text,
            blacklist=blacklist_tags,
            whitelist=whitelist_tags,
            ignore_numeric=ignore_numeric_tags,
            max_tag_length=max_tag_length,
            word_based=word_based_tagging,
            stop_words=stop_words,
            adjectives=adjectives,
            short_words=short_words,
            lowercase_prompt_tags=lowercase_prompt_tags
        )
        for t in extracted:
            if t.lower() not in seen_tags:
                seen_tags.add(t.lower())
                all_tags.append(t)
    meta.prompt_tags = all_tags

    return meta

def _is_lora_active(inputs: Dict[str, Any], min_strength: float) -> bool:
    str_model = inputs.get("strength_model")
    str_clip = inputs.get("strength_clip")
    str_gen = inputs.get("strength")

    strengths = []
    for val in [str_model, str_clip, str_gen]:
        if isinstance(val, (int, float)):
            strengths.append(abs(float(val)))

    if strengths:
        return any(s >= min_strength for s in strengths)
    return True

def _parse_api_prompt(
    prompt_data: Dict[str, Any],
    meta: ComfyMetadata,
    inactive_node_ids: Set[str],
    negative_node_ids: Set[str],
    matched_prompt_node_ids: Set[str],
    min_lora_strength: float,
    prompt_keys: List[str]
):
    clean_keys = [k.strip().lower() for k in prompt_keys if k.strip()]

    for node_id, node in prompt_data.items():
        node_id_str = str(node_id)
        if node_id_str in inactive_node_ids or node_id_str in negative_node_ids:
            continue

        if not isinstance(node, dict):
            continue
        class_type = str(node.get("class_type", ""))
        inputs = node.get("inputs", {})
        if not isinstance(inputs, dict):
            continue

        for key in ["ckpt_name", "unet_name", "model_name", "checkpoint"]:
            if key in inputs and isinstance(inputs[key], str):
                cleaned = clean_model_name(inputs[key])
                if cleaned:
                    meta.checkpoints.append(cleaned)

        if "Power Lora Loader" in class_type or class_type == "Power Lora Loader (rgthree)":
            for key, val in inputs.items():
                if isinstance(val, dict) and "lora" in val:
                    is_on = val.get("on", True)
                    lora_name = val.get("lora")
                    strength_m = val.get("strength", 1.0)
                    strength_c = val.get("strengthTwo", strength_m)
                    if strength_c is None:
                        strength_c = strength_m
                    if is_on and isinstance(lora_name, str) and lora_name.strip():
                        m_ok = isinstance(strength_m, (int, float)) and abs(float(strength_m)) >= min_lora_strength
                        c_ok = isinstance(strength_c, (int, float)) and abs(float(strength_c)) >= min_lora_strength
                        if m_ok or c_ok:
                            cleaned = clean_model_name(lora_name)
                            if cleaned and cleaned.lower() != "none":
                                meta.loras.append(cleaned)
        elif "Lora" in class_type or any(k.startswith("lora") for k in inputs.keys()):
            if _is_lora_active(inputs, min_lora_strength):
                for key in ["lora_name", "lora_name_1", "lora_name_2"]:
                    if key in inputs and isinstance(inputs[key], str):
                        cleaned = clean_model_name(inputs[key])
                        if cleaned and cleaned.lower() != "none":
                            meta.loras.append(cleaned)

        if "KSampler" in class_type or "Sampler" in class_type:
            if "sampler_name" in inputs and isinstance(inputs["sampler_name"], str):
                meta.samplers.append(inputs["sampler_name"])
            if "scheduler" in inputs and isinstance(inputs["scheduler"], str):
                meta.schedulers.append(inputs["scheduler"])
            if "steps" in inputs and isinstance(inputs["steps"], (int, float)):
                meta.steps = int(inputs["steps"])
            if "cfg" in inputs and isinstance(inputs["cfg"], (int, float)):
                meta.cfg = float(inputs["cfg"])

        for key, val in inputs.items():
            if isinstance(val, str) and val.strip():
                key_lower = key.strip().lower()
                
                # If we have explicitly matched prompt nodes from workflow, do NOT extract positive prompts
                # from the API prompt chunk (since it can be out of sync). We rely on workflow widgets_values instead.
                if matched_prompt_node_ids:
                    continue

                # Fallback to standard matching
                is_custom_match = key_lower in clean_keys
                is_clip_positive = "CLIPTextEncode" in class_type and (key_lower == "text" or key_lower == "text_positive")
                
                if is_custom_match or is_clip_positive:
                    if not any(bad in val.lower()[:30] for bad in ["blurry", "low quality", "worst quality", "bad anatomy", "deformed"]):
                        val_clean = val.strip()
                        meta.positive_prompts.append(val_clean)
                        meta.positive_prompts_sources[val_clean] = f"ID: {node_id_str}"

def _parse_ui_workflow(
    workflow_data: Dict[str, Any],
    meta: ComfyMetadata,
    inactive_node_ids: Set[str],
    min_lora_strength: float
):
    nodes = workflow_data.get("nodes", [])
    if not isinstance(nodes, list):
        return

    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_id = str(node.get("id", ""))
        if node_id in inactive_node_ids:
            continue

        mode = node.get("mode", 0)
        if mode in (2, 4):
            continue

        type_str = str(node.get("type", ""))
        widgets_values = node.get("widgets_values", [])

        if "CheckpointLoader" in type_str and isinstance(widgets_values, list) and widgets_values:
            ckpt = clean_model_name(widgets_values[0])
            if ckpt and ckpt not in meta.checkpoints:
                meta.checkpoints.append(ckpt)

        if "LoraLoader" in type_str and isinstance(widgets_values, list) and len(widgets_values) >= 1:
            lora_name = widgets_values[0]
            strength_active = True
            if len(widgets_values) >= 2 and isinstance(widgets_values[1], (int, float)):
                str_m = float(widgets_values[1])
                str_c = float(widgets_values[2]) if len(widgets_values) >= 3 and isinstance(widgets_values[2], (int, float)) else str_m
                if abs(str_m) < min_lora_strength and abs(str_c) < min_lora_strength:
                    strength_active = False

            if strength_active:
                lora = clean_model_name(lora_name)
                if lora and lora.lower() != "none" and lora not in meta.loras:
                    meta.loras.append(lora)

        if "Power Lora Loader" in type_str or type_str == "Power Lora Loader (rgthree)":
            if isinstance(widgets_values, list):
                for val in widgets_values:
                    if isinstance(val, dict) and "lora" in val:
                        is_on = val.get("on", True)
                        lora_name = val.get("lora")
                        strength_m = val.get("strength", 1.0)
                        strength_c = val.get("strengthTwo", strength_m)
                        if strength_c is None:
                            strength_c = strength_m
                        if is_on and isinstance(lora_name, str) and lora_name.strip():
                            m_ok = isinstance(strength_m, (int, float)) and abs(float(strength_m)) >= min_lora_strength
                            c_ok = isinstance(strength_c, (int, float)) and abs(float(strength_c)) >= min_lora_strength
                            if m_ok or c_ok:
                                 lora = clean_model_name(lora_name)
                                 if lora and lora.lower() != "none" and lora not in meta.loras:
                                     meta.loras.append(lora)

def analyze_workflow_prompts(image_path: str) -> Optional[List[dict]]:
    """
    Analyzes ComfyUI metadata of a PNG image and extracts text fields
    that look like positive prompts, returning a list of candidate dictionaries.
    """
    if not os.path.exists(image_path):
        return None

    prompt_data = None
    workflow_data = None

    try:
        with Image.open(image_path) as img:
            info = img.info
            if "prompt" in info:
                prompt_data = json.loads(info["prompt"])
            if "workflow" in info:
                workflow_data = json.loads(info["workflow"])
    except Exception:
        return None

    if not prompt_data and not workflow_data:
        return []

    candidates = []
    seen_texts = set()

    # Helper to check if text is a prompt candidate
    def is_prompt_candidate(text: str) -> bool:
        if not isinstance(text, str):
            return False
        text_strip = text.strip()
        if len(text_strip) < 10:
            return False
        # Avoid file paths/names
        if any(ext in text_strip.lower() for ext in [".safetensors", ".ckpt", ".png", ".jpg", ".jpeg", ".pt", ".yaml"]):
            return False
        # Avoid negative prompts
        bad_words = ["blurry", "low quality", "worst quality", "bad anatomy", "deformed", "bad hands", "disfigured", "mutation", "negative", "negativ"]
        text_lower = text_strip.lower()
        if any(bad in text_lower for bad in bad_words):
            # Check if it has significantly many negative prompt keywords in first 120 chars
            bad_count = sum(1 for bad in bad_words if bad in text_lower[:120])
            if bad_count >= 2 or "negative" in text_lower[:50]:
                return False
        return True

    # Helper to clean text preview
    def clean_preview(text: str) -> str:
        text_strip = text.strip().replace("\n", " ").replace("\r", "")
        if len(text_strip) > 120:
            return text_strip[:117] + "..."
        return text_strip

    # 1. Parse prompt_data (API format)
    # prompt_data is a dict of: node_id -> { "class_type": ..., "inputs": { ... } }
    if prompt_data and isinstance(prompt_data, dict):
        for node_id, node_def in prompt_data.items():
            if not isinstance(node_def, dict):
                continue
            class_type = node_def.get("class_type", "UnknownNode")
            inputs = node_def.get("inputs", {})
            if not isinstance(inputs, dict):
                continue
            for input_key, input_val in inputs.items():
                if isinstance(input_val, str) and is_prompt_candidate(input_val):
                    text_val = input_val.strip()
                    if text_val not in seen_texts:
                        seen_texts.add(text_val)
                        candidates.append({
                            "source": "API Prompt Graph",
                            "node_id": str(node_id),
                            "node_title": class_type,
                            "node_type": class_type,
                            "widget_or_input": input_key,
                            "value": text_val,
                            "preview": clean_preview(text_val)
                        })

    # 2. Parse workflow_data (UI format)
    # workflow_data contains a list of nodes under "nodes": [ { "id": int, "type": ..., "title": ..., "widgets_values": [...] } ]
    if workflow_data and isinstance(workflow_data, dict):
        nodes = workflow_data.get("nodes", [])
        if isinstance(nodes, list):
            for node in nodes:
                if not isinstance(node, dict):
                    continue
                node_id = str(node.get("id", ""))
                node_type = str(node.get("type", "UnknownNode"))
                node_title = str(node.get("title", "")) or node_type
                widgets_values = node.get("widgets_values", [])
                if isinstance(widgets_values, list):
                    for idx, val in enumerate(widgets_values):
                        if isinstance(val, str) and is_prompt_candidate(val):
                            text_val = val.strip()
                            if text_val not in seen_texts:
                                seen_texts.add(text_val)
                                candidates.append({
                                    "source": "UI Workflow Node",
                                    "node_id": node_id,
                                    "node_title": node_title,
                                    "node_type": node_type,
                                    "widget_or_input": f"widget_{idx}",
                                    "value": text_val,
                                    "preview": clean_preview(text_val)
                                })
                            else:
                                # Update existing candidate source if found in prompt but also in workflow widgets
                                for cand in candidates:
                                    if cand["value"] == text_val:
                                        cand["node_title"] = node_title # Prefer workflow title if available
                                        break

    return candidates
