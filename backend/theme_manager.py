import os
import json

DEFAULT_THEMES = {
    "Standard Dark": {
        "color_primary_btn": "#2b8a3e",
        "color_primary_hover": "#237032",
        "color_secondary_btn": "#1c7ed6",
        "color_secondary_hover": "#1864ab",
        "color_danger_btn": "#c92a2a",
        "color_danger_hover": "#a61e1e",
        "color_warning_btn": "#e67e22",
        "color_warning_hover": "#d35400",
        "color_neutral_btn": "#495057",
        "color_neutral_hover": "#343a40",
        "color_inner_frame_bg": "#1a1b1e",
        "color_info_link": "#74c0fc",
        "color_badge_untagged": "#2b8a3e",
        "color_tag_new": "#51cf66",
        "color_tag_existing": "#868e96",
        "color_tag_deleted": "#fa5252",
        "color_tag_warning": "#ff6b6b",
        "color_tag_low_warning": "#ffd43b",
        "color_tag_xmp_prefix": "#0bc9e3",
        "color_listbox_details": "#868e96",
        "color_textbox_prompt_body": "#ced4da",
        "color_label_text": "#ffffff",
        "color_listbox_selected_bg": "#1c7ed6",
        "color_progress_bar": "#2b8a3e",
        "color_info_date": "#ffd43b",
        "color_tag_extra_meta": "#b197fc"
    },
    "Nordic Frost": {
        "color_primary_btn": "#4c566a",
        "color_primary_hover": "#3b4252",
        "color_secondary_btn": "#88c0d0",
        "color_secondary_hover": "#81a1c1",
        "color_danger_btn": "#bf616a",
        "color_danger_hover": "#a3be8c",
        "color_warning_btn": "#ebcb8b",
        "color_warning_hover": "#d08770",
        "color_neutral_btn": "#4c566a",
        "color_neutral_hover": "#434c5e",
        "color_inner_frame_bg": "#2e3440",
        "color_info_link": "#8fbcbb",
        "color_badge_untagged": "#a3be8c",
        "color_tag_new": "#a3be8c",
        "color_tag_existing": "#d8dee9",
        "color_tag_deleted": "#bf616a",
        "color_tag_warning": "#bf616a",
        "color_tag_low_warning": "#ebcb8b",
        "color_tag_xmp_prefix": "#88c0d0",
        "color_listbox_details": "#d8dee9",
        "color_textbox_prompt_body": "#e5e9f0",
        "color_label_text": "#eceff4",
        "color_listbox_selected_bg": "#88c0d0",
        "color_progress_bar": "#88c0d0",
        "color_info_date": "#ebcb8b",
        "color_tag_extra_meta": "#b48ead"
    },
    "Sunset Orange": {
        "color_primary_btn": "#d35400",
        "color_primary_hover": "#ba4a00",
        "color_secondary_btn": "#f39c12",
        "color_secondary_hover": "#d68910",
        "color_danger_btn": "#c0392b",
        "color_danger_hover": "#962d22",
        "color_warning_btn": "#e67e22",
        "color_warning_hover": "#ca6f1e",
        "color_neutral_btn": "#34495e",
        "color_neutral_hover": "#2c3e50",
        "color_inner_frame_bg": "#2c3e50",
        "color_info_link": "#f1c40f",
        "color_badge_untagged": "#27ae60",
        "color_tag_new": "#2ecc71",
        "color_tag_existing": "#95a5a6",
        "color_tag_deleted": "#e74c3c",
        "color_tag_warning": "#e74c3c",
        "color_tag_low_warning": "#f1c40f",
        "color_tag_xmp_prefix": "#3498db",
        "color_listbox_details": "#95a5a6",
        "color_textbox_prompt_body": "#ecf0f1",
        "color_label_text": "#ecf0f1",
        "color_listbox_selected_bg": "#f39c12",
        "color_progress_bar": "#d35400",
        "color_info_date": "#f1c40f",
        "color_tag_extra_meta": "#9b59b6"
    },
    "Cyberpunk Neon": {
        "color_primary_btn": "#ff007f",
        "color_primary_hover": "#d9006b",
        "color_secondary_btn": "#00ffff",
        "color_secondary_hover": "#00cccc",
        "color_danger_btn": "#ff0033",
        "color_danger_hover": "#cc0029",
        "color_warning_btn": "#ffaa00",
        "color_warning_hover": "#cc8800",
        "color_neutral_btn": "#2e2e42",
        "color_neutral_hover": "#1f1f2e",
        "color_inner_frame_bg": "#0d0e15",
        "color_info_link": "#00ff66",
        "color_badge_untagged": "#00ff66",
        "color_tag_new": "#00ff66",
        "color_tag_existing": "#7b7e8e",
        "color_tag_deleted": "#ff007f",
        "color_tag_warning": "#ff0033",
        "color_tag_low_warning": "#ffaa00",
        "color_tag_xmp_prefix": "#00ffff",
        "color_listbox_details": "#7b7e8e",
        "color_textbox_prompt_body": "#f0f3f8",
        "color_label_text": "#f0f3f8",
        "color_listbox_selected_bg": "#00ffff",
        "color_progress_bar": "#ff007f",
        "color_info_date": "#ffaa00",
        "color_tag_extra_meta": "#cc00ff"
    }
}

THEMES_FILE = os.path.join("config", "themes.json")

def load_custom_themes():
    if not os.path.exists(THEMES_FILE):
        return {}
    try:
        with open(THEMES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_custom_themes(custom_themes):
    os.makedirs(os.path.dirname(THEMES_FILE), exist_ok=True)
    try:
        with open(THEMES_FILE, "w", encoding="utf-8") as f:
            json.dump(custom_themes, f, indent=4)
        return True
    except Exception:
        return False

class ThemeManager:
    _custom_themes = None

    @classmethod
    def get_all_themes(cls):
        if cls._custom_themes is None:
            cls._custom_themes = load_custom_themes()
        
        all_themes = {}
        all_themes.update(DEFAULT_THEMES)
        all_themes.update(cls._custom_themes)
        return all_themes

    @classmethod
    def get_theme_names(cls):
        return list(cls.get_all_themes().keys())

    @classmethod
    def get_theme_colors(cls, theme_name):
        themes = cls.get_all_themes()
        res = dict(DEFAULT_THEMES["Standard Dark"])
        res.update(themes.get(theme_name, {}))
        return res

    @classmethod
    def save_theme(cls, theme_name, colors):
        if theme_name in DEFAULT_THEMES:
            # Cannot overwrite default themes
            return False
        
        if cls._custom_themes is None:
            cls._custom_themes = load_custom_themes()
            
        cls._custom_themes[theme_name] = colors
        return save_custom_themes(cls._custom_themes)

    @classmethod
    def delete_theme(cls, theme_name):
        if theme_name in DEFAULT_THEMES:
            return False
            
        if cls._custom_themes is None:
            cls._custom_themes = load_custom_themes()
            
        if theme_name in cls._custom_themes:
            del cls._custom_themes[theme_name]
            return save_custom_themes(cls._custom_themes)
        return False
