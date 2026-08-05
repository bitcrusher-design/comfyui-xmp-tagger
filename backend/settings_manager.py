import os
import json
from typing import Dict, Any, List

CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config")
SETTINGS_FILE = os.path.join(CONFIG_DIR, "settings.json")
PRESETS_DIR = os.path.join(CONFIG_DIR, "presets")

DEFAULT_SETTINGS = {
    "include_models": True,
    "include_loras": True,
    "include_samplers": True,
    "include_prompts": True,
    "write_flat_dc": True,
    "ignore_inactive_nodes": True,
    "ignore_numeric_tags": True,
    "max_tag_length": 50,
    "recursive_scan": True,
    "splitter_ratio": 0.45,
    "include_resolution": True,
    "prefix_resolution": "Resolution",
    "res_tier1_mp": 1.0,
    "res_tier1_name": "Preview",
    "res_tier2_mp": 2.5,
    "res_tier2_name": "Standard",
    "res_tier3_name": "Upscale",
    "min_lora_strength": 0.01,
    "use_whitelist": False,
    "whitelist_tags": "cyberpunk, portrait, landscape, outdoor, 1girl, realistic",
    "blacklist_tags": "masterpiece, best quality, ultra detailed, highly detailed",
    "prompt_keys": "text, text_0, text_1, text_positive, positive, prompt, text_g, text_l, wildcard, wildcard_text",
    "prefix_model": "Model",
    "prefix_lora": "Lora",
    "prefix_prompt": "Prompt",
    "storage_mode": "embed",
    "active_preset": "Standard (Default)",
    "overwrite_existing_tags": False,
    "write_created_date": False,
    "write_camera_model": False,
    "write_description": False,
    "custom_creator": "",
    "custom_copyright": "",
    "custom_camera_make": "",
    "custom_software": "",
    "custom_comment": "",
    "window_width": 1200,
    "window_height": 880,
    "window_x": 100,
    "window_y": 100,
    "window_maximized": False,
    "language": "de",
    "active_theme": "Standard Dark",
    "ui_preview_font_size": "12",
    "lowercase_prompt_tags": False,
    "ui_preview_extra_meta": True,
    "ui_thumb_size": "200",
    "ui_details_order": ["checkpoint", "lora", "resolution", "date"],
    "ui_details_visible": ["checkpoint", "lora"],
    "ui_show_listbox_warnings": True,
    "ui_show_tagging_confirm": True
}

def ensure_config_dirs():
    os.makedirs(CONFIG_DIR, exist_ok=True)
    os.makedirs(PRESETS_DIR, exist_ok=True)

def load_settings() -> Dict[str, Any]:
    """Loads default settings merged with settings.json if present."""
    ensure_config_dirs()
    settings = dict(DEFAULT_SETTINGS)
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                if isinstance(saved, dict):
                    settings.update(saved)
        except Exception as e:
            print(f"Error loading settings.json: {e}")
    return settings

def save_settings(settings_data: Dict[str, Any]) -> bool:
    """Saves settings_data dictionary to settings.json."""
    ensure_config_dirs()
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings_data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving settings.json: {e}")
        return False

def list_presets() -> List[str]:
    """Returns list of available preset names."""
    ensure_config_dirs()
    presets = ["Standard (Default)"]
    if os.path.exists(PRESETS_DIR):
        for f in sorted(os.listdir(PRESETS_DIR)):
            if f.lower().endswith(".json"):
                name = os.path.splitext(f)[0]
                if name != "Standard (Default)":
                    presets.append(name)
    return presets

def save_preset(name: str, settings_data: Dict[str, Any]) -> bool:
    """Saves settings_data under a named preset in config/presets/<name>.json."""
    ensure_config_dirs()
    safe_name = "".join([c for c in name if c.isalnum() or c in (' ', '_', '-')]).strip()
    if not safe_name:
        return False
    
    preset_path = os.path.join(PRESETS_DIR, f"{safe_name}.json")
    try:
        with open(preset_path, "w", encoding="utf-8") as f:
            json.dump(settings_data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving preset {safe_name}: {e}")
        return False

def load_preset(name: str) -> Dict[str, Any]:
    """Loads settings dictionary from a preset name."""
    if name == "Standard (Default)":
        return dict(DEFAULT_SETTINGS)
    
    ensure_config_dirs()
    preset_path = os.path.join(PRESETS_DIR, f"{name}.json")
    if os.path.exists(preset_path):
        try:
            with open(preset_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    res = dict(DEFAULT_SETTINGS)
                    res.update(data)
                    return res
        except Exception as e:
            print(f"Error loading preset {name}: {e}")
            
    return dict(DEFAULT_SETTINGS)

def delete_preset(name: str) -> bool:
    """Deletes a named preset file."""
    if name == "Standard (Default)":
        return False
    ensure_config_dirs()
    preset_path = os.path.join(PRESETS_DIR, f"{name}.json")
    if os.path.exists(preset_path):
        try:
            os.remove(preset_path)
            return True
        except Exception as e:
            print(f"Error deleting preset {name}: {e}")
    return False
