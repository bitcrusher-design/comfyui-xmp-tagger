import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
import customtkinter as ctk
from PIL import Image

# Ensure project root is in sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.comfy_parser import parse_comfy_png, get_stopwords_file_path, load_custom_stop_words, get_adjectives_file_path, load_custom_adjectives, get_short_words_file_path, load_custom_short_words, extract_all_xmp_properties
from backend.xmp_builder import generate_xmp_payload, XMPConfig
from backend.png_writer import embed_xmp_in_png, write_xmp_sidecar, remove_xmp_tags_from_file
from backend.settings_manager import (
    load_settings, save_settings, list_presets,
    save_preset, load_preset, delete_preset
)
from backend.theme_manager import ThemeManager, DEFAULT_THEMES
from backend.localization import Text

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class ToolTip:
    """Creates a hover tooltip for a widget."""
    def __init__(self, widget, text=""):
        self.widget = widget
        self.text = text
        self.tip_window = None
        self.widget.bind("<Enter>", self.show_tip)
        self.widget.bind("<Leave>", self.hide_tip)

    def show_tip(self, event=None):
        text_val = self.text() if callable(self.text) else self.text
        if self.tip_window or not text_val:
            return
        x, y, _, _ = self.widget.bbox("insert") if hasattr(self.widget, "bbox") else (0, 0, 0, 0)
        x = x + self.widget.winfo_rootx() + 20
        y = y + self.widget.winfo_rooty() + 30

        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")

        label = tk.Label(
            tw,
            text=text_val,
            justify=tk.LEFT,
            background="#2b2b2b",
            foreground="#ffffff",
            relief=tk.SOLID,
            borderwidth=1,
            font=("Segoe UI", 9, "normal"),
            padx=8,
            pady=5
        )
        label.pack(ipadx=1)

    def hide_tip(self, event=None):
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None

    def update_text(self, new_text):
        self.text = new_text

class ExistingTagsDialog(ctk.CTkToplevel):
    """Modal popup dialog showing existing XMP and binary EXIF metadata embedded in an image."""
    def __init__(self, parent, filepath: str, meta):
        super().__init__(parent)
        filename = os.path.basename(filepath)
        self.title(Text.get("dialog_existing_metadata_title", filename=filename))
        self.geometry("640x550")
        self.minsize(500, 360)
        self.transient(parent)
        self.grab_set()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Header
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, padx=20, pady=(15, 5), sticky="ew")

        lbl_title = ctk.CTkLabel(
            header_frame,
            text=Text.get("dialog_existing_metadata_title", filename=filename),
            font=ctk.CTkFont(size=16, weight="bold")
        )
        lbl_title.pack(anchor="w")

        lbl_subtitle = ctk.CTkLabel(
            header_frame,
            text=Text.get("dialog_existing_metadata_subtitle"),
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        lbl_subtitle.pack(anchor="w", pady=(2, 0))

        # Textbox
        txt_box = ctk.CTkTextbox(self, font=ctk.CTkFont(family="Consolas", size=12), fg_color="#1a1b1e")
        txt_box.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")

        content_text = ""

        # Section 1: XMP Tags (Subject)
        tags = meta.existing_xmp_tags if meta else []
        header_xmp = Text.get("dialog_existing_metadata_xmp_tags")
        content_text += f"{header_xmp}\n"
        content_text += "=" * len(header_xmp) + "\n"
        if tags:
            for t in tags:
                content_text += f"  - {t}\n"
        else:
            content_text += f"{Text.get('dialog_existing_metadata_no_xmp_tags')}\n"
        
        # Section 2: Other XMP Fields
        raw_xmp = meta.raw_xmp_str if meta else ""
        properties = {}
        if raw_xmp:
            properties = extract_all_xmp_properties(raw_xmp)
        
        # Filter out keyword container keys
        filtered_props = {}
        keyword_patterns = ["subject", "tagslist", "hierarchicalsubject"]
        for k, v in properties.items():
            k_lower = k.lower()
            if not any(pat in k_lower for pat in keyword_patterns):
                filtered_props[k] = v

        header_fields = Text.get("dialog_existing_metadata_xmp_fields")
        content_text += f"\n{header_fields}\n"
        content_text += "=" * len(header_fields) + "\n"
        if filtered_props:
            # Sort properties for cleaner display
            for key in sorted(filtered_props.keys()):
                val = filtered_props[key]
                content_text += f"  {key}:\n"
                lines = val.split('\n')
                for line in lines:
                    content_text += f"    {line}\n"
                content_text += "\n"
        else:
            content_text += f"{Text.get('dialog_existing_metadata_no_xmp_fields')}\n"

        # Section 3: Binary EXIF Metadata
        header_exif = Text.get("dialog_existing_metadata_exif_title")
        content_text += f"\n{header_exif}\n"
        content_text += "=" * len(header_exif) + "\n"
        exif_props = {}
        if filepath and os.path.exists(filepath):
            try:
                from PIL import Image, ExifTags
                with Image.open(filepath) as img:
                    exif_data = img.getexif()
                    
                    # Read main IFD0 tags
                    for tag, val in exif_data.items():
                        if tag in [0x8769, 34665, 0x8825, 34853]:
                            continue
                        tag_name = ExifTags.TAGS.get(tag, str(tag))
                        exif_props[tag_name] = val
                        
                    # Read SubIFD tags safely
                    try:
                        sub_ifd = exif_data.get_ifd(0x8769)
                        if sub_ifd:
                            for tag, val in sub_ifd.items():
                                tag_name = ExifTags.TAGS.get(tag, str(tag))
                                if tag == 0x8822: # ExposureProgram
                                    prog_names = {
                                        0: "Not defined",
                                        1: "Manual",
                                        2: "Normal program",
                                        3: "Aperture priority",
                                        4: "Shutter priority",
                                        5: "Creative program (Biased toward depth of field)",
                                        6: "Action program (Biased toward fast shutter speed)",
                                        7: "Portrait mode",
                                        8: "Landscape mode"
                                    }
                                    val = f"{val} ({prog_names.get(val, 'Unknown')})"
                                exif_props[tag_name] = val
                    except Exception as sub_e:
                        print(f"Error reading Exif SubIFD: {sub_e}")
            except Exception as e:
                print(f"Error reading binary EXIF for details popup: {e}")
                
        if exif_props:
            for key in sorted(exif_props.keys()):
                val = exif_props[key]
                content_text += f"  {key}: {val}\n"
        else:
            content_text += f"{Text.get('dialog_existing_metadata_no_exif')}\n"

        txt_box.insert("1.0", content_text)
        txt_box.configure(state="disabled")

        # Bottom Frame
        bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        bottom_frame.grid(row=2, column=0, padx=20, pady=(5, 15), sticky="ew")

        btn_close = ctk.CTkButton(bottom_frame, text=Text.get("btn_close"), width=120, command=self.destroy)
        btn_close.pack(side="right")

class CustomMetadataDialog(ctk.CTkToplevel):
    """Modal popup dialog for entering custom metadata fields."""
    def __init__(self, parent, vars_dict: dict):
        super().__init__(parent)
        self.title(Text.get("dialog_custom_metadata_title"))
        self.geometry("500x380")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        # Center on parent window
        self.update_idletasks()
        parent_x = parent.winfo_x()
        parent_y = parent.winfo_y()
        parent_w = parent.winfo_width()
        parent_h = parent.winfo_height()
        
        # Center coordinates
        x = parent_x + (parent_w - 500) // 2
        y = parent_y + (parent_h - 380) // 2
        self.geometry(f"500x380+{max(0, x)}+{max(0, y)}")

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        main_frame = ctk.CTkFrame(self)
        main_frame.grid(row=0, column=0, padx=15, pady=15, sticky="nsew")
        main_frame.grid_columnconfigure(1, weight=1)

        # Title
        lbl_title = ctk.CTkLabel(
            main_frame,
            text=Text.get("dialog_custom_metadata_header"),
            font=ctk.CTkFont(size=15, weight="bold")
        )
        lbl_title.grid(row=0, column=0, columnspan=2, padx=15, pady=(15, 10), sticky="w")

        lbl_desc = ctk.CTkLabel(
            main_frame,
            text=Text.get("dialog_custom_metadata_desc"),
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        lbl_desc.grid(row=1, column=0, columnspan=2, padx=15, pady=(0, 15), sticky="w")

        # Field 1: Ersteller
        ctk.CTkLabel(main_frame, text=Text.get("dialog_custom_metadata_creator_label")).grid(row=2, column=0, padx=15, pady=6, sticky="e")
        self.entry_creator = ctk.CTkEntry(main_frame)
        self.entry_creator.insert(0, vars_dict["creator"].get())
        self.entry_creator.grid(row=2, column=1, padx=15, pady=6, sticky="ew")

        # Field 2: Copyright
        ctk.CTkLabel(main_frame, text=Text.get("dialog_custom_metadata_copyright_label")).grid(row=3, column=0, padx=15, pady=6, sticky="e")
        self.entry_copyright = ctk.CTkEntry(main_frame)
        self.entry_copyright.insert(0, vars_dict["copyright"].get())
        self.entry_copyright.grid(row=3, column=1, padx=15, pady=6, sticky="ew")

        # Field 3: Kamerahersteller
        ctk.CTkLabel(main_frame, text=Text.get("dialog_custom_metadata_camera_make_label")).grid(row=4, column=0, padx=15, pady=6, sticky="e")
        self.entry_camera_make = ctk.CTkEntry(main_frame)
        self.entry_camera_make.insert(0, vars_dict["camera_make"].get())
        self.entry_camera_make.grid(row=4, column=1, padx=15, pady=6, sticky="ew")

        # Field 4: Software
        ctk.CTkLabel(main_frame, text=Text.get("dialog_custom_metadata_software_label")).grid(row=5, column=0, padx=15, pady=6, sticky="e")
        self.entry_software = ctk.CTkEntry(main_frame)
        self.entry_software.insert(0, vars_dict["software"].get())
        self.entry_software.grid(row=5, column=1, padx=15, pady=6, sticky="ew")

        # Field 5: Kommentar
        ctk.CTkLabel(main_frame, text=Text.get("dialog_custom_metadata_comment_label")).grid(row=6, column=0, padx=15, pady=6, sticky="e")
        self.entry_comment = ctk.CTkEntry(main_frame)
        self.entry_comment.insert(0, vars_dict["comment"].get())
        self.entry_comment.grid(row=6, column=1, padx=15, pady=6, sticky="ew")

        # Buttons
        btn_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        btn_frame.grid(row=7, column=0, columnspan=2, padx=15, pady=(20, 10), sticky="ew")
        btn_frame.grid_columnconfigure(0, weight=1)

        btn_cancel = ctk.CTkButton(
            btn_frame,
            text=Text.get("dialog_custom_metadata_cancel"),
            width=100,
            fg_color="#495057",
            hover_color="#343a40",
            command=self.destroy
        )
        btn_cancel.pack(side="right", padx=(5, 0))

        btn_save = ctk.CTkButton(
            btn_frame,
            text=Text.get("dialog_custom_metadata_save"),
            width=100,
            fg_color="#1c7ed6",
            hover_color="#1864ab",
            command=self.save_and_close
        )
        btn_save.pack(side="right", padx=5)

        self.vars_dict = vars_dict
        self.saved = False

    def save_and_close(self):
        self.vars_dict["creator"].set(self.entry_creator.get().strip())
        self.vars_dict["copyright"].set(self.entry_copyright.get().strip())
        self.vars_dict["camera_make"].set(self.entry_camera_make.get().strip())
        self.vars_dict["software"].set(self.entry_software.get().strip())
        self.vars_dict["comment"].set(self.entry_comment.get().strip())
        self.saved = True
        self.destroy()

class ThemeEditorDialog(ctk.CTkToplevel):
    """Modal popup dialog for customizing theme colors."""
    def __init__(self, parent):
        super().__init__(parent)
        self.title(Text.get("dialog_theme_editor_title"))
        self.geometry("640x700")
        self.minsize(580, 500)
        self.transient(parent)
        self.grab_set()

        self.parent = parent

        # Center on parent window
        self.update_idletasks()
        parent_x = parent.winfo_x()
        parent_y = parent.winfo_y()
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()
        x = parent_x + (parent_width - 640) // 2
        y = parent_y + (parent_height - 700) // 2
        self.geometry(f"+{x}+{y}")

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Header Frame
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, padx=20, pady=(15, 10), sticky="ew")

        lbl_title = ctk.CTkLabel(
            header_frame,
            text=Text.get("dialog_theme_editor_title"),
            font=ctk.CTkFont(size=16, weight="bold")
        )
        lbl_title.pack(anchor="w")

        # Scrollable Frame for the 21 color variables
        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color=parent.get_theme_color("color_inner_frame_bg"))
        self.scroll_frame.grid(row=1, column=0, padx=20, pady=5, sticky="nsew")
        self.scroll_frame.grid_columnconfigure(0, weight=1)

        self.color_keys = [
            "color_primary_btn",
            "color_primary_hover",
            "color_secondary_btn",
            "color_secondary_hover",
            "color_danger_btn",
            "color_danger_hover",
            "color_warning_btn",
            "color_warning_hover",
            "color_neutral_btn",
            "color_neutral_hover",
            "color_inner_frame_bg",
            "color_info_link",
            "color_badge_untagged",
            "color_tag_new",
            "color_tag_existing",
            "color_tag_deleted",
            "color_tag_warning",
            "color_tag_low_warning",
            "color_tag_xmp_prefix",
            "color_listbox_details",
            "color_textbox_prompt_body",
            "color_label_text",
            "color_listbox_selected_bg",
            "color_progress_bar",
            "color_info_date",
            "color_tag_extra_meta"
        ]

        self.canvas_dict = {}

        for idx, key in enumerate(self.color_keys):
            row_frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
            row_frame.grid(row=idx, column=0, padx=10, pady=5, sticky="ew")
            row_frame.grid_columnconfigure(0, weight=1)

            # Label (Description)
            lbl = ctk.CTkLabel(row_frame, text=Text.get(key), font=ctk.CTkFont(size=11))
            lbl.pack(side="left", anchor="w", padx=(5, 10))

            # Action Frame on the right
            action_frame = ctk.CTkFrame(row_frame, fg_color="transparent")
            action_frame.pack(side="right")

            # Color preview canvas
            curr_color = parent.theme_colors.get(key, "#ffffff")
            canvas = tk.Canvas(action_frame, width=50, height=22, bg=curr_color, highlightthickness=1, highlightbackground="#495057")
            canvas.pack(side="left", padx=5)
            self.canvas_dict[key] = canvas

            # Edit Button
            btn_pick = ctk.CTkButton(
                action_frame,
                text="🎨",
                width=35,
                fg_color=parent.get_theme_color("color_neutral_btn"),
                hover_color=parent.get_theme_color("color_neutral_hover"),
                command=lambda k=key: self.pick_color(k)
            )
            btn_pick.pack(side="left")

        # Bottom Frame
        bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        bottom_frame.grid(row=2, column=0, padx=20, pady=(10, 15), sticky="ew")

        # Delete Button (if custom)
        is_custom = parent.active_theme not in DEFAULT_THEMES
        self.btn_delete = ctk.CTkButton(
            bottom_frame,
            text=Text.get("btn_delete_theme"),
            fg_color=parent.get_theme_color("color_danger_btn"),
            hover_color=parent.get_theme_color("color_danger_hover"),
            state="normal" if is_custom else "disabled",
            command=self.delete_theme
        )
        self.btn_delete.pack(side="left")

        # Close button
        btn_close = ctk.CTkButton(
            bottom_frame,
            text=Text.get("btn_close"),
            fg_color=parent.get_theme_color("color_neutral_btn"),
            hover_color=parent.get_theme_color("color_neutral_hover"),
            command=self.destroy
        )
        btn_close.pack(side="right")

        # Save As... button
        btn_save_as = ctk.CTkButton(
            bottom_frame,
            text=Text.get("btn_save_theme_as"),
            fg_color=parent.get_theme_color("color_primary_btn"),
            hover_color=parent.get_theme_color("color_primary_hover"),
            command=self.save_theme_as
        )
        btn_save_as.pack(side="right", padx=5)

    def pick_color(self, key):
        from tkinter import colorchooser
        initial_color = self.parent.theme_colors.get(key, "#ffffff")
        _, chosen = colorchooser.askcolor(initialcolor=initial_color, parent=self)
        if chosen:
            self.parent.theme_colors[key] = chosen
            self.canvas_dict[key].configure(bg=chosen)
            
            # Auto-save custom theme if active
            if self.parent.active_theme not in DEFAULT_THEMES:
                ThemeManager.save_theme(self.parent.active_theme, self.parent.theme_colors)
            
            # Hot-reload colors immediately in main window!
            self.parent.apply_theme()

    def save_theme_as(self):
        name = simpledialog.askstring(
            Text.get("btn_save_theme_as"),
            Text.get("msg_theme_save_prompt"),
            parent=self
        )
        if name and name.strip():
            safe_name = name.strip()
            if safe_name in DEFAULT_THEMES:
                messagebox.showerror(Text.get("msg_title_theme_error"), Text.get("msg_theme_delete_default_warning"))
                return
            
            # Save using ThemeManager
            if ThemeManager.save_theme(safe_name, self.parent.theme_colors):
                self.parent._update_theme_menu(select_name=safe_name)
                messagebox.showinfo(Text.get("msg_title_theme_saved"), Text.get("msg_theme_saved", name=safe_name))
                self.btn_delete.configure(state="normal")
            else:
                messagebox.showerror(Text.get("msg_title_theme_error"), Text.get("msg_theme_error"))

    def delete_theme(self):
        theme_name = self.parent.active_theme
        if theme_name in DEFAULT_THEMES:
            messagebox.showerror(Text.get("msg_title_theme_error"), Text.get("msg_theme_delete_default_warning"))
            return
            
        confirm = messagebox.askyesno(
            Text.get("msg_title_theme_delete_confirm"),
            Text.get("msg_theme_delete_confirm", name=theme_name),
            parent=self
        )
        if confirm:
            if ThemeManager.delete_theme(theme_name):
                self.parent._update_theme_menu(select_name="Standard Dark")
                messagebox.showinfo(Text.get("msg_title_theme_deleted"), Text.get("msg_theme_deleted", name=theme_name))
                self.destroy()

THUMB_SIZE_MAP = {
    "145": {"de": "Klein (145x145)", "en": "Small (145x145)"},
    "200": {"de": "Mittel (200x200)", "en": "Medium (200x200)"},
    "320": {"de": "Groß (320x320)", "en": "Large (320x320)"}
}

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Initialize default theme before building UI
        self.active_theme = "Standard Dark"
        self.theme_colors = dict(ThemeManager.get_theme_colors(self.active_theme))

        self.title(Text.get("app_title"))
        self.geometry("1200 x 880")
        self.minsize(1020, 700)

        self.scanned_files = [] # list of dicts: {path, filename, display_name, meta}
        self.is_processing = False
        self.cancel_processing = False
        self.scanning_active = False
        self.cancel_scanning = False
        self.current_selected_idx = 0
        self.current_thumb_image = None # reference to prevent GC
        self.status_tooltip = None
        self.translatable_widgets = []
        self.help_labels = []
        self.last_status_info = ("lbl_status_ready", {})

        # Default visible details items & sequence
        self.detail_items = [
            {"key": "checkpoint", "label_key": "listbox_model_title", "visible": True},
            {"key": "lora", "label_key": "listbox_loras_title", "visible": True},
            {"key": "resolution", "label_key": "listbox_resolution_title", "visible": False},
            {"key": "date", "label_key": "listbox_date_title", "visible": False}
        ]

        self.var_ui_thumb_size = tk.StringVar(value="200")
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self._build_ui()
        self._load_and_apply_saved_settings()

    def get_theme_color(self, color_key):
        return self.theme_colors.get(color_key, "#ffffff")

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # -------------------------------------------------------------
        # Header Frame
        # -------------------------------------------------------------
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, padx=20, pady=(8, 2), sticky="ew")

        self.title_label = ctk.CTkLabel(
            header_frame,
            text=Text.get("header_title"),
            font=ctk.CTkFont(size=18, weight="bold")
        )
        self.title_label.pack(side="left")
        self.register_widget(self.title_label, "header_title")

        self.subtitle_label = ctk.CTkLabel(
            header_frame,
            text=Text.get("header_subtitle"),
            font=ctk.CTkFont(size=12, slant="italic"),
            text_color="gray"
        )
        self.subtitle_label.pack(side="left", padx=15)
        self.register_widget(self.subtitle_label, "header_subtitle")

        # -------------------------------------------------------------
        # Main Tabview Component
        # -------------------------------------------------------------
        self.tabview = ctk.CTkTabview(self, anchor="nw")
        self.tabview.grid(row=1, column=0, padx=20, pady=(5, 10), sticky="nsew")

        self.tab_process = self.tabview.add("tab_process")
        self.tab_settings = self.tabview.add("tab_settings")
        self.tab_analyzer = self.tabview.add("tab_analyzer")
        self.tab_layout = self.tabview.add("tab_layout")
        self.tab_help = self.tabview.add("tab_help")

        # Set up Tabs
        self.selected_sample_filename = None
        self.selected_sample_file_path = None
        self.analyzer_state = "initial"
        self.help_frames = {}
        self._build_tab_process()
        self._build_tab_settings()
        self._build_tab_analyzer()
        self._build_tab_layout()
        self._build_tab_help()

        # -------------------------------------------------------------
        # Bottom Progress & Log Frame
        # -------------------------------------------------------------
        bottom_frame = ctk.CTkFrame(self)
        bottom_frame.grid(row=2, column=0, padx=20, pady=(0, 5), sticky="ew")
        bottom_frame.grid_columnconfigure(0, weight=1)

        self.progress_bar = ctk.CTkProgressBar(bottom_frame, progress_color=self.get_theme_color("color_progress_bar"))
        self.progress_bar.grid(row=0, column=0, padx=15, pady=(4, 2), sticky="ew")
        self.progress_bar.set(0)

        self.lbl_status = ctk.CTkLabel(bottom_frame, text=Text.get("lbl_status_ready"), font=ctk.CTkFont(size=12))
        self.lbl_status.grid(row=1, column=0, padx=15, pady=(0, 5), sticky="w")
        self.register_widget(self.lbl_status, "lbl_status_ready")

    # =================================================================
    # Tab 1: Processing & Preview Dashboard
    # =================================================================
    def _build_tab_process(self):
        tab = self.tab_process
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)

        # Top Row: Folder Selection & Recursive Checkbox
        folder_frame = ctk.CTkFrame(tab)
        folder_frame.grid(row=0, column=0, padx=10, pady=5, sticky="ew")
        folder_frame.grid_columnconfigure(1, weight=1)

        self.lbl_dir = ctk.CTkLabel(folder_frame, text=Text.get("scan_dir_label"), font=ctk.CTkFont(size=14, weight="bold"))
        self.lbl_dir.grid(row=0, column=0, padx=12, pady=(6, 1))
        self.register_widget(self.lbl_dir, "scan_dir_label")
        
        self.folder_entry = ctk.CTkEntry(folder_frame, placeholder_text=Text.get("scan_dir_placeholder"))
        self.folder_entry.grid(row=0, column=1, padx=5, pady=(6, 1), sticky="ew")

        self.btn_browse = ctk.CTkButton(
            folder_frame,
            text=Text.get("btn_browse"),
            width=120,
            fg_color=self.get_theme_color("color_neutral_btn"),
            hover_color=self.get_theme_color("color_neutral_hover"),
            command=self.browse_folder
        )
        self.btn_browse.grid(row=0, column=2, padx=5, pady=(6, 1))
        self.register_widget(self.btn_browse, "btn_browse")

        self.btn_next_folder = ctk.CTkButton(
            folder_frame,
            text=Text.get("btn_next_folder"),
            width=130,
            fg_color=self.get_theme_color("color_neutral_btn"),
            hover_color=self.get_theme_color("color_neutral_hover"),
            command=self.next_folder,
            state="disabled"
        )
        self.btn_next_folder.grid(row=0, column=3, padx=5, pady=(6, 1))
        self.register_widget(self.btn_next_folder, "btn_next_folder")

        self.btn_scan = ctk.CTkButton(
            folder_frame,
            text=Text.get("btn_scan"),
            width=130,
            fg_color=self.get_theme_color("color_primary_btn"),
            hover_color=self.get_theme_color("color_primary_hover"),
            command=self.scan_folder
        )
        self.btn_scan.grid(row=0, column=4, padx=(5, 12), pady=(6, 1))
        self.register_widget(self.btn_scan, "btn_scan")
        # Recursive Checkbox — placed in same row as buttons (column 5) to save vertical space
        self.var_recursive_scan = tk.BooleanVar(value=True)
        self.chk_recursive = ctk.CTkCheckBox(
            folder_frame,
            text=Text.get("chk_recursive_scan"),
            variable=self.var_recursive_scan,
            command=self.on_setting_changed
        )
        self.chk_recursive.grid(row=0, column=5, padx=(8, 12), pady=(6, 1), sticky="w")
        self.register_widget(self.chk_recursive, "chk_recursive_scan")
        ToolTip(self.chk_recursive, lambda: Text.get("chk_recursive_scan_tooltip"))

        # Middle Content: Draggable PanedWindow (Splitter between File List & Tag Preview)
        content_frame = ctk.CTkFrame(tab, fg_color="transparent")
        content_frame.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")
        content_frame.grid_columnconfigure(0, weight=1)
        content_frame.grid_rowconfigure(0, weight=1)

        # Tkinter PanedWindow for Draggable Sash Splitter
        self.paned_window = tk.PanedWindow(
            content_frame,
            orient=tk.HORIZONTAL,
            bg="#242424",
            bd=0,
            sashwidth=6,
            sashpad=2,
            sashrelief=tk.RAISED
        )
        self.paned_window.grid(row=0, column=0, sticky="nsew")

        # Left Column: File List
        files_box_frame = ctk.CTkFrame(self.paned_window)
        files_box_frame.grid_columnconfigure(0, weight=1)
        files_box_frame.grid_rowconfigure(2, weight=1)

        self.lbl_files_found = ctk.CTkLabel(
            files_box_frame,
            text=Text.get("lbl_files_found"),
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.lbl_files_found.grid(row=0, column=0, padx=12, pady=(10, 5), sticky="w")
        self.register_widget(self.lbl_files_found, "lbl_files_found")
        
        # Action Buttons for selection
        btn_select_frame = ctk.CTkFrame(files_box_frame, fg_color="transparent")
        btn_select_frame.grid(row=1, column=0, padx=12, pady=(0, 5), sticky="w")

        self.btn_select_all = ctk.CTkButton(
            btn_select_frame,
            text="☑️ " + Text.get("btn_select_all"),
            width=110,
            height=26,
            font=ctk.CTkFont(size=11),
            command=self.select_all_files
        )
        self.btn_select_all.pack(side="left", padx=(0, 10))
        self.register_widget(self.btn_select_all, "btn_select_all", prefix="☑️ ")

        self.btn_select_none = ctk.CTkButton(
            btn_select_frame,
            text="⬜ " + Text.get("btn_deselect_all"),
            width=120,
            height=26,
            font=ctk.CTkFont(size=11),
            command=self.select_no_files
        )
        self.btn_select_none.pack(side="left")
        self.register_widget(self.btn_select_none, "btn_deselect_all", prefix="⬜ ")

        # Label for scan summary (e.g. "902 images | 44 with XMP tags")
        self.lbl_scan_summary = ctk.CTkLabel(
            btn_select_frame,
            text="",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=self.get_theme_color("color_tag_existing")
        )
        self.lbl_scan_summary.pack(side="left", padx=(15, 0))

        # Colored warnings label packed next to the main summary
        self.lbl_scan_summary_warn = ctk.CTkLabel(
            btn_select_frame,
            text="",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=self.get_theme_color("color_tag_warning")
        )
        self.lbl_scan_summary_warn.pack(side="left", padx=(0, 0))

        # Listbox for files (re-implemented as CTkTextbox to prevent Windows GDI Object exhaustion)
        self.file_listbox = ctk.CTkTextbox(files_box_frame, font=ctk.CTkFont(family="Consolas", size=11), wrap="none", fg_color=self.get_theme_color("color_inner_frame_bg"))
        self.file_listbox.grid(row=2, column=0, padx=12, pady=(0, 12), sticky="nsew")
        
        # Configure custom rendering tags on underlying tk.Text
        tb = self.file_listbox._textbox
        tb.tag_config("checked_box", foreground=self.get_theme_color("color_tag_new"), font=ctk.CTkFont(family="Consolas", size=11, weight="bold"))
        tb.tag_config("unchecked_box", foreground=self.get_theme_color("color_tag_existing"), font=ctk.CTkFont(family="Consolas", size=11))
        tb.tag_config("xmp_prefix", foreground=self.get_theme_color("color_tag_xmp_prefix"), font=ctk.CTkFont(family="Consolas", size=11, weight="bold"))
        tb.tag_config("listbox_details", foreground=self.get_theme_color("color_listbox_details"), font=ctk.CTkFont(family="Consolas", size=11))
        tb.tag_config("selected_line", background=self.get_theme_color("color_secondary_btn"), foreground="#ffffff")
        tb.tag_raise("selected_line")
        
        # Bind events
        self.file_listbox.bind("<ButtonRelease-1>", self._on_file_click)
        self.file_listbox.bind("<KeyRelease-Up>", self._on_key_nav)
        self.file_listbox.bind("<KeyRelease-Down>", self._on_key_nav)
        self.file_listbox.bind("<Delete>", self._on_delete_key)

        # Right Column: Optimized Header (Metadata Left | Thumbnail Right) + Tag Textbox
        preview_box_frame = ctk.CTkFrame(self.paned_window)
        preview_box_frame.grid_columnconfigure(0, weight=1)
        preview_box_frame.grid_rowconfigure(2, weight=1)

        self.lbl_preview_title = ctk.CTkLabel(
            preview_box_frame,
            text=Text.get("lbl_preview_title"),
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.lbl_preview_title.grid(row=0, column=0, padx=12, pady=(10, 5), sticky="w")
        self.register_widget(self.lbl_preview_title, "lbl_preview_title")

        # Combined Top Info Container (Row 1)
        self.top_info_container = ctk.CTkFrame(preview_box_frame, fg_color=self.get_theme_color("color_inner_frame_bg"), corner_radius=6)
        self.top_info_container.grid(row=1, column=0, padx=12, pady=(0, 8), sticky="ew")
        self.top_info_container.grid_columnconfigure(0, weight=1)
        self.top_info_container.grid_columnconfigure(1, weight=0)

        # Left Info Frame (Metadata & Status Badge)
        left_info_frame = ctk.CTkFrame(self.top_info_container, fg_color="transparent")
        left_info_frame.grid(row=0, column=0, padx=12, pady=6, sticky="nw")
        left_info_frame.grid_columnconfigure(0, weight=1)

        # Status Badge Pill
        self.lbl_status_badge = ctk.CTkLabel(
            left_info_frame,
            text=Text.get("status_badge_no_images"),
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#495057",
            text_color="white",
            corner_radius=4,
            padx=8,
            pady=3
        )
        self.lbl_status_badge.grid(row=0, column=0, padx=0, pady=(0, 4), sticky="w")
        self.lbl_status_badge.bind("<Button-1>", self._on_status_badge_clicked)

        self.status_tooltip = ToolTip(self.lbl_status_badge, lambda: Text.get("status_badge_tooltip"))

        # Metadata Labels
        self.lbl_info_filename = ctk.CTkLabel(left_info_frame, text=Text.get("lbl_info_filename"), font=ctk.CTkFont(size=12, weight="bold"), height=22)
        self.lbl_info_filename.grid(row=1, column=0, padx=0, pady=0, sticky="w")
        self.register_widget(self.lbl_info_filename, "lbl_info_filename")

        self.lbl_info_resolution = ctk.CTkLabel(left_info_frame, text=Text.get("lbl_info_resolution"), font=ctk.CTkFont(size=11), text_color="#63e6be", height=20)
        self.lbl_info_resolution.grid(row=2, column=0, padx=0, pady=0, sticky="w")
        self.register_widget(self.lbl_info_resolution, "lbl_info_resolution")

        self.lbl_info_date = ctk.CTkLabel(left_info_frame, text=Text.get("lbl_info_date"), font=ctk.CTkFont(size=11), text_color=self.get_theme_color("color_info_date"), height=20)
        self.lbl_info_date.grid(row=3, column=0, padx=0, pady=0, sticky="w")
        self.register_widget(self.lbl_info_date, "lbl_info_date")

        self.lbl_info_models = ctk.CTkLabel(left_info_frame, text=Text.get("lbl_info_models"), font=ctk.CTkFont(size=11), text_color="gray85", wraplength=320, justify="left", height=20)
        self.lbl_info_models.grid(row=4, column=0, padx=0, pady=0, sticky="w")
        self.register_widget(self.lbl_info_models, "lbl_info_models")

        self.lbl_info_loras = ctk.CTkLabel(left_info_frame, text=Text.get("lbl_info_loras"), font=ctk.CTkFont(size=11), text_color="gray85", wraplength=320, justify="left", height=20)
        self.lbl_info_loras.grid(row=5, column=0, padx=0, pady=0, sticky="w")
        self.register_widget(self.lbl_info_loras, "lbl_info_loras")

        self.lbl_info_sampler = ctk.CTkLabel(left_info_frame, text=Text.get("lbl_info_sampler"), font=ctk.CTkFont(size=11), text_color="gray85", height=20)
        self.lbl_info_sampler.grid(row=6, column=0, padx=0, pady=0, sticky="w")
        self.register_widget(self.lbl_info_sampler, "lbl_info_sampler")

        # Right Frame (Thumbnail Label aligned to the right edge)
        init_size = 200
        try:
            init_size = int(self.var_ui_thumb_size.get())
        except Exception:
            pass
        self.lbl_thumb = ctk.CTkLabel(self.top_info_container, text="", width=init_size, height=init_size, cursor="hand2")
        self.lbl_thumb.grid(row=0, column=1, padx=10, pady=10, sticky="ne")
        self.lbl_thumb.bind("<Button-1>", self._on_thumbnail_clicked)
        ToolTip(self.lbl_thumb, lambda: Text.get("lbl_thumb_tooltip"))

        # Text Preview Box (Row 2 - Displays clean XMP Tags)
        self.tag_preview_box = ctk.CTkTextbox(preview_box_frame, font=ctk.CTkFont(family="Consolas", size=12), fg_color=self.get_theme_color("color_inner_frame_bg"))
        self.tag_preview_box.grid(row=2, column=0, padx=12, pady=(0, 12), sticky="nsew")

        # Add both panels to PanedWindow
        self.paned_window.add(files_box_frame, minsize=220)
        self.paned_window.add(preview_box_frame, minsize=350)

        # Bottom Bar: Reset Checkbox, Overwrite Checkbox & Process Button
        bottom_action_frame = ctk.CTkFrame(tab)
        bottom_action_frame.grid(row=2, column=0, padx=10, pady=3, sticky="ew")
        bottom_action_frame.grid_columnconfigure(0, weight=1)

        self.var_mode = tk.StringVar(value="embed")
        self.var_overwrite_tags = tk.BooleanVar(value=False)
        self.var_custom_creator = tk.StringVar(value="")
        self.var_custom_copyright = tk.StringVar(value="")
        self.var_custom_camera_make = tk.StringVar(value="")
        self.var_custom_software = tk.StringVar(value="")
        self.var_custom_comment = tk.StringVar(value="")

        # Left aligned sub-frame for checkboxes
        chk_frame = ctk.CTkFrame(bottom_action_frame, fg_color="transparent")
        chk_frame.grid(row=0, column=0, padx=5, pady=1, sticky="w")

        # Reset Checkbox
        self.var_reset_tags = tk.BooleanVar(value=False)
        self.chk_reset_tags = ctk.CTkCheckBox(
            chk_frame,
            text=Text.get("chk_reset_tags"),
            variable=self.var_reset_tags,
            command=self._on_reset_checkbox_toggled,
            fg_color="#c92a2a",
            hover_color="#a61e1e"
        )
        self.chk_reset_tags.pack(side="left", padx=10, pady=2)
        self.register_widget(self.chk_reset_tags, "chk_reset_tags")
        ToolTip(self.chk_reset_tags, lambda: Text.get("chk_reset_tags_tooltip"))

        # Overwrite / Clean-Write Checkbox
        self.chk_overwrite_tags = ctk.CTkCheckBox(
            chk_frame,
            text=Text.get("chk_overwrite_tags_ui"),
            variable=self.var_overwrite_tags,
            command=self.on_setting_changed,
            fg_color="#e67e22",
            hover_color="#d35400"
        )
        self.chk_overwrite_tags.pack(side="left", padx=10, pady=2)
        self.register_widget(self.chk_overwrite_tags, "chk_overwrite_tags_ui")
        ToolTip(self.chk_overwrite_tags, lambda: Text.get("chk_overwrite_tags_tooltip"))

        # Metadata Dialog Button
        self.btn_custom_meta = ctk.CTkButton(
            chk_frame,
            text=Text.get("btn_custom_meta_ui"),
            width=150,
            fg_color=self.get_theme_color("color_neutral_btn"),
            hover_color=self.get_theme_color("color_neutral_hover"),
            command=self.open_custom_metadata_dialog
        )
        self.btn_custom_meta.pack(side="left", padx=10, pady=2)
        self.register_widget(self.btn_custom_meta, "btn_custom_meta_ui")
        ToolTip(self.btn_custom_meta, lambda: Text.get("btn_custom_meta_tooltip"))

        self.btn_process = ctk.CTkButton(
            bottom_action_frame,
            text="⚡ XMP-Tags auf Bilder anwenden",
            font=ctk.CTkFont(size=15, weight="bold"),
            height=36,
            width=260,
            fg_color=self.get_theme_color("color_primary_btn"),
            hover_color=self.get_theme_color("color_primary_hover"),
            command=self.start_batch_processing
        )
        self.btn_process.grid(row=0, column=1, padx=12, pady=3, sticky="e")

    # =================================================================
    # Tab 2: Settings & Tag Rules
    # =================================================================
    def _build_tab_settings(self):
        tab = self.tab_settings
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)

        scroll_container = ctk.CTkScrollableFrame(tab)
        scroll_container.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        scroll_container.grid_columnconfigure(0, weight=1, uniform="settings_cols")
        scroll_container.grid_columnconfigure(1, weight=1, uniform="settings_cols")

        # Section 0: Preset Management Bar (Spans both columns)
        self.sec_preset = ctk.CTkFrame(scroll_container, fg_color=self.get_theme_color("color_inner_frame_bg"))
        self.sec_preset.grid(row=0, column=0, columnspan=2, padx=10, pady=(10, 5), sticky="ew")
        self.sec_preset.grid_columnconfigure(1, weight=1)

        self.lbl_sec_presets = ctk.CTkLabel(self.sec_preset, text=Text.get("lbl_presets"), font=ctk.CTkFont(size=15, weight="bold"))
        self.lbl_sec_presets.grid(row=0, column=0, padx=15, pady=12, sticky="w")
        self.register_widget(self.lbl_sec_presets, "lbl_presets")

        self.option_preset = ctk.CTkOptionMenu(self.sec_preset, values=list_presets(), width=200)
        self.option_preset.grid(row=0, column=1, padx=10, pady=12, sticky="w")

        self.btn_load_p = ctk.CTkButton(self.sec_preset, text=Text.get("btn_load"), width=80, fg_color=self.get_theme_color("color_primary_btn"), hover_color=self.get_theme_color("color_primary_hover"), command=self.btn_load_preset_clicked)
        self.btn_load_p.grid(row=0, column=2, padx=4, pady=12)
        self.register_widget(self.btn_load_p, "btn_load")

        self.btn_quick_save_p = ctk.CTkButton(self.sec_preset, text=Text.get("btn_save_preset"), width=90, fg_color=self.get_theme_color("color_secondary_btn"), hover_color=self.get_theme_color("color_secondary_hover"), command=self.btn_quick_save_preset_clicked)
        self.btn_quick_save_p.grid(row=0, column=3, padx=4, pady=12)
        self.register_widget(self.btn_quick_save_p, "btn_save_preset")

        btn_save_p = ctk.CTkButton(self.sec_preset, text=Text.get("btn_save_preset_as"), width=130, command=self.btn_save_preset_clicked)
        btn_save_p.grid(row=0, column=4, padx=4, pady=12)
        self.register_widget(btn_save_p, "btn_save_preset_as")

        self.btn_save_def = ctk.CTkButton(self.sec_preset, text=Text.get("btn_save_default"), width=110, fg_color=self.get_theme_color("color_warning_btn"), hover_color=self.get_theme_color("color_warning_hover"), command=self.btn_save_default_clicked)
        self.btn_save_def.grid(row=0, column=5, padx=4, pady=12)
        self.register_widget(self.btn_save_def, "btn_save_default")

        self.btn_del_p = ctk.CTkButton(self.sec_preset, text=Text.get("btn_delete_preset"), width=80, fg_color=self.get_theme_color("color_danger_btn"), hover_color=self.get_theme_color("color_danger_hover"), command=self.btn_delete_preset_clicked)
        self.btn_del_p.grid(row=0, column=6, padx=(4, 15), pady=12)
        self.register_widget(self.btn_del_p, "btn_delete_preset")

        # Helper to create styled headers with info tooltip buttons
        def create_section_header(parent, title_key, tooltip_key, col_span=3):
            h_frame = ctk.CTkFrame(parent, fg_color="transparent")
            h_frame.grid(row=0, column=0, columnspan=col_span, padx=15, pady=(12, 8), sticky="w")
            lbl = ctk.CTkLabel(h_frame, text=Text.get(title_key), font=ctk.CTkFont(size=15, weight="bold"))
            lbl.pack(side="left")
            self.register_widget(lbl, title_key)
            help_lbl = ctk.CTkLabel(h_frame, text=" 🛈", font=ctk.CTkFont(size=22, weight="bold"), text_color=self.get_theme_color("color_info_link"), cursor="hand2")
            help_lbl.pack(side="left", padx=5)
            self.help_labels.append(help_lbl)
            ToolTip(help_lbl, lambda: Text.get(tooltip_key))
            return h_frame

        # Create Left and Right Column Frames
        left_column = ctk.CTkFrame(scroll_container, fg_color="transparent")
        left_column.grid(row=1, column=0, padx=(10, 5), pady=5, sticky="nsew")
        left_column.grid_columnconfigure(0, weight=1)

        right_column = ctk.CTkFrame(scroll_container, fg_color="transparent")
        right_column.grid(row=1, column=1, padx=(5, 10), pady=5, sticky="nsew")
        right_column.grid_columnconfigure(0, weight=1)

        # ==========================================
        # LEFT COLUMN
        # ==========================================

        # Section 1: Categories & Prefixes (Option C compact design)
        sec_categories = ctk.CTkFrame(left_column)
        sec_categories.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        sec_categories.grid_columnconfigure(0, weight=1)
        sec_categories.grid_columnconfigure(2, weight=1)

        create_section_header(
            sec_categories, 
            "lbl_sec_categories_prefixes", 
            "lbl_sec_categories_prefixes_tooltip"
        )

        # Models
        self.var_models = tk.BooleanVar(value=True)
        self.chk_models = ctk.CTkCheckBox(sec_categories, text=Text.get("chk_include_models"), variable=self.var_models, command=self.on_setting_changed)
        self.chk_models.grid(row=1, column=0, padx=15, pady=4, sticky="w")
        self.register_widget(self.chk_models, "chk_include_models")
        
        lbl_pref1 = ctk.CTkLabel(sec_categories, text=Text.get("lbl_prefix_short"))
        lbl_pref1.grid(row=1, column=1, padx=5, pady=4, sticky="e")
        self.register_widget(lbl_pref1, "lbl_prefix_short")
        
        self.entry_prefix_model = ctk.CTkEntry(sec_categories, width=120)
        self.entry_prefix_model.insert(0, "Model")
        self.entry_prefix_model.grid(row=1, column=2, padx=(5, 15), pady=4, sticky="ew")

        # Loras
        self.var_loras = tk.BooleanVar(value=True)
        self.chk_loras = ctk.CTkCheckBox(sec_categories, text=Text.get("chk_include_loras"), variable=self.var_loras, command=self.on_setting_changed)
        self.chk_loras.grid(row=2, column=0, padx=15, pady=4, sticky="w")
        self.register_widget(self.chk_loras, "chk_include_loras")
        
        lbl_pref2 = ctk.CTkLabel(sec_categories, text=Text.get("lbl_prefix_short"))
        lbl_pref2.grid(row=2, column=1, padx=5, pady=4, sticky="e")
        self.register_widget(lbl_pref2, "lbl_prefix_short")
        
        self.entry_prefix_lora = ctk.CTkEntry(sec_categories, width=120)
        self.entry_prefix_lora.insert(0, "Lora")
        self.entry_prefix_lora.grid(row=2, column=2, padx=(5, 15), pady=4, sticky="ew")

        # Samplers
        self.var_samplers = tk.BooleanVar(value=True)
        self.chk_samplers = ctk.CTkCheckBox(sec_categories, text=Text.get("chk_include_samplers"), variable=self.var_samplers, command=self.on_setting_changed)
        self.chk_samplers.grid(row=3, column=0, padx=15, pady=4, sticky="w")
        self.register_widget(self.chk_samplers, "chk_include_samplers")
        
        lbl_pref3 = ctk.CTkLabel(sec_categories, text=Text.get("lbl_prefix_short"))
        lbl_pref3.grid(row=3, column=1, padx=5, pady=4, sticky="e")
        self.register_widget(lbl_pref3, "lbl_prefix_short")
        
        self.entry_prefix_sampler = ctk.CTkEntry(sec_categories, width=120)
        self.entry_prefix_sampler.insert(0, "Sampler")
        self.entry_prefix_sampler.grid(row=3, column=2, padx=(5, 15), pady=4, sticky="ew")

        # Prompts
        self.var_prompts = tk.BooleanVar(value=True)
        self.chk_prompts = ctk.CTkCheckBox(sec_categories, text=Text.get("chk_include_prompts"), variable=self.var_prompts, command=self.on_setting_changed)
        self.chk_prompts.grid(row=4, column=0, padx=15, pady=4, sticky="w")
        self.register_widget(self.chk_prompts, "chk_include_prompts")
        
        lbl_pref4 = ctk.CTkLabel(sec_categories, text=Text.get("lbl_prefix_short"))
        lbl_pref4.grid(row=4, column=1, padx=5, pady=4, sticky="e")
        self.register_widget(lbl_pref4, "lbl_prefix_short")
        
        self.entry_prefix_prompt = ctk.CTkEntry(sec_categories, width=120)
        self.entry_prefix_prompt.insert(0, "Prompt")
        self.entry_prefix_prompt.grid(row=4, column=2, padx=(5, 15), pady=4, sticky="ew")

        # Flat Tags (dc:subject)
        self.var_write_flat = tk.BooleanVar(value=True)
        self.chk_write_flat = ctk.CTkCheckBox(sec_categories, text=Text.get("chk_write_flat_dc"), variable=self.var_write_flat, command=self.on_setting_changed)
        self.chk_write_flat.grid(row=5, column=0, columnspan=3, padx=15, pady=(4, 12), sticky="w")
        self.register_widget(self.chk_write_flat, "chk_write_flat_dc")

        # Section 2: Resolution / Megapixel Tiers
        sec_res = ctk.CTkFrame(left_column)
        sec_res.grid(row=1, column=0, padx=5, pady=5, sticky="ew")
        sec_res.grid_columnconfigure(1, weight=1)

        create_section_header(
            sec_res, 
            "lbl_sec_resolution_tiers", 
            "lbl_sec_resolution_tiers_tooltip",
            col_span=2
        )

        self.var_include_resolution = tk.BooleanVar(value=True)
        self.chk_include_resolution = ctk.CTkCheckBox(sec_res, text=Text.get("chk_include_resolution"), variable=self.var_include_resolution, command=self.on_setting_changed)
        self.chk_include_resolution.grid(row=1, column=0, columnspan=2, padx=15, pady=4, sticky="w")
        self.register_widget(self.chk_include_resolution, "chk_include_resolution")

        self.lbl_prefix_resolution = ctk.CTkLabel(sec_res, text=Text.get("lbl_res_prefix"))
        self.lbl_prefix_resolution.grid(row=2, column=0, padx=15, pady=4, sticky="w")
        self.register_widget(self.lbl_prefix_resolution, "lbl_res_prefix")
        
        self.entry_prefix_resolution = ctk.CTkEntry(sec_res, width=120)
        self.entry_prefix_resolution.insert(0, "Resolution")
        self.entry_prefix_resolution.grid(row=2, column=1, padx=15, pady=4, sticky="w")

        # Tier 1
        self.lbl_res_tier1 = ctk.CTkLabel(sec_res, text=Text.get("lbl_res_tier1"))
        self.lbl_res_tier1.grid(row=3, column=0, padx=15, pady=4, sticky="w")
        self.register_widget(self.lbl_res_tier1, "lbl_res_tier1")
        
        tier1_frame = ctk.CTkFrame(sec_res, fg_color="transparent")
        tier1_frame.grid(row=3, column=1, padx=15, pady=4, sticky="w")
        self.entry_res_t1_mp = ctk.CTkEntry(tier1_frame, width=50)
        self.entry_res_t1_mp.insert(0, "1.0")
        self.entry_res_t1_mp.pack(side="left", padx=(0, 5))
        
        lbl_mp1 = ctk.CTkLabel(tier1_frame, text=Text.get("lbl_res_tier1_name")) # Name
        lbl_mp1.pack(side="left", padx=5)
        self.register_widget(lbl_mp1, "lbl_res_tier1_name")
        
        self.entry_res_t1_name = ctk.CTkEntry(tier1_frame, width=100)
        self.entry_res_t1_name.insert(0, "Preview")
        self.entry_res_t1_name.pack(side="left", padx=5)

        # Tier 2
        self.lbl_res_tier2 = ctk.CTkLabel(sec_res, text=Text.get("lbl_res_tier2_desc"))
        self.lbl_res_tier2.grid(row=4, column=0, padx=15, pady=4, sticky="w")
        self.register_widget(self.lbl_res_tier2, "lbl_res_tier2_desc")
        
        tier2_frame = ctk.CTkFrame(sec_res, fg_color="transparent")
        tier2_frame.grid(row=4, column=1, padx=15, pady=4, sticky="w")
        self.entry_res_t2_mp = ctk.CTkEntry(tier2_frame, width=50)
        self.entry_res_t2_mp.insert(0, "2.5")
        self.entry_res_t2_mp.pack(side="left", padx=(0, 5))
        
        lbl_mp2 = ctk.CTkLabel(tier2_frame, text=Text.get("lbl_res_tier1_name")) # name
        lbl_mp2.pack(side="left", padx=5)
        self.register_widget(lbl_mp2, "lbl_res_tier1_name")
        
        self.entry_res_t2_name = ctk.CTkEntry(tier2_frame, width=100)
        self.entry_res_t2_name.insert(0, "Standard")
        self.entry_res_t2_name.pack(side="left", padx=5)

        # Tier 3
        self.lbl_res_tier3 = ctk.CTkLabel(sec_res, text=Text.get("lbl_res_tier3_desc"))
        self.lbl_res_tier3.grid(row=5, column=0, padx=15, pady=(4, 12), sticky="w")
        self.register_widget(self.lbl_res_tier3, "lbl_res_tier3_desc")
        
        tier3_frame = ctk.CTkFrame(sec_res, fg_color="transparent")
        tier3_frame.grid(row=5, column=1, padx=15, pady=(4, 12), sticky="w")
        
        lbl_mp3_limit = ctk.CTkLabel(tier3_frame, text=Text.get("lbl_res_tier2_mp_arrow"))
        lbl_mp3_limit.pack(side="left", padx=(0, 5))
        self.register_widget(lbl_mp3_limit, "lbl_res_tier2_mp_arrow")
        
        self.entry_res_t3_name = ctk.CTkEntry(tier3_frame, width=100)
        self.entry_res_t3_name.insert(0, "Upscale")
        self.entry_res_t3_name.pack(side="left", padx=5)

        # Section 4: Active LoRA & Node Filtering
        sec_filter = ctk.CTkFrame(left_column)
        sec_filter.grid(row=2, column=0, padx=5, pady=5, sticky="ew")
        sec_filter.grid_columnconfigure(1, weight=1)

        create_section_header(
            sec_filter, 
            "lbl_sec_active_lora_filter", 
            "lbl_sec_active_lora_filter_tooltip",
            col_span=2
        )

        self.var_ignore_inactive = tk.BooleanVar(value=True)
        self.chk_ignore_inactive = ctk.CTkCheckBox(sec_filter, text=Text.get("chk_ignore_inactive_nodes"), variable=self.var_ignore_inactive, command=self.on_setting_changed)
        self.chk_ignore_inactive.grid(row=1, column=0, columnspan=2, padx=15, pady=4, sticky="w")
        self.register_widget(self.chk_ignore_inactive, "chk_ignore_inactive_nodes")

        self.lbl_min_strength = ctk.CTkLabel(sec_filter, text=Text.get("lbl_min_lora_strength"))
        self.lbl_min_strength.grid(row=2, column=0, padx=15, pady=(4, 12), sticky="w")
        self.register_widget(self.lbl_min_strength, "lbl_min_lora_strength")
        
        self.entry_min_strength = ctk.CTkEntry(sec_filter, width=80)
        self.entry_min_strength.insert(0, "0.01")
        self.entry_min_strength.grid(row=2, column=1, padx=15, pady=(4, 12), sticky="w")

        # Section 7: Storage Mode
        sec_storage = ctk.CTkFrame(left_column)
        sec_storage.grid(row=3, column=0, padx=5, pady=5, sticky="ew")
        sec_storage.grid_columnconfigure(0, weight=1)

        create_section_header(
            sec_storage,
            "lbl_sec_storage_mode",
            "lbl_sec_storage_mode_tooltip",
            col_span=1
        )

        self.rad_embed = ctk.CTkRadioButton(sec_storage, text=Text.get("rad_storage_embed"), variable=self.var_mode, value="embed", command=self.on_setting_changed)
        self.rad_embed.grid(row=1, column=0, padx=15, pady=4, sticky="w")
        self.register_widget(self.rad_embed, "rad_storage_embed")

        self.rad_sidecar = ctk.CTkRadioButton(sec_storage, text=Text.get("rad_storage_sidecar"), variable=self.var_mode, value="sidecar", command=self.on_setting_changed)
        self.rad_sidecar.grid(row=2, column=0, padx=15, pady=4, sticky="w")
        self.register_widget(self.rad_sidecar, "rad_storage_sidecar")

        self.var_ui_show_tagging_confirm = tk.BooleanVar(value=True)
        self.chk_show_tagging_confirm = ctk.CTkCheckBox(
            sec_storage,
            text=Text.get("chk_show_tagging_confirm"),
            variable=self.var_ui_show_tagging_confirm,
            command=self.on_setting_changed
        )
        self.chk_show_tagging_confirm.grid(row=3, column=0, padx=15, pady=(4, 12), sticky="w")
        self.register_widget(self.chk_show_tagging_confirm, "chk_show_tagging_confirm")
        ToolTip(self.chk_show_tagging_confirm, lambda: Text.get("chk_show_tagging_confirm_tooltip"))

        # ==========================================
        # RIGHT COLUMN
        # ==========================================

        # Section 3: Custom Prompt Keys
        sec_keys = ctk.CTkFrame(right_column)
        sec_keys.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        sec_keys.grid_columnconfigure(0, weight=1)

        create_section_header(
            sec_keys, 
            "lbl_sec_custom_prompt_keys", 
            "lbl_sec_custom_prompt_keys_tooltip",
            col_span=1
        )
        self.lbl_prompt_keys_desc = ctk.CTkLabel(sec_keys, text=Text.get("lbl_prompt_keys_desc"), font=ctk.CTkFont(size=11), text_color="gray")
        self.lbl_prompt_keys_desc.grid(row=1, column=0, padx=15, pady=(0, 4), sticky="w")
        self.register_widget(self.lbl_prompt_keys_desc, "lbl_prompt_keys_desc")

        self.entry_prompt_keys = ctk.CTkTextbox(sec_keys, height=110, font=ctk.CTkFont(family="Consolas", size=11))
        self.entry_prompt_keys.insert("1.0", "text\ntext_0\ntext_1\ntext_positive\npositive\nprompt\ntext_g\ntext_l\nwildcard\nwildcard_text")
        self.entry_prompt_keys.grid(row=2, column=0, padx=15, pady=(0, 12), sticky="ew")

        # Section 5: Whitelist (Positiv-Liste)
        sec_whitelist = ctk.CTkFrame(right_column)
        sec_whitelist.grid(row=1, column=0, padx=5, pady=5, sticky="ew")
        sec_whitelist.grid_columnconfigure(0, weight=1)

        create_section_header(
            sec_whitelist, 
            "lbl_sec_whitelist", 
            "lbl_sec_whitelist_tooltip",
            col_span=1
        )
        
        self.var_use_whitelist = tk.BooleanVar(value=False)
        self.chk_use_whitelist = ctk.CTkCheckBox(sec_whitelist, text=Text.get("chk_use_whitelist"), variable=self.var_use_whitelist, command=self.on_setting_changed)
        self.chk_use_whitelist.grid(row=1, column=0, padx=15, pady=4, sticky="w")
        self.register_widget(self.chk_use_whitelist, "chk_use_whitelist")

        self.entry_whitelist = ctk.CTkEntry(sec_whitelist, placeholder_text="z.B. cyberpunk, portrait, landscape")
        self.entry_whitelist.insert(0, "cyberpunk, portrait, landscape, outdoor, 1girl, realistic")
        self.entry_whitelist.grid(row=2, column=0, padx=15, pady=(4, 4), sticky="ew")

        self.lbl_edit_whitelist = ctk.CTkLabel(
            sec_whitelist,
            text=Text.get("lbl_edit_whitelist"),
            font=ctk.CTkFont(size=13, underline=True),
            text_color=self.get_theme_color("color_info_link"),
            cursor="hand2"
        )
        self.lbl_edit_whitelist.grid(row=3, column=0, padx=15, pady=(0, 12), sticky="w")
        self.lbl_edit_whitelist.bind("<Button-1>", lambda event: self.open_whitelist_file())
        self.register_widget(self.lbl_edit_whitelist, "lbl_edit_whitelist")

        # Section 6: Blacklist (Stopwords & Length Filter)
        sec_blacklist = ctk.CTkFrame(right_column)
        sec_blacklist.grid(row=2, column=0, padx=5, pady=5, sticky="ew")
        sec_blacklist.grid_columnconfigure(1, weight=1)

        create_section_header(
            sec_blacklist, 
            "lbl_sec_blacklist", 
            "lbl_sec_blacklist_tooltip",
            col_span=2
        )

        self.var_ignore_numeric = tk.BooleanVar(value=True)
        self.chk_ignore_numeric = ctk.CTkCheckBox(sec_blacklist, text=Text.get("chk_ignore_numeric_tags"), variable=self.var_ignore_numeric, command=self.on_setting_changed)
        self.chk_ignore_numeric.grid(row=1, column=0, columnspan=2, padx=15, pady=4, sticky="w")
        self.register_widget(self.chk_ignore_numeric, "chk_ignore_numeric_tags")

        self.var_lowercase_prompt_tags = tk.BooleanVar(value=False)
        self.chk_lowercase_prompt_tags = ctk.CTkCheckBox(sec_blacklist, text=Text.get("chk_lowercase_prompt_tags"), variable=self.var_lowercase_prompt_tags, command=self.on_setting_changed)
        self.chk_lowercase_prompt_tags.grid(row=2, column=0, columnspan=2, padx=15, pady=4, sticky="w")
        self.register_widget(self.chk_lowercase_prompt_tags, "chk_lowercase_prompt_tags")

        self.lbl_max_tag_length = ctk.CTkLabel(sec_blacklist, text=Text.get("lbl_max_tag_length"))
        self.lbl_max_tag_length.grid(row=3, column=0, padx=15, pady=4, sticky="w")
        self.register_widget(self.lbl_max_tag_length, "lbl_max_tag_length")
        
        self.entry_max_tag_length = ctk.CTkEntry(sec_blacklist, width=80)
        self.entry_max_tag_length.insert(0, "50")
        self.entry_max_tag_length.grid(row=3, column=1, padx=15, pady=4, sticky="w")

        self.lbl_blacklist_tags = ctk.CTkLabel(sec_blacklist, text=Text.get("lbl_blacklist_tags"), font=ctk.CTkFont(size=11), text_color="gray")
        self.lbl_blacklist_tags.grid(row=4, column=0, columnspan=2, padx=15, pady=(8, 2), sticky="w")
        self.register_widget(self.lbl_blacklist_tags, "lbl_blacklist_tags")

        self.entry_blacklist = ctk.CTkEntry(sec_blacklist, placeholder_text="z.B. masterpiece, best quality")
        self.entry_blacklist.insert(0, "masterpiece, best quality, ultra detailed, highly detailed")
        self.entry_blacklist.grid(row=5, column=0, columnspan=2, padx=15, pady=(0, 4), sticky="ew")

        self.lbl_edit_blacklist = ctk.CTkLabel(
            sec_blacklist,
            text=Text.get("lbl_edit_blacklist"),
            font=ctk.CTkFont(size=13, underline=True),
            text_color=self.get_theme_color("color_info_link"),
            cursor="hand2"
        )
        self.lbl_edit_blacklist.grid(row=6, column=0, columnspan=2, padx=15, pady=(0, 8), sticky="w")
        self.lbl_edit_blacklist.bind("<Button-1>", lambda event: self.open_blacklist_file())
        self.register_widget(self.lbl_edit_blacklist, "lbl_edit_blacklist")

        self.var_word_based_tagging = tk.BooleanVar(value=False)
        self.chk_word_based_tagging = ctk.CTkCheckBox(
            sec_blacklist,
            text=Text.get("chk_word_based_tagging"),
            variable=self.var_word_based_tagging,
            command=self.on_setting_changed
        )
        self.chk_word_based_tagging.grid(row=7, column=0, columnspan=2, padx=15, pady=(4, 4), sticky="w")
        self.register_widget(self.chk_word_based_tagging, "chk_word_based_tagging")

        self.lbl_edit_stopwords = ctk.CTkLabel(
            sec_blacklist,
            text=Text.get("lbl_edit_stopwords"),
            font=ctk.CTkFont(size=13, underline=True),
            text_color="#74c0fc",
            cursor="hand2"
        )
        self.lbl_edit_stopwords.grid(row=8, column=0, columnspan=2, padx=35, pady=(0, 4), sticky="w")
        self.lbl_edit_stopwords.bind("<Button-1>", lambda event: self.open_stopwords_file())
        self.register_widget(self.lbl_edit_stopwords, "lbl_edit_stopwords")

        self.lbl_edit_adjectives = ctk.CTkLabel(
            sec_blacklist,
            text=Text.get("lbl_edit_adjectives"),
            font=ctk.CTkFont(size=13, underline=True),
            text_color="#74c0fc",
            cursor="hand2"
        )
        self.lbl_edit_adjectives.grid(row=9, column=0, columnspan=2, padx=35, pady=(0, 4), sticky="w")
        self.lbl_edit_adjectives.bind("<Button-1>", lambda event: self.open_adjectives_file())
        self.register_widget(self.lbl_edit_adjectives, "lbl_edit_adjectives")

        self.lbl_edit_short_words = ctk.CTkLabel(
            sec_blacklist,
            text=Text.get("lbl_edit_short_words"),
            font=ctk.CTkFont(size=13, underline=True),
            text_color="#74c0fc",
            cursor="hand2"
        )
        self.lbl_edit_short_words.grid(row=10, column=0, columnspan=2, padx=35, pady=(0, 12), sticky="w")
        self.lbl_edit_short_words.bind("<Button-1>", lambda event: self.open_short_words_file())
        self.register_widget(self.lbl_edit_short_words, "lbl_edit_short_words")

        # Section 8: Additional EXIF / XMP Metadata
        sec_extra_meta = ctk.CTkFrame(right_column)
        sec_extra_meta.grid(row=3, column=0, padx=5, pady=5, sticky="ew")
        sec_extra_meta.grid_columnconfigure(0, weight=1)

        create_section_header(
            sec_extra_meta,
            "lbl_sec_extra_meta",
            "lbl_sec_extra_meta_tooltip",
            col_span=1
        )

        self.var_write_created_date = tk.BooleanVar(value=False)
        self.chk_write_created_date = ctk.CTkCheckBox(
            sec_extra_meta,
            text=Text.get("chk_write_created_date"),
            variable=self.var_write_created_date,
            command=self.on_setting_changed
        )
        self.chk_write_created_date.grid(row=1, column=0, padx=15, pady=4, sticky="w")
        self.register_widget(self.chk_write_created_date, "chk_write_created_date")

        self.var_write_camera_model = tk.BooleanVar(value=False)
        self.chk_write_camera_model = ctk.CTkCheckBox(
            sec_extra_meta,
            text=Text.get("chk_write_camera_model"),
            variable=self.var_write_camera_model,
            command=self.on_setting_changed
        )
        self.chk_write_camera_model.grid(row=2, column=0, padx=15, pady=4, sticky="w")
        self.register_widget(self.chk_write_camera_model, "chk_write_camera_model")

        self.var_write_description = tk.BooleanVar(value=False)
        self.chk_write_description = ctk.CTkCheckBox(
            sec_extra_meta,
            text=Text.get("chk_write_description"),
            variable=self.var_write_description,
            command=self.on_setting_changed
        )
        self.chk_write_description.grid(row=3, column=0, padx=15, pady=(4, 12), sticky="w")
        self.register_widget(self.chk_write_description, "chk_write_description")

    def _build_tab_analyzer(self):
        tab = self.tab_analyzer
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)

        # Main Header frame for controls, info and thumbnail
        header_frame = ctk.CTkFrame(tab, fg_color="transparent")
        header_frame.grid(row=0, column=0, padx=10, pady=(10, 0), sticky="ew")
        header_frame.grid_columnconfigure(0, weight=1)
        header_frame.grid_columnconfigure(1, weight=0)

        # Left controls and explanation container
        left_header = ctk.CTkFrame(header_frame, fg_color="transparent")
        left_header.grid(row=0, column=0, sticky="nsew")
        left_header.grid_columnconfigure(1, weight=1)

        self.btn_select_sample = ctk.CTkButton(
            left_header,
            text=Text.get("btn_select_sample"),
            command=self.select_sample_image,
            fg_color=self.get_theme_color("color_primary_btn"),
            hover_color=self.get_theme_color("color_primary_hover")
        )
        self.btn_select_sample.grid(row=0, column=0, padx=(0, 10), pady=5, sticky="w")
        self.register_widget(self.btn_select_sample, "btn_select_sample")

        self.lbl_sample_file = ctk.CTkLabel(
            left_header,
            text=Text.get("lbl_sample_file_placeholder"),
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="gray85"
        )
        self.lbl_sample_file.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        # Instruction & Info Label under the select button
        self.lbl_analyzer_info = ctk.CTkLabel(
            left_header,
            text=Text.get("lbl_analyzer_instruction"),
            font=ctk.CTkFont(size=12),
            text_color="gray85",
            justify="left",
            wraplength=700
        )
        self.lbl_analyzer_info.grid(row=1, column=0, columnspan=2, padx=0, pady=(12, 5), sticky="w")

        # Preview Thumbnail on the right of header_frame
        init_size = 200
        try:
            init_size = int(self.var_ui_thumb_size.get())
        except Exception:
            pass
        self.lbl_analyzer_thumb = ctk.CTkLabel(header_frame, text="", width=init_size, height=init_size)
        self.lbl_analyzer_thumb.grid(row=0, column=1, padx=10, pady=5, sticky="ne")

        # Scrollable container for candidates (spans full width)
        self.analyzer_scroll = ctk.CTkScrollableFrame(tab)
        self.analyzer_scroll.grid(row=1, column=0, padx=10, pady=(5, 10), sticky="nsew")
        self.analyzer_scroll.grid_columnconfigure(0, weight=1)


    def _clear_analyzer_results(self):
        for widget in self.analyzer_scroll.winfo_children():
            widget.destroy()

    def _update_analyzer_thumbnail(self):
        if not hasattr(self, "lbl_analyzer_thumb") or not self.lbl_analyzer_thumb:
            return
        if not hasattr(self, "selected_sample_file_path") or not self.selected_sample_file_path:
            self.lbl_analyzer_thumb.configure(image=None, text="")
            return

        file_path = self.selected_sample_file_path
        def load_analyzer_thumb(retries=3, delay_ms=150):
            try:
                with Image.open(file_path) as img:
                    img_copy = img.copy()
                    try:
                        thumb_size = int(self.var_ui_thumb_size.get())
                    except Exception:
                        thumb_size = 200
                    img_copy.thumbnail((thumb_size, thumb_size), Image.Resampling.LANCZOS)
                    ctk_img = ctk.CTkImage(light_image=img_copy, dark_image=img_copy, size=img_copy.size)
                    self.lbl_analyzer_thumb.configure(image=ctk_img, text="")
            except Exception:
                if retries > 0:
                    self.after(delay_ms, lambda: load_analyzer_thumb(retries - 1, delay_ms))
                else:
                    self.lbl_analyzer_thumb.configure(image=None, text="[Vorschau]")

        load_analyzer_thumb()

    def select_sample_image(self):
        file_path = filedialog.askopenfilename(
            filetypes=[("PNG files", "*.png")]
        )
        if not file_path:
            return

        self.selected_sample_file_path = file_path
        filename = os.path.basename(file_path)
        self.selected_sample_filename = filename
        self.lbl_sample_file.configure(
            text=Text.get("lbl_sample_file_val", filename=filename),
            text_color="#63e6be"
        )

        self._clear_analyzer_results()
        self._update_analyzer_thumbnail()

        from backend.comfy_parser import analyze_workflow_prompts
        candidates = analyze_workflow_prompts(file_path)

        if candidates is None or len(candidates) == 0:
            self.analyzer_state = "no_meta"
            self.lbl_analyzer_info.configure(
                text=Text.get("lbl_analyzer_no_meta"),
                text_color="#ff8787"
            )
            self.lbl_analyzer_thumb.configure(image=None, text="")
            return

        self.analyzer_state = "success"
        self.lbl_analyzer_info.configure(
            text=Text.get("lbl_analyzer_intro"),
            text_color="gray85"
        )

        prompt_keys = self.get_prompt_keys_list()

        for item in candidates:
            source = item["source"]
            node_id = item["node_id"]
            title = item["node_title"]
            ntype = item["node_type"]
            input_key = item["widget_or_input"]
            full_val = item["value"]

            # Card frame
            card = ctk.CTkFrame(self.analyzer_scroll, fg_color=self.get_theme_color("color_inner_frame_bg"), corner_radius=6)
            card.pack(fill="x", padx=10, pady=6)
            card.grid_columnconfigure(0, weight=1)
            card.grid_columnconfigure(1, weight=0)

            # Left Info Container
            info_frame = ctk.CTkFrame(card, fg_color="transparent")
            info_frame.grid(row=0, column=0, padx=12, pady=10, sticky="nsew")
            info_frame.grid_columnconfigure(0, weight=1)

            # Source & Node header
            header_text = f"⚙️ {Text.get('lbl_cand_source', source=source)}  |  🧩 {Text.get('lbl_cand_node', title=title, node_id=node_id)}"
            lbl_header = ctk.CTkLabel(info_frame, text=header_text, font=ctk.CTkFont(size=11, weight="bold"), text_color="#74c0fc", justify="left")
            lbl_header.grid(row=0, column=0, padx=0, pady=(0, 4), sticky="w")

            # Preview Text Box (selectable & scrollable)
            text_box = ctk.CTkTextbox(info_frame, height=55, font=ctk.CTkFont(family="Consolas", size=11), fg_color="#1a1b1e" if self.active_theme.lower() != "light" else "gray90")
            text_box.insert("1.0", full_val)
            text_box.configure(state="disabled")
            text_box.grid(row=1, column=0, padx=0, pady=(2, 0), sticky="ew")

            # Right Button Container
            btn_frame = ctk.CTkFrame(card, fg_color="transparent")
            btn_frame.grid(row=0, column=1, padx=(5, 12), pady=10, sticky="ns")

            # 1. Add Node ID Button
            is_added_id = node_id in prompt_keys
            btn_id = ctk.CTkButton(
                btn_frame,
                text=f"✓ ID '{node_id}'" if is_added_id else f"+ ID '{node_id}'",
                width=110,
                height=26,
                font=ctk.CTkFont(size=11),
                state="disabled" if is_added_id else "normal",
                fg_color="#2b8a3e" if is_added_id else self.get_theme_color("color_primary_btn"),
                hover_color=self.get_theme_color("color_primary_hover"),
                command=lambda k=node_id, b=None: self.add_custom_prompt_key(k, b)
            )
            btn_id.configure(command=lambda k=node_id, b=btn_id: self.add_custom_prompt_key(k, b))
            btn_id.pack(pady=2, fill="x")

            # 2. Add Input Key Button (if unique)
            if input_key and not input_key.startswith("widget_") and input_key.strip():
                is_added_key = input_key in prompt_keys
                btn_key = ctk.CTkButton(
                    btn_frame,
                    text=f"✓ Key '{input_key}'" if is_added_key else f"+ Key '{input_key}'",
                    width=110,
                    height=26,
                    font=ctk.CTkFont(size=11),
                    state="disabled" if is_added_key else "normal",
                    fg_color="#2b8a3e" if is_added_key else self.get_theme_color("color_secondary_btn"),
                    hover_color=self.get_theme_color("color_secondary_hover"),
                    command=lambda k=input_key, b=None: self.add_custom_prompt_key(k, b)
                )
                btn_key.configure(command=lambda k=input_key, b=btn_key: self.add_custom_prompt_key(k, b))
                btn_key.pack(pady=2, fill="x")

            # 3. Add Custom Name Button (if title is different from type)
            if title and ntype and title.strip().lower() != ntype.strip().lower():
                btn_title_text = title if len(title) <= 12 else title[:9] + "..."
                is_added_title = title in prompt_keys
                btn_title = ctk.CTkButton(
                    btn_frame,
                    text=f"✓ Name '{btn_title_text}'" if is_added_title else f"+ Name '{btn_title_text}'",
                    width=110,
                    height=26,
                    font=ctk.CTkFont(size=11),
                    state="disabled" if is_added_title else "normal",
                    fg_color="#2b8a3e" if is_added_title else "#37b24d",
                    hover_color="#2b8a3e" if is_added_title else "#2b8a3e",
                    command=lambda k=title, b=None: self.add_custom_prompt_key(k, b)
                )
                btn_title.configure(command=lambda k=title, b=btn_title: self.add_custom_prompt_key(k, b))
                btn_title.pack(pady=2, fill="x")

    def add_custom_prompt_key(self, key, button_widget=None):
        current_text = self.entry_prompt_keys.get("1.0", "end-1c").strip()
        keys = [k.strip() for k in current_text.split("\n") if k.strip()]
        if key in keys:
            if button_widget:
                current_text_val = button_widget.cget("text")
                if not current_text_val.startswith("✓"):
                    new_text = current_text_val.replace("+", "✓")
                    button_widget.configure(text=new_text)
                button_widget.configure(state="disabled", fg_color="#2b8a3e")
            else:
                messagebox.showinfo(
                    "Information",
                    Text.get("msg_key_already_exists", key=key)
                )
            return

        keys.append(key)
        self.entry_prompt_keys.delete("1.0", "end")
        self.entry_prompt_keys.insert("1.0", "\n".join(keys))
        self.on_setting_changed()

        if button_widget:
            current_text_val = button_widget.cget("text")
            new_text = current_text_val.replace("+", "✓")
            button_widget.configure(text=new_text, state="disabled", fg_color="#2b8a3e")
        else:
            messagebox.showinfo(
                "Success" if Text.get_lang() == "en" else "Erfolgreich",
                Text.get("msg_key_added", key=key)
            )

    def _build_tab_help(self):
        tab = self.tab_help
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)

        self.var_help_seg = tk.StringVar(value="getting_started")
        localized_values = [
            Text.get("help_seg_getting_started"),
            Text.get("help_seg_tagging_rules"),
            Text.get("help_seg_shortcuts"),
            Text.get("help_seg_about")
        ]
        self.help_seg = ctk.CTkSegmentedButton(
            tab,
            values=localized_values,
            variable=self.var_help_seg,
            command=self._on_help_seg_changed
        )
        self.help_seg.grid(row=0, column=0, padx=15, pady=(15, 10), sticky="ew")

        self.help_content_frame = ctk.CTkFrame(tab, fg_color="transparent")
        self.help_content_frame.grid(row=1, column=0, padx=15, pady=(0, 15), sticky="nsew")
        self.help_content_frame.grid_columnconfigure(0, weight=1)
        self.help_content_frame.grid_rowconfigure(0, weight=1)

        self._build_help_getting_started()
        self._build_help_tagging_rules()
        self._build_help_shortcuts()
        self._build_help_about()

        self._on_help_seg_changed(Text.get("help_seg_getting_started"))

    def _build_help_getting_started(self):
        frame = ctk.CTkScrollableFrame(self.help_content_frame, fg_color="transparent")
        self.help_frames["getting_started"] = frame
        frame.grid_columnconfigure(0, weight=1)

        steps = [
            ("help_gs_intro_title", "help_gs_intro_desc"),
            ("help_gs_step1_title", "help_gs_step1_desc"),
            ("help_gs_step2_title", "help_gs_step2_desc"),
            ("help_gs_step3_title", "help_gs_step3_desc"),
            ("help_gs_step4_title", "help_gs_step4_desc")
        ]

        for title_key, desc_key in steps:
            card = ctk.CTkFrame(frame, fg_color=self.get_theme_color("color_inner_frame_bg"), corner_radius=6)
            card.pack(fill="x", padx=10, pady=6)
            card.grid_columnconfigure(0, weight=1)

            title_color = "#63e6be" if title_key == "help_gs_intro_title" else "#74c0fc"

            lbl_title = ctk.CTkLabel(
                card,
                text=Text.get(title_key),
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color=title_color,
                justify="left"
            )
            lbl_title.grid(row=0, column=0, padx=15, pady=(10, 2), sticky="w")
            self.register_widget(lbl_title, title_key)

            lbl_desc = ctk.CTkLabel(
                card,
                text=Text.get(desc_key),
                font=ctk.CTkFont(size=12),
                text_color="gray85",
                justify="left",
                wraplength=650
            )
            lbl_desc.grid(row=1, column=0, padx=15, pady=(0, 10), sticky="w")
            self.register_widget(lbl_desc, desc_key)

    def _build_help_tagging_rules(self):
        frame = ctk.CTkScrollableFrame(self.help_content_frame, fg_color="transparent")
        self.help_frames["tagging_rules"] = frame
        frame.grid_columnconfigure(0, weight=1)

        rules = [
            ("help_tr_std_title", "help_tr_std_desc"),
            ("help_tr_word_title", "help_tr_word_desc"),
            ("help_tr_list_title", "help_tr_list_desc"),
            ("help_tr_meta_title", "help_tr_meta_desc")
        ]

        for title_key, desc_key in rules:
            card = ctk.CTkFrame(frame, fg_color=self.get_theme_color("color_inner_frame_bg"), corner_radius=6)
            card.pack(fill="x", padx=10, pady=6)
            card.grid_columnconfigure(0, weight=1)

            lbl_title = ctk.CTkLabel(
                card,
                text=Text.get(title_key),
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color="#74c0fc",
                justify="left"
            )
            lbl_title.grid(row=0, column=0, padx=15, pady=(10, 2), sticky="w")
            self.register_widget(lbl_title, title_key)

            lbl_desc = ctk.CTkLabel(
                card,
                text=Text.get(desc_key),
                font=ctk.CTkFont(size=12),
                text_color="gray85",
                justify="left",
                wraplength=650
            )
            lbl_desc.grid(row=1, column=0, padx=15, pady=(0, 10), sticky="w")
            self.register_widget(lbl_desc, desc_key)

    def _build_help_shortcuts(self):
        frame = ctk.CTkScrollableFrame(self.help_content_frame, fg_color="transparent")
        self.help_frames["shortcuts"] = frame
        frame.grid_columnconfigure(0, weight=1)

        shortcuts = [
            ("help_sc_del_title", "help_sc_del_desc"),
            ("help_sc_nav_title", "help_sc_nav_desc"),
            ("help_sc_space_title", "help_sc_space_desc"),
            ("help_sc_f5_title", "help_sc_f5_desc")
        ]

        for title_key, desc_key in shortcuts:
            card = ctk.CTkFrame(frame, fg_color=self.get_theme_color("color_inner_frame_bg"), corner_radius=6)
            card.pack(fill="x", padx=10, pady=5)
            card.grid_columnconfigure(0, weight=0)
            card.grid_columnconfigure(1, weight=1)

            lbl_key = ctk.CTkLabel(
                card,
                text=Text.get(title_key),
                font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
                text_color="#ff922b",
                fg_color="#2b2d31" if self.active_theme.lower() != "light" else "gray80",
                corner_radius=4,
                width=180,
                height=26
            )
            lbl_key.grid(row=0, column=0, padx=12, pady=10, sticky="w")
            self.register_widget(lbl_key, title_key)

            lbl_desc = ctk.CTkLabel(
                card,
                text=Text.get(desc_key),
                font=ctk.CTkFont(size=12),
                text_color="gray85",
                justify="left",
                wraplength=480
            )
            lbl_desc.grid(row=0, column=1, padx=(5, 12), pady=10, sticky="w")
            self.register_widget(lbl_desc, desc_key)

    def _build_help_about(self):
        frame = ctk.CTkFrame(self.help_content_frame, fg_color="transparent")
        self.help_frames["about"] = frame
        frame.grid_columnconfigure(0, weight=1)

        card = ctk.CTkFrame(frame, fg_color=self.get_theme_color("color_inner_frame_bg"), corner_radius=6)
        card.pack(fill="x", padx=10, pady=10)
        card.grid_columnconfigure(0, weight=1)

        lbl_app = ctk.CTkLabel(
            card,
            text=Text.get("help_about_title"),
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#63e6be"
        )
        lbl_app.grid(row=0, column=0, padx=20, pady=(15, 2), sticky="w")
        self.register_widget(lbl_app, "help_about_title")

        lbl_ver = ctk.CTkLabel(
            card,
            text=Text.get("help_about_version"),
            font=ctk.CTkFont(size=12, slant="italic"),
            text_color="gray75"
        )
        lbl_ver.grid(row=1, column=0, padx=20, pady=(0, 10), sticky="w")
        self.register_widget(lbl_ver, "help_about_version")

        lbl_desc = ctk.CTkLabel(
            card,
            text=Text.get("help_about_desc"),
            font=ctk.CTkFont(size=12),
            text_color="gray85",
            justify="left",
            wraplength=650
        )
        lbl_desc.grid(row=2, column=0, padx=20, pady=(0, 10), sticky="w")
        self.register_widget(lbl_desc, "help_about_desc")

        lbl_github_title = ctk.CTkLabel(
            card,
            text=Text.get("help_about_github"),
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="gray85"
        )
        lbl_github_title.grid(row=3, column=0, padx=20, pady=(0, 2), sticky="w")
        self.register_widget(lbl_github_title, "help_about_github")

        lbl_github_link = ctk.CTkLabel(
            card,
            text="https://github.com/bitcrusher-design/comfyui-xmp-tagger",
            font=ctk.CTkFont(size=12, underline=True),
            text_color=self.get_theme_color("color_info_link"),
            cursor="hand2"
        )
        lbl_github_link.grid(row=4, column=0, padx=20, pady=(0, 20), sticky="w")

        def open_github(event):
            import webbrowser
            webbrowser.open_new_tab("https://github.com/bitcrusher-design/comfyui-xmp-tagger")

        lbl_github_link.bind("<Button-1>", open_github)

        self.btn_help_changelog = ctk.CTkButton(
            frame,
            text=Text.get("help_btn_changelog"),
            command=self.open_changelog_viewer,
            fg_color=self.get_theme_color("color_primary_btn"),
            hover_color=self.get_theme_color("color_primary_hover")
        )
        self.btn_help_changelog.pack(padx=10, pady=10, anchor="w")
        self.register_widget(self.btn_help_changelog, "help_btn_changelog")

    def open_changelog_viewer(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title(Text.get("help_title_changelog"))
        dialog.geometry("750x600")
        dialog.transient(self)
        dialog.focus()
        
        dialog.grid_columnconfigure(0, weight=1)
        dialog.grid_rowconfigure(0, weight=1)
        dialog.grid_rowconfigure(1, weight=0)

        changelog_content = ""
        changelog_path = "CHANGELOG.md"
        if os.path.exists(changelog_path):
            try:
                with open(changelog_path, "r", encoding="utf-8", errors="ignore") as f:
                    changelog_content = f.read()
            except Exception:
                changelog_content = "Could not load CHANGELOG.md."
        else:
            changelog_content = "CHANGELOG.md file not found."

        tb = ctk.CTkTextbox(
            dialog,
            font=ctk.CTkFont(family="Consolas", size=11),
            wrap="word",
            fg_color="#1a1b1e" if self.active_theme.lower() != "light" else "gray90"
        )
        tb.grid(row=0, column=0, padx=15, pady=15, sticky="nsew")
        tb.insert("1.0", changelog_content)
        tb.configure(state="disabled")

        btn_close = ctk.CTkButton(
            dialog,
            text=Text.get("btn_close") if Text.get("btn_close") != "btn_close" else "Close",
            command=dialog.destroy
        )
        btn_close.grid(row=1, column=0, padx=15, pady=(0, 15))

    def _on_help_seg_changed(self, value):
        from backend.localization import LOCALIZATION
        key = "getting_started"
        if value == LOCALIZATION["en"].get("help_seg_tagging_rules") or value == LOCALIZATION["de"].get("help_seg_tagging_rules") or value == "tagging_rules":
            key = "tagging_rules"
        elif value == LOCALIZATION["en"].get("help_seg_shortcuts") or value == LOCALIZATION["de"].get("help_seg_shortcuts") or value == "shortcuts":
            key = "shortcuts"
        elif value == LOCALIZATION["en"].get("help_seg_about") or value == LOCALIZATION["de"].get("help_seg_about") or value == "about":
            key = "about"
        elif value == LOCALIZATION["en"].get("help_seg_getting_started") or value == LOCALIZATION["de"].get("help_seg_getting_started") or value == "getting_started":
            key = "getting_started"
        else:
            key = value

        for f in self.help_frames.values():
            f.grid_remove()

        if key in self.help_frames:
            self.help_frames[key].grid(row=0, column=0, sticky="nsew")

    def _build_tab_layout(self):
        tab = self.tab_layout
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)

        scroll_container = ctk.CTkScrollableFrame(tab)
        scroll_container.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        scroll_container.grid_columnconfigure(0, weight=1)

        # Helper to create styled headers with info tooltip buttons
        def create_section_header(parent, title_key, tooltip_key, col_span=3):
            h_frame = ctk.CTkFrame(parent, fg_color="transparent")
            h_frame.grid(row=0, column=0, columnspan=col_span, padx=15, pady=(12, 8), sticky="w")
            lbl = ctk.CTkLabel(h_frame, text=Text.get(title_key), font=ctk.CTkFont(size=15, weight="bold"))
            lbl.pack(side="left")
            self.register_widget(lbl, title_key)
            help_lbl = ctk.CTkLabel(h_frame, text=" 🛈", font=ctk.CTkFont(size=22, weight="bold"), text_color=self.get_theme_color("color_info_link"), cursor="hand2")
            help_lbl.pack(side="left", padx=5)
            self.help_labels.append(help_lbl)
            ToolTip(help_lbl, lambda: Text.get(tooltip_key))
            return h_frame

        # Section 1: Language Settings
        sec_lang = ctk.CTkFrame(scroll_container)
        sec_lang.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        sec_lang.grid_columnconfigure(1, weight=1)

        create_section_header(
            sec_lang,
            "lbl_sec_language",
            "lbl_sec_language_tooltip",
            col_span=2
        )

        # Language Selector
        self.lbl_ui_language = ctk.CTkLabel(sec_lang, text=Text.get("lbl_ui_language"))
        self.lbl_ui_language.grid(row=1, column=0, padx=15, pady=(8, 15), sticky="w")
        self.register_widget(self.lbl_ui_language, "lbl_ui_language")
        
        self.var_ui_lang = tk.StringVar(value="de")
        self.option_language = ctk.CTkOptionMenu(
            sec_lang,
            values=["de", "en"],
            variable=self.var_ui_lang,
            width=80,
            command=self._on_language_changed
        )
        self.option_language.grid(row=1, column=1, padx=15, pady=(8, 15), sticky="w")

        # Section 2: Dateiliste & Ansicht (File list & view)
        sec_list = ctk.CTkFrame(scroll_container)
        sec_list.grid(row=1, column=0, padx=10, pady=10, sticky="ew")
        sec_list.grid_columnconfigure(1, weight=1)

        create_section_header(
            sec_list,
            "lbl_sec_layout_list",
            "lbl_sec_layout_list_tooltip",
            col_span=2
        )

        self.var_ui_show_details = tk.BooleanVar(value=True)
        self.chk_ui_show_details = ctk.CTkCheckBox(
            sec_list,
            text=Text.get("chk_ui_show_details"),
            variable=self.var_ui_show_details,
            command=self._on_show_details_changed
        )
        self.chk_ui_show_details.grid(row=1, column=0, columnspan=2, padx=15, pady=(8, 4), sticky="w")
        self.register_widget(self.chk_ui_show_details, "chk_ui_show_details")

        # Container for Details items ordering and visibility config
        self.frame_details_config = ctk.CTkFrame(sec_list, fg_color="transparent")
        self.frame_details_config.grid(row=2, column=0, columnspan=2, padx=35, pady=(0, 8), sticky="w")
        self._refresh_details_config_ui()

        self.var_ui_show_listbox_warnings = tk.BooleanVar(value=True)
        self.chk_ui_show_listbox_warnings = ctk.CTkCheckBox(
            sec_list,
            text=Text.get("chk_ui_show_listbox_warnings"),
            variable=self.var_ui_show_listbox_warnings,
            command=self._on_show_warnings_changed
        )
        self.chk_ui_show_listbox_warnings.grid(row=3, column=0, columnspan=2, padx=15, pady=8, sticky="w")
        self.register_widget(self.chk_ui_show_listbox_warnings, "chk_ui_show_listbox_warnings")

        # Section 3: XMP Preview
        sec_preview = ctk.CTkFrame(scroll_container)
        sec_preview.grid(row=2, column=0, padx=10, pady=10, sticky="ew")
        sec_preview.grid_columnconfigure(1, weight=1)

        create_section_header(
            sec_preview,
            "lbl_sec_layout_preview",
            "lbl_sec_layout_preview_tooltip",
            col_span=2
        )

        self.var_ui_preview_extra_meta = tk.BooleanVar(value=True)
        self.chk_ui_preview_extra_meta = ctk.CTkCheckBox(
            sec_preview,
            text=Text.get("chk_ui_preview_extra_meta"),
            variable=self.var_ui_preview_extra_meta,
            command=self.on_setting_changed
        )
        self.chk_ui_preview_extra_meta.grid(row=1, column=0, columnspan=2, padx=15, pady=8, sticky="w")
        self.register_widget(self.chk_ui_preview_extra_meta, "chk_ui_preview_extra_meta")

        # Section 4: Appearance
        sec_appearance = ctk.CTkFrame(scroll_container)
        sec_appearance.grid(row=3, column=0, padx=10, pady=10, sticky="ew")
        sec_appearance.grid_columnconfigure(1, weight=1)

        create_section_header(
            sec_appearance,
            "lbl_sec_layout_appearance",
            "lbl_sec_layout_appearance_tooltip",
            col_span=2
        )

        self.lbl_ui_text_size = ctk.CTkLabel(sec_appearance, text=Text.get("lbl_ui_text_size"))
        self.lbl_ui_text_size.grid(row=1, column=0, padx=15, pady=(8, 15), sticky="w")
        self.register_widget(self.lbl_ui_text_size, "lbl_ui_text_size")
        
        self.var_ui_font_size = tk.StringVar(value="11")
        self.option_font_size = ctk.CTkOptionMenu(
            sec_appearance,
            values=["8", "9", "10", "11", "12", "13", "14", "15", "16"],
            variable=self.var_ui_font_size,
            width=80,
            command=lambda val: self.on_setting_changed()
        )
        self.option_font_size.grid(row=1, column=1, padx=15, pady=(8, 15), sticky="w")

        # XMP Preview Font Size
        self.lbl_ui_preview_text_size = ctk.CTkLabel(sec_appearance, text=Text.get("lbl_ui_preview_text_size"))
        self.lbl_ui_preview_text_size.grid(row=2, column=0, padx=15, pady=(8, 15), sticky="w")
        self.register_widget(self.lbl_ui_preview_text_size, "lbl_ui_preview_text_size")
        
        self.var_ui_preview_font_size = tk.StringVar(value="12")
        self.option_preview_font_size = ctk.CTkOptionMenu(
            sec_appearance,
            values=["8", "9", "10", "11", "12", "13", "14", "15", "16"],
            variable=self.var_ui_preview_font_size,
            width=80,
            command=lambda val: self.on_setting_changed()
        )
        self.option_preview_font_size.grid(row=2, column=1, padx=15, pady=(8, 15), sticky="w")

        # Thumbnail Size dropdown
        self.lbl_ui_thumb_size = ctk.CTkLabel(sec_appearance, text=Text.get("lbl_ui_thumb_size"))
        self.lbl_ui_thumb_size.grid(row=3, column=0, padx=15, pady=(8, 15), sticky="w")
        self.register_widget(self.lbl_ui_thumb_size, "lbl_ui_thumb_size")

        self.option_thumb_size = ctk.CTkOptionMenu(
            sec_appearance,
            values=["Mittel (200x200)"],
            width=150,
            command=self._on_thumb_size_changed
        )
        self.option_thumb_size.grid(row=3, column=1, padx=15, pady=(8, 15), sticky="w")
        self._update_thumb_option_menu_selection()

        # Theme Selector
        self.lbl_ui_theme = ctk.CTkLabel(sec_appearance, text=Text.get("lbl_active_theme"))
        self.lbl_ui_theme.grid(row=4, column=0, padx=15, pady=(8, 15), sticky="w")
        self.register_widget(self.lbl_ui_theme, "lbl_active_theme")

        self.option_theme = ctk.CTkOptionMenu(
            sec_appearance,
            values=ThemeManager.get_theme_names(),
            width=150,
            command=self._on_theme_changed
        )
        self.option_theme.grid(row=4, column=1, padx=15, pady=(8, 15), sticky="w")
        self.option_theme.set(self.active_theme)

        # Theme Customize Button
        self.btn_customize_theme = ctk.CTkButton(
            sec_appearance,
            text=Text.get("btn_customize_theme"),
            fg_color=self.get_theme_color("color_neutral_btn"),
            hover_color=self.get_theme_color("color_neutral_hover"),
            command=self.open_theme_editor
        )
        self.btn_customize_theme.grid(row=5, column=0, columnspan=2, padx=15, pady=(8, 15), sticky="w")
        self.register_widget(self.btn_customize_theme, "btn_customize_theme")

    # -----------------------------------------------------------------
    # Settings & Preset Management Handlers
    # -----------------------------------------------------------------
    def _on_theme_changed(self, value):
        self.active_theme = value
        self.theme_colors = dict(ThemeManager.get_theme_colors(value))
        self.apply_theme()
        self.on_setting_changed()

    def open_theme_editor(self):
        ThemeEditorDialog(self)

    def _update_theme_menu(self, select_name=None):
        themes = ThemeManager.get_theme_names()
        if hasattr(self, "option_theme"):
            self.option_theme.configure(values=themes)
            if select_name:
                self.option_theme.set(select_name)
                self.active_theme = select_name
                self.theme_colors = dict(ThemeManager.get_theme_colors(select_name))
                self.apply_theme()
                self.on_setting_changed()

    def apply_theme(self):
        # 1. Update specific widgets
        if hasattr(self, "btn_browse"):
            self.btn_browse.configure(
                fg_color=self.get_theme_color("color_neutral_btn"),
                hover_color=self.get_theme_color("color_neutral_hover")
            )
        if hasattr(self, "btn_scan"):
            self.btn_scan.configure(
                fg_color=self.get_theme_color("color_primary_btn"),
                hover_color=self.get_theme_color("color_primary_hover")
            )
        if hasattr(self, "file_listbox"):
            self.file_listbox.configure(fg_color=self.get_theme_color("color_inner_frame_bg"))
            tb = self.file_listbox._textbox
            tb.tag_config("checked_box", foreground=self.get_theme_color("color_tag_new"))
            tb.tag_config("unchecked_box", foreground=self.get_theme_color("color_tag_existing"))
            tb.tag_config("xmp_prefix", foreground=self.get_theme_color("color_tag_xmp_prefix"))
            tb.tag_config("listbox_details", foreground=self.get_theme_color("color_listbox_details"))
            tb.tag_config("selected_line", background=self.get_theme_color("color_listbox_selected_bg"))
            tb.tag_raise("selected_line")
            
        if hasattr(self, "top_info_container"):
            self.top_info_container.configure(fg_color=self.get_theme_color("color_inner_frame_bg"))
            
        if hasattr(self, "lbl_info_resolution"):
            self.lbl_info_resolution.configure(text_color=self.get_theme_color("color_tag_new"))
            
        if hasattr(self, "lbl_info_date"):
            self.lbl_info_date.configure(text_color=self.get_theme_color("color_info_date"))
            
        if hasattr(self, "tag_preview_box"):
            self.tag_preview_box.configure(fg_color=self.get_theme_color("color_inner_frame_bg"))
            tb = self.tag_preview_box._textbox
            tb.tag_config("deleted", foreground=self.get_theme_color("color_tag_deleted"))
            tb.tag_config("new", foreground=self.get_theme_color("color_tag_new"))
            tb.tag_config("existing", foreground=self.get_theme_color("color_tag_existing"))
            tb.tag_config("warning", foreground=self.get_theme_color("color_tag_warning"))
            tb.tag_config("low_warning", foreground=self.get_theme_color("color_tag_low_warning"))
            tb.tag_config("prompt_body", foreground=self.get_theme_color("color_textbox_prompt_body"))
            tb.tag_config("extra_meta", foreground=self.get_theme_color("color_tag_extra_meta"))
            
        if hasattr(self, "sec_preset"):
            self.sec_preset.configure(fg_color=self.get_theme_color("color_inner_frame_bg"))
            
        # Update preset frame buttons
        if hasattr(self, "btn_load_p"):
            self.btn_load_p.configure(
                fg_color=self.get_theme_color("color_primary_btn"),
                hover_color=self.get_theme_color("color_primary_hover")
            )
        if hasattr(self, "btn_quick_save_p"):
            self.btn_quick_save_p.configure(
                fg_color=self.get_theme_color("color_secondary_btn"),
                hover_color=self.get_theme_color("color_secondary_hover")
            )
        if hasattr(self, "btn_save_def"):
            self.btn_save_def.configure(
                fg_color=self.get_theme_color("color_warning_btn"),
                hover_color=self.get_theme_color("color_warning_hover")
            )
        if hasattr(self, "btn_del_p"):
            self.btn_del_p.configure(
                fg_color=self.get_theme_color("color_danger_btn"),
                hover_color=self.get_theme_color("color_danger_hover")
            )
        if hasattr(self, "progress_bar"):
            self.progress_bar.configure(progress_color=self.get_theme_color("color_progress_bar"))
            
        # Update process buttons
        self.update_process_button_text()
        
        # Update help link text colors
        if hasattr(self, "help_labels"):
            for lbl in self.help_labels:
                lbl.configure(text_color=self.get_theme_color("color_info_link"))

        if hasattr(self, "lbl_edit_stopwords"):
            self.lbl_edit_stopwords.configure(text_color=self.get_theme_color("color_info_link"))
        if hasattr(self, "lbl_edit_adjectives"):
            self.lbl_edit_adjectives.configure(text_color=self.get_theme_color("color_info_link"))
        if hasattr(self, "lbl_edit_short_words"):
            self.lbl_edit_short_words.configure(text_color=self.get_theme_color("color_info_link"))
        if hasattr(self, "lbl_edit_whitelist"):
            self.lbl_edit_whitelist.configure(text_color=self.get_theme_color("color_info_link"))
        if hasattr(self, "lbl_edit_blacklist"):
            self.lbl_edit_blacklist.configure(text_color=self.get_theme_color("color_info_link"))
            
        if hasattr(self, "btn_customize_theme"):
            self.btn_customize_theme.configure(
                fg_color=self.get_theme_color("color_neutral_btn"),
                hover_color=self.get_theme_color("color_neutral_hover")
            )

        # Update general text color of labels, check boxes, and radio buttons
        if hasattr(self, "translatable_widgets"):
            for widget, _, _ in self.translatable_widgets:
                if isinstance(widget, (ctk.CTkLabel, ctk.CTkCheckBox, ctk.CTkRadioButton)):
                    # Skip resolution label and help links which have their own color
                    if widget in [
                        getattr(self, "lbl_info_resolution", None),
                        getattr(self, "lbl_info_date", None),
                        getattr(self, "lbl_edit_stopwords", None),
                        getattr(self, "lbl_edit_adjectives", None),
                        getattr(self, "lbl_edit_short_words", None),
                        getattr(self, "lbl_edit_whitelist", None),
                        getattr(self, "lbl_edit_blacklist", None)
                    ]:
                        continue
                    # Skip info help labels
                    if hasattr(self, "help_labels") and widget in self.help_labels:
                        continue
                    try:
                        widget.configure(text_color=self.get_theme_color("color_label_text"))
                    except Exception:
                        pass
                        
        # Dynamic label text color updates for other info labels
        for lbl_name in ["lbl_info_filename", "lbl_info_models", "lbl_info_loras", "lbl_info_sampler", "lbl_status", "lbl_scan_summary", "lbl_preview_title"]:
            if hasattr(self, lbl_name):
                try:
                    getattr(self, lbl_name).configure(text_color=self.get_theme_color("color_label_text"))
                except Exception:
                    pass
        if hasattr(self, "lbl_scan_summary_warn") and self.lbl_scan_summary_warn:
            try:
                self.lbl_scan_summary_warn.configure(text_color=self.get_theme_color("color_tag_warning"))
            except Exception:
                pass

        # Re-render file list and previews to show new colors immediately
        if self.scanned_files:
            self._render_file_listbox()
            self._update_highlight_and_preview(self.current_selected_idx)



    def _on_reset_checkbox_toggled(self):
        """Dynamic styling for process button when Reset checkbox is toggled."""
        if self.var_reset_tags.get():
            self.btn_process.configure(
                fg_color=self.get_theme_color("color_danger_btn"),
                hover_color=self.get_theme_color("color_danger_hover")
            )
        else:
            self.btn_process.configure(
                fg_color=self.get_theme_color("color_primary_btn"),
                hover_color=self.get_theme_color("color_primary_hover")
            )
        self.update_process_button_text()
        if self.scanned_files:
            self._update_highlight_and_preview(self.current_selected_idx)

    def _export_ui_to_dict(self) -> dict:
        """Collects all UI settings into a dictionary."""
        is_max = False
        try:
            is_max = (self.state() == "zoomed")
        except Exception:
            pass

        from backend.settings_manager import load_settings
        try:
            prev_settings = load_settings()
        except Exception:
            prev_settings = {}

        if not is_max and self.winfo_width() > 200 and self.winfo_height() > 200:
            w = self.winfo_width()
            h = self.winfo_height()
            x = self.winfo_x()
            y = self.winfo_y()
        else:
            w = prev_settings.get("window_width", 1200)
            h = prev_settings.get("window_height", 880)
            x = prev_settings.get("window_x", 100)
            y = prev_settings.get("window_y", 100)

        ratio = 0.45
        try:
            total_w = self.paned_window.winfo_width()
            if total_w > 100:
                sash_x = self.paned_window.sash_coord(0)[0]
                ratio = round(sash_x / float(total_w), 3)
        except Exception:
            pass

        t1_mp = 1.0
        t2_mp = 2.5
        try: t1_mp = float(self.entry_res_t1_mp.get().strip())
        except Exception: pass
        try: t2_mp = float(self.entry_res_t2_mp.get().strip())
        except Exception: pass

        return {
            "include_models": self.var_models.get(),
            "include_loras": self.var_loras.get(),
            "include_samplers": self.var_samplers.get(),
            "include_prompts": self.var_prompts.get(),
            "include_resolution": self.var_include_resolution.get(),
            "prefix_resolution": self.entry_prefix_resolution.get(),
            "res_tier1_mp": t1_mp,
            "res_tier1_name": self.entry_res_t1_name.get(),
            "res_tier2_mp": t2_mp,
            "res_tier2_name": self.entry_res_t2_name.get(),
            "res_tier3_name": self.entry_res_t3_name.get(),
            "write_flat_dc": self.var_write_flat.get(),
            "ignore_inactive_nodes": self.var_ignore_inactive.get(),
            "ignore_numeric_tags": self.var_ignore_numeric.get(),
            "max_tag_length": self.get_max_tag_length(),
            "recursive_scan": self.var_recursive_scan.get(),
            "splitter_ratio": ratio,
            "min_lora_strength": self.get_min_strength(),
            "use_whitelist": self.var_use_whitelist.get(),
            "whitelist_tags": self.entry_whitelist.get(),
            "blacklist_tags": self.entry_blacklist.get(),
            "prompt_keys": self.entry_prompt_keys.get("1.0", "end").strip(),
            "prefix_model": self.entry_prefix_model.get(),
            "prefix_lora": self.entry_prefix_lora.get(),
            "prefix_prompt": self.entry_prefix_prompt.get(),
            "prefix_sampler": self.entry_prefix_sampler.get(),
            "storage_mode": self.var_mode.get(),
            "active_preset": self.option_preset.get(),
            "overwrite_existing_tags": self.var_overwrite_tags.get(),
            "ui_show_details": self.var_ui_show_details.get(),
            "ui_font_size": self.var_ui_font_size.get(),
            "ui_preview_font_size": self.var_ui_preview_font_size.get(),
            "ui_preview_extra_meta": self.var_ui_preview_extra_meta.get(),
            "ui_show_listbox_warnings": self.var_ui_show_listbox_warnings.get(),
            "ui_show_tagging_confirm": self.var_ui_show_tagging_confirm.get(),
            "ui_thumb_size": self.var_ui_thumb_size.get(),
            "ui_details_order": [item["key"] for item in self.detail_items],
            "ui_details_visible": [item["key"] for item in self.detail_items if item["visible"]],
            "word_based_tagging": self.var_word_based_tagging.get(),
            "lowercase_prompt_tags": self.var_lowercase_prompt_tags.get(),
            "write_created_date": self.var_write_created_date.get(),
            "write_camera_model": self.var_write_camera_model.get(),
            "write_description": self.var_write_description.get(),
            "custom_creator": self.var_custom_creator.get().strip(),
            "custom_copyright": self.var_custom_copyright.get().strip(),
            "custom_camera_make": self.var_custom_camera_make.get().strip(),
            "custom_software": self.var_custom_software.get().strip(),
            "custom_comment": self.var_custom_comment.get().strip(),
            "window_width": w,
            "window_height": h,
            "window_x": x,
            "window_y": y,
            "window_maximized": is_max,
            "language": self.var_ui_lang.get(),
            "active_theme": self.active_theme
        }

    def _apply_dict_to_ui(self, d: dict):
        """Applies a settings dictionary to UI widgets."""
        if "include_models" in d: self.var_models.set(bool(d["include_models"]))
        if "include_loras" in d: self.var_loras.set(bool(d["include_loras"]))
        if "include_samplers" in d: self.var_samplers.set(bool(d["include_samplers"]))
        if "include_prompts" in d: self.var_prompts.set(bool(d["include_prompts"]))
        if "include_resolution" in d: self.var_include_resolution.set(bool(d["include_resolution"]))
        if "write_flat_dc" in d: self.var_write_flat.set(bool(d["write_flat_dc"]))
        if "ignore_inactive_nodes" in d: self.var_ignore_inactive.set(bool(d["ignore_inactive_nodes"]))
        if "ignore_numeric_tags" in d: self.var_ignore_numeric.set(bool(d["ignore_numeric_tags"]))
        if "recursive_scan" in d: self.var_recursive_scan.set(bool(d["recursive_scan"]))
        if "use_whitelist" in d: self.var_use_whitelist.set(bool(d["use_whitelist"]))
        if "overwrite_existing_tags" in d: self.var_overwrite_tags.set(bool(d["overwrite_existing_tags"]))
        if "word_based_tagging" in d: self.var_word_based_tagging.set(bool(d["word_based_tagging"]))
        if "lowercase_prompt_tags" in d: self.var_lowercase_prompt_tags.set(bool(d["lowercase_prompt_tags"]))
        if "write_created_date" in d: self.var_write_created_date.set(bool(d["write_created_date"]))
        if "write_camera_model" in d: self.var_write_camera_model.set(bool(d["write_camera_model"]))
        if "write_description" in d: self.var_write_description.set(bool(d["write_description"]))
        if "custom_creator" in d: self.var_custom_creator.set(str(d["custom_creator"]))
        if "custom_copyright" in d: self.var_custom_copyright.set(str(d["custom_copyright"]))
        if "custom_camera_make" in d: self.var_custom_camera_make.set(str(d["custom_camera_make"]))
        if "custom_software" in d: self.var_custom_software.set(str(d["custom_software"]))
        if "custom_comment" in d: self.var_custom_comment.set(str(d["custom_comment"]))
        if "ui_details_order" in d and "ui_details_visible" in d:
            order = d["ui_details_order"]
            visible = d["ui_details_visible"]
            new_items = []
            for key in order:
                label_key = "listbox_model_title"
                if key == "lora": label_key = "listbox_loras_title"
                elif key == "resolution": label_key = "listbox_resolution_title"
                elif key == "date": label_key = "listbox_date_title"
                new_items.append({
                    "key": key,
                    "label_key": label_key,
                    "visible": key in visible
                })
            self.detail_items = new_items
            if hasattr(self, "frame_details_config"):
                self._refresh_details_config_ui()
        if "ui_show_listbox_warnings" in d:
            self.var_ui_show_listbox_warnings.set(bool(d["ui_show_listbox_warnings"]))
        if "ui_show_tagging_confirm" in d:
            self.var_ui_show_tagging_confirm.set(bool(d["ui_show_tagging_confirm"]))
        if "ui_thumb_size" in d:
            self.var_ui_thumb_size.set(str(d["ui_thumb_size"]))
            self._update_thumb_option_menu_selection()
            try:
                size_val = int(self.var_ui_thumb_size.get())
                if hasattr(self, "lbl_thumb"):
                    self.lbl_thumb.configure(width=size_val, height=size_val)
            except Exception:
                pass

        if "prefix_resolution" in d:
            self.entry_prefix_resolution.delete(0, tk.END)
            self.entry_prefix_resolution.insert(0, str(d["prefix_resolution"]))

        if "res_tier1_mp" in d:
            self.entry_res_t1_mp.delete(0, tk.END)
            self.entry_res_t1_mp.insert(0, str(d["res_tier1_mp"]))

        if "res_tier1_name" in d:
            self.entry_res_t1_name.delete(0, tk.END)
            self.entry_res_t1_name.insert(0, str(d["res_tier1_name"]))

        if "res_tier2_mp" in d:
            self.entry_res_t2_mp.delete(0, tk.END)
            self.entry_res_t2_mp.insert(0, str(d["res_tier2_mp"]))

        if "res_tier2_name" in d:
            self.entry_res_t2_name.delete(0, tk.END)
            self.entry_res_t2_name.insert(0, str(d["res_tier2_name"]))

        if "res_tier3_name" in d:
            self.entry_res_t3_name.delete(0, tk.END)
            self.entry_res_t3_name.insert(0, str(d["res_tier3_name"]))

        if "min_lora_strength" in d:
            self.entry_min_strength.delete(0, tk.END)
            self.entry_min_strength.insert(0, str(d["min_lora_strength"]))

        if "max_tag_length" in d:
            self.entry_max_tag_length.delete(0, tk.END)
            self.entry_max_tag_length.insert(0, str(d["max_tag_length"]))

        if "whitelist_tags" in d:
            self.entry_whitelist.delete(0, tk.END)
            self.entry_whitelist.insert(0, str(d["whitelist_tags"]))

        if "blacklist_tags" in d:
            self.entry_blacklist.delete(0, tk.END)
            self.entry_blacklist.insert(0, str(d["blacklist_tags"]))

        if "prompt_keys" in d:
            self.entry_prompt_keys.delete("1.0", tk.END)
            val = str(d["prompt_keys"])
            if "," in val and "\n" not in val:
                val = "\n".join([k.strip() for k in val.split(",") if k.strip()])
            self.entry_prompt_keys.insert("1.0", val)

        if "prefix_model" in d:
            self.entry_prefix_model.delete(0, tk.END)
            self.entry_prefix_model.insert(0, str(d["prefix_model"]))

        if "prefix_lora" in d:
            self.entry_prefix_lora.delete(0, tk.END)
            self.entry_prefix_lora.insert(0, str(d["prefix_lora"]))

        if "prefix_prompt" in d:
            self.entry_prefix_prompt.delete(0, tk.END)
            self.entry_prefix_prompt.insert(0, str(d["prefix_prompt"]))

        if "prefix_sampler" in d:
            self.entry_prefix_sampler.delete(0, tk.END)
            self.entry_prefix_sampler.insert(0, str(d["prefix_sampler"]))

        if "storage_mode" in d:
            self.var_mode.set(str(d["storage_mode"]))

        if "ui_show_details" in d:
            self.var_ui_show_details.set(bool(d["ui_show_details"]))

        if "ui_preview_extra_meta" in d:
            self.var_ui_preview_extra_meta.set(bool(d["ui_preview_extra_meta"]))

        if "ui_font_size" in d:
            self.var_ui_font_size.set(str(d["ui_font_size"]))

        if "ui_preview_font_size" in d:
            self.var_ui_preview_font_size.set(str(d["ui_preview_font_size"]))
            if hasattr(self, "option_preview_font_size"):
                self.option_preview_font_size.set(str(d["ui_preview_font_size"]))

        if "splitter_ratio" in d:
            ratio = float(d["splitter_ratio"])
            self.update_idletasks()
            self._apply_splitter_ratio(ratio)
            self.after(150, lambda r=ratio: self._apply_splitter_ratio(r))

        if "language" in d:
            lang = str(d["language"])
            self.var_ui_lang.set(lang)
            Text.set_lang(lang)
            self.retranslate_ui()

        if "active_theme" in d:
            self.active_theme = str(d["active_theme"])
            self.theme_colors = dict(ThemeManager.get_theme_colors(self.active_theme))
            if hasattr(self, "option_theme"):
                self.option_theme.set(self.active_theme)
            self.apply_theme()

        self.on_setting_changed()

    def _apply_splitter_ratio(self, ratio: float):
        try:
            total_w = self.paned_window.winfo_width()
            if total_w > 100:
                sash_x = int(total_w * ratio)
                self.paned_window.sash_place(0, sash_x, 0)
        except Exception:
            pass

    def _load_and_apply_saved_settings(self):
        saved = load_settings()
        self._apply_dict_to_ui(saved)
        active = saved.get("active_preset", "Standard (Default)")
        self._update_preset_menu(select_name=active)

        # Restore window geometry
        w = saved.get("window_width", 1200)
        h = saved.get("window_height", 880)
        x = saved.get("window_x", 100)
        y = saved.get("window_y", 100)
        maximized = saved.get("window_maximized", False)
        
        try:
            self.geometry(f"{w}x{h}+{x}+{y}")
            if maximized:
                self.state("zoomed")
        except Exception:
            pass

        # Force Tkinter to draw the layout at target dimensions, then apply splitter ratio
        self.update()
        if "splitter_ratio" in saved:
            try:
                self._apply_splitter_ratio(float(saved["splitter_ratio"]))
            except Exception:
                pass

    def btn_load_preset_clicked(self):
        preset_name = self.option_preset.get()
        data = load_preset(preset_name)
        self._apply_dict_to_ui(data)
        messagebox.showinfo(Text.get("msg_title_preset_loaded"), Text.get("msg_preset_loaded", name=preset_name))

    def btn_save_preset_clicked(self):
        name = simpledialog.askstring(Text.get("msg_preset_save_title"), Text.get("msg_preset_save_prompt"))
        if name and name.strip():
            safe_name = name.strip()
            data = self._export_ui_to_dict()
            if save_preset(safe_name, data):
                self._update_preset_menu(select_name=safe_name)
                messagebox.showinfo(Text.get("msg_title_preset_saved"), Text.get("msg_preset_saved", name=safe_name))
            else:
                messagebox.showerror(Text.get("msg_title_preset_error"), Text.get("msg_preset_error"))

    def btn_quick_save_preset_clicked(self):
        preset_name = self.option_preset.get()
        data = self._export_ui_to_dict()
        if preset_name == "Standard (Default)":
            if save_settings(data):
                messagebox.showinfo(Text.get("msg_title_default_updated"), Text.get("msg_default_updated"))
            else:
                messagebox.showerror(Text.get("msg_title_preset_error"), Text.get("msg_default_update_error"))
        else:
            if save_preset(preset_name, data):
                messagebox.showinfo(Text.get("msg_title_preset_updated"), Text.get("msg_preset_updated", name=preset_name))
            else:
                messagebox.showerror(Text.get("msg_title_preset_error"), Text.get("msg_preset_update_error", name=preset_name))

    def btn_save_default_clicked(self):
        data = self._export_ui_to_dict()
        if save_settings(data):
            messagebox.showinfo(Text.get("msg_title_success"), Text.get("msg_default_updated"))

    def btn_delete_preset_clicked(self):
        preset_name = self.option_preset.get()
        if preset_name == "Standard (Default)":
            messagebox.showwarning(Text.get("msg_title_warning"), Text.get("msg_preset_delete_default_warning"))
            return
        if messagebox.askyesno(Text.get("msg_title_preset_delete_confirm"), Text.get("msg_preset_delete_confirm", name=preset_name)):
            if delete_preset(preset_name):
                self._update_preset_menu()
                messagebox.showinfo(Text.get("msg_title_preset_deleted"), Text.get("msg_preset_deleted", name=preset_name))

    def _update_preset_menu(self, select_name=None):
        presets = list_presets()
        self.option_preset.configure(values=presets)
        if select_name and select_name in presets:
            self.option_preset.set(select_name)
        else:
            self.option_preset.set(presets[0])

    def on_close(self):
        try:
            save_settings(self._export_ui_to_dict())
        except Exception:
            pass
        self.destroy()

    # -----------------------------------------------------------------
    # Helper & Event Handlers
    # -----------------------------------------------------------------
    def _on_status_badge_clicked(self, event=None):
        """Single click handler for status badge popup to prevent multiple popups."""
        if not self.scanned_files:
            return
        idx = self.current_selected_idx
        if 0 <= idx < len(self.scanned_files):
            item = self.scanned_files[idx]
            meta = item.get("meta")
            if meta and meta.has_existing_xmp:
                ExistingTagsDialog(self, item["path"], meta)

    def _on_thumbnail_clicked(self, event=None):
        """Opens the selected image in the system's default image viewer."""
        if not self.scanned_files:
            return
        idx = self.current_selected_idx
        if 0 <= idx < len(self.scanned_files):
            filepath = self.scanned_files[idx]["path"]
            if os.path.exists(filepath):
                import platform
                import subprocess
                try:
                    if platform.system() == "Windows":
                        os.startfile(filepath)
                    elif platform.system() == "Darwin":
                        subprocess.run(["open", filepath], check=True)
                    else:
                        subprocess.run(["xdg-open", filepath], check=True)
                except Exception as e:
                    messagebox.showerror(Text.get("msg_title_preset_error"), Text.get("msg_error_image_open", error=str(e)))

    def open_stopwords_file(self):
        import platform
        import subprocess
        try:
            filepath = get_stopwords_file_path()
            if platform.system() == "Windows":
                os.startfile(filepath)
            elif platform.system() == "Darwin":
                subprocess.run(["open", filepath], check=True)
            else:
                subprocess.run(["xdg-open", filepath], check=True)
        except Exception as e:
            messagebox.showerror(Text.get("msg_title_preset_error"), Text.get("msg_error_stopwords_open", error=str(e)))


    def open_adjectives_file(self):
        import platform
        import subprocess
        try:
            filepath = get_adjectives_file_path()
            if platform.system() == "Windows":
                os.startfile(filepath)
            elif platform.system() == "Darwin":
                subprocess.run(["open", filepath], check=True)
            else:
                subprocess.run(["xdg-open", filepath], check=True)
        except Exception as e:
            messagebox.showerror(Text.get("msg_title_preset_error"), Text.get("msg_error_adjectives_open", error=str(e)))

    def open_short_words_file(self):
        import platform
        import subprocess
        try:
            filepath = get_short_words_file_path()
            if platform.system() == "Windows":
                os.startfile(filepath)
            elif platform.system() == "Darwin":
                subprocess.run(["open", filepath], check=True)
            else:
                subprocess.run(["xdg-open", filepath], check=True)
        except Exception as e:
            messagebox.showerror(Text.get("msg_title_preset_error"), Text.get("msg_error_shortwords_open", error=str(e)))

    def open_whitelist_file(self):
        import platform
        import subprocess
        try:
            from backend.comfy_parser import get_whitelist_file_path
            filepath = get_whitelist_file_path()
            if platform.system() == "Windows":
                os.startfile(filepath)
            elif platform.system() == "Darwin":
                subprocess.run(["open", filepath], check=True)
            else:
                subprocess.run(["xdg-open", filepath], check=True)
        except Exception as e:
            messagebox.showerror(Text.get("msg_title_preset_error"), Text.get("msg_error_whitelist_open", error=str(e)))

    def open_blacklist_file(self):
        import platform
        import subprocess
        try:
            from backend.comfy_parser import get_blacklist_file_path
            filepath = get_blacklist_file_path()
            if platform.system() == "Windows":
                os.startfile(filepath)
            elif platform.system() == "Darwin":
                subprocess.run(["open", filepath], check=True)
            else:
                subprocess.run(["xdg-open", filepath], check=True)
        except Exception as e:
            messagebox.showerror(Text.get("msg_title_preset_error"), Text.get("msg_error_blacklist_open", error=str(e)))

    def open_custom_metadata_dialog(self):
        vars_dict = {
            "creator": self.var_custom_creator,
            "copyright": self.var_custom_copyright,
            "camera_make": self.var_custom_camera_make,
            "software": self.var_custom_software,
            "comment": self.var_custom_comment
        }
        dialog = CustomMetadataDialog(self, vars_dict)
        self.wait_window(dialog)
        if dialog.saved:
            self.on_setting_changed()

    def on_setting_changed(self):
        if hasattr(self, "file_listbox") and self.file_listbox:
            self.update_listbox_font()
            if self.scanned_files:
                self._render_file_listbox()
        if hasattr(self, "tag_preview_box") and self.tag_preview_box:
            self.update_preview_font()
        if self.scanned_files:
            self._update_highlight_and_preview(self.current_selected_idx)

    def get_prompt_keys_list(self) -> list:
        raw = self.entry_prompt_keys.get("1.0", "end").strip()
        if not raw:
            return ["text", "text_0", "text_1", "text_positive", "positive", "prompt"]
        return [k.strip() for k in raw.split("\n") if k.strip()]

    def get_blacklist_set(self) -> set:
        # Load from blacklist.txt
        from backend.comfy_parser import load_custom_blacklist
        black_words = load_custom_blacklist()

        # Merge with UI entry field words
        raw = self.entry_blacklist.get().strip()
        if raw:
            ui_words = {item.strip().lower() for item in raw.split(",") if item.strip()}
            black_words.update(ui_words)
            
        return black_words

    def get_whitelist_set(self) -> set:
        if not self.var_use_whitelist.get():
            return set()
        
        # Load from whitelist.txt
        from backend.comfy_parser import load_custom_whitelist
        white_words = load_custom_whitelist()
        
        # Merge with UI entry field words
        raw = self.entry_whitelist.get().strip()
        if raw:
            ui_words = {item.strip().lower() for item in raw.split(",") if item.strip()}
            white_words.update(ui_words)
            
        return white_words

    def get_min_strength(self) -> float:
        try:
            val = float(self.entry_min_strength.get().strip())
            return max(0.0, val)
        except Exception:
            return 0.01

    def get_max_tag_length(self) -> int:
        try:
            val = int(self.entry_max_tag_length.get().strip())
            return max(0, val)
        except Exception:
            return 50

    def browse_folder(self):
        chosen = filedialog.askdirectory()
        if chosen:
            self.folder_entry.delete(0, tk.END)
            self.folder_entry.insert(0, chosen)
            self.scan_folder()

    def _update_next_folder_btn(self):
        """Enable or disable the 'Next Folder' button based on whether a later
        sibling directory exists alphabetically in the current folder's parent."""
        if not hasattr(self, "btn_next_folder"):
            return
        current = self.folder_entry.get().strip()
        if not current or not os.path.isdir(current):
            self.btn_next_folder.configure(state="disabled")
            return
        parent = os.path.dirname(current)
        if not parent or parent == current:
            self.btn_next_folder.configure(state="disabled")
            return
        try:
            siblings = sorted(
                [d for d in os.listdir(parent) if os.path.isdir(os.path.join(parent, d))],
                key=lambda s: s.lower()
            )
        except PermissionError:
            self.btn_next_folder.configure(state="disabled")
            return
        current_name = os.path.basename(current)
        if current_name in siblings and siblings.index(current_name) < len(siblings) - 1:
            self.btn_next_folder.configure(state="normal")
        else:
            self.btn_next_folder.configure(state="disabled")

    def next_folder(self):
        """Load the next sibling directory alphabetically and trigger a scan."""
        current = self.folder_entry.get().strip()
        if not current or not os.path.isdir(current):
            return
        parent = os.path.dirname(current)
        if not parent or parent == current:
            return
        try:
            siblings = sorted(
                [d for d in os.listdir(parent) if os.path.isdir(os.path.join(parent, d))],
                key=lambda s: s.lower()
            )
        except PermissionError:
            return
        current_name = os.path.basename(current)
        if current_name not in siblings:
            return
        idx = siblings.index(current_name)
        if idx < len(siblings) - 1:
            next_path = os.path.join(parent, siblings[idx + 1])
            self.folder_entry.delete(0, tk.END)
            self.folder_entry.insert(0, next_path)
            self.scan_folder()

    def scan_folder(self):
        folder_path = self.folder_entry.get().strip()
        if not folder_path or not os.path.exists(folder_path):
            messagebox.showerror(Text.get("msg_title_scan_error"), Text.get("msg_scan_error"))
            return

        if hasattr(self, "scanning_active") and self.scanning_active:
            self.cancel_scanning = True
            self.btn_scan.configure(text=Text.get("btn_scanning"), state="disabled")
            return

        self.scanning_active = True
        self.cancel_scanning = False

        self.scanned_files.clear()
        self.prev_selected_idx = None
        self.file_listbox.configure(state="normal")
        self.file_listbox.delete("1.0", "end")
        self.file_listbox.configure(state="disabled")
        self.tag_preview_box.delete("1.0", tk.END)
        self.lbl_scan_summary.configure(text="")

        # Optimization 2 & 3: Reset Preview panel & warnings summary during scanning
        if hasattr(self, "lbl_thumb") and self.lbl_thumb:
            try:
                self.lbl_thumb._label.configure(image="")
            except Exception:
                pass
            self.lbl_thumb.configure(image=None, text=Text.get("lbl_thumbnail_placeholder"))
        self.current_thumb_image = None

        if hasattr(self, "tag_preview_box") and self.tag_preview_box:
            self.tag_preview_box.configure(state="normal")
            self.tag_preview_box.delete("1.0", "end")
            self.tag_preview_box.configure(state="disabled")

        if hasattr(self, "lbl_status_badge") and self.lbl_status_badge:
            self.lbl_status_badge.configure(text=Text.get("status_badge_no_images"), fg_color="#495057", cursor="")

        if hasattr(self, "lbl_info_filename") and self.lbl_info_filename:
            self.lbl_info_filename.configure(text=Text.get("lbl_info_filename"))
            self.lbl_info_resolution.configure(text=Text.get("lbl_info_resolution"))
            self.lbl_info_date.configure(text=Text.get("lbl_info_date"))
            self.lbl_info_models.configure(text=Text.get("lbl_info_models"))
            self.lbl_info_loras.configure(text=Text.get("lbl_info_loras"))
            self.lbl_info_sampler.configure(text=Text.get("lbl_info_sampler"))

        if hasattr(self, "lbl_scan_summary_warn") and self.lbl_scan_summary_warn:
            self.lbl_scan_summary_warn.configure(text="")

        is_recursive = self.var_recursive_scan.get()

        file_entries = []
        if is_recursive:
            for root, _, files in os.walk(folder_path):
                for f in files:
                    if f.lower().endswith(".png"):
                        full_p = os.path.join(root, f)
                        rel_p = os.path.relpath(full_p, folder_path)
                        file_entries.append((full_p, rel_p, f))
        else:
            for f in os.listdir(folder_path):
                if f.lower().endswith(".png"):
                    full_p = os.path.join(folder_path, f)
                    file_entries.append((full_p, f, f))

        if not file_entries:
            self.lbl_status.configure(text=Text.get("lbl_status_no_pngs", folder=folder_path))
            self.progress_bar.set(0)
            self.scanning_active = False
            return

        self.btn_scan.configure(
            text=Text.get("btn_scan_cancel"),
            fg_color="#c92a2a",
            hover_color="#a61e1e",
            state="normal"
        )
        self.btn_browse.configure(state="disabled")
        self.btn_next_folder.configure(state="disabled")
        self.btn_process.configure(state="disabled")
        self.progress_bar.set(0)
        self.lbl_status.configure(text=Text.get("lbl_status_scanning_count", count=len(file_entries)))

        min_strength = self.get_min_strength()
        max_length = self.get_max_tag_length()
        ignore_inactive = self.var_ignore_inactive.get()
        ignore_numeric = self.var_ignore_numeric.get()
        blacklist = self.get_blacklist_set()
        whitelist = self.get_whitelist_set()
        prompt_keys = self.get_prompt_keys_list()
        word_based = self.var_word_based_tagging.get()
        stop_words_set = load_custom_stop_words() if word_based else None
        adjectives_set = load_custom_adjectives() if word_based else None
        short_words_set = load_custom_short_words() if word_based else None

        def _do_scan():
            valid_count = 0
            total_files = len(file_entries)

            for i, (full_path, display_name, filename) in enumerate(file_entries):
                if self.cancel_scanning:
                    break

                progress = (i + 1) / total_files
                status_text = Text.get("lbl_status_scanning_progress", current=i + 1, total=total_files)
                self.after(0, lambda p=progress, s=status_text: self._update_progress(p, s))

                meta = parse_comfy_png(
                    full_path,
                    min_lora_strength=min_strength,
                    ignore_inactive_nodes=ignore_inactive,
                    blacklist_tags=blacklist,
                    whitelist_tags=whitelist,
                    custom_prompt_keys=prompt_keys,
                    ignore_numeric_tags=ignore_numeric,
                    max_tag_length=max_length,
                    word_based_tagging=word_based,
                    stop_words=stop_words_set,
                    adjectives=adjectives_set,
                    short_words=short_words_set,
                    lowercase_prompt_tags=self.var_lowercase_prompt_tags.get()
                )
                if meta:
                    valid_count += 1
                    self.scanned_files.append({
                        "path": full_path,
                        "display_name": display_name,
                        "filename": filename,
                        "meta": meta
                    })

            cancelled_flag = self.cancel_scanning
            self.after(0, lambda: self._on_scan_complete(valid_count, total_files, cancelled=cancelled_flag))

        threading.Thread(target=_do_scan, daemon=True).start()

    def _update_progress(self, value, text):
        self.progress_bar.set(value)
        self.lbl_status.configure(text=text)

    def update_listbox_font(self):
        try:
            size = int(self.var_ui_font_size.get())
        except Exception:
            size = 11
        if hasattr(self, "file_listbox") and self.file_listbox:
            self.file_listbox.configure(font=ctk.CTkFont(family="Consolas", size=size))
            tb = self.file_listbox._textbox
            tb.tag_config("checked_box", font=ctk.CTkFont(family="Consolas", size=size, weight="bold"))
            tb.tag_config("unchecked_box", font=ctk.CTkFont(family="Consolas", size=size))
            tb.tag_config("xmp_prefix", font=ctk.CTkFont(family="Consolas", size=size, weight="bold"))
            tb.tag_config("listbox_details", font=ctk.CTkFont(family="Consolas", size=size))
            tb.tag_raise("selected_line")

    def update_preview_font(self):
        try:
            size = int(self.var_ui_preview_font_size.get())
        except Exception:
            size = 12
        if hasattr(self, "tag_preview_box") and self.tag_preview_box:
            self.tag_preview_box.configure(font=ctk.CTkFont(family="Consolas", size=size))
            tb = self.tag_preview_box._textbox
            tb.tag_config("deleted", font=ctk.CTkFont(family="Consolas", size=size))
            tb.tag_config("new", font=ctk.CTkFont(family="Consolas", size=size))
            tb.tag_config("existing", font=ctk.CTkFont(family="Consolas", size=size))
            tb.tag_config("header", font=ctk.CTkFont(family="Consolas", size=size, weight="bold"))
            tb.tag_config("warning", font=ctk.CTkFont(family="Consolas", size=size, weight="bold"))
            tb.tag_config("low_warning", font=ctk.CTkFont(family="Consolas", size=size, weight="bold"))
            tb.tag_config("prompt_body", font=ctk.CTkFont(family="Consolas", size=size))
            tb.tag_config("extra_meta", font=ctk.CTkFont(family="Consolas", size=size))

    def _render_file_listbox(self):
        self.file_listbox.configure(state="normal")
        self.file_listbox.delete("1.0", "end")
        
        show_details = getattr(self, "var_ui_show_details", None)
        show_details_val = show_details.get() if show_details else True
        show_warnings_val = getattr(self, "var_ui_show_listbox_warnings", None)
        show_warnings_bool = show_warnings_val.get() if show_warnings_val else True
        
        lines = []
        for item in self.scanned_files:
            chk_str = "[X]" if item.get("checked", True) else "[ ]"
            prefix_str = "[XMP]" if item["meta"].has_existing_xmp else "     "
            
            warn_str = "⚠ " if (show_warnings_bool and self._has_metadata_warnings(item["meta"])) else ""
            
            details_parts = []
            if show_details_val and hasattr(self, "detail_items"):
                for det in self.detail_items:
                    if not det["visible"]:
                        continue
                    
                    key = det["key"]
                    if key == "checkpoint":
                        model_lbl = Text.get("listbox_model")
                        none_m = Text.get("listbox_none_m")
                        checkpoint_val = ', '.join(item['meta'].checkpoints) or none_m
                        details_parts.append(f"{model_lbl}: {checkpoint_val}")
                        
                    elif key == "lora":
                        loras_lbl = Text.get("listbox_loras")
                        none_f = Text.get("listbox_none_f")
                        loras_val = ', '.join(item['meta'].loras) if item['meta'].loras else none_f
                        details_parts.append(f"{loras_lbl}: {loras_val}")
                        
                    elif key == "resolution":
                        res_lbl = Text.get("listbox_resolution")
                        config = self._get_current_config()
                        res_tier = "None"
                        if item['meta'].width and item['meta'].height:
                            mp = item['meta'].megapixels
                            if mp < config.res_tier1_mp:
                                res_tier = config.res_tier1_name
                            elif mp < config.res_tier2_mp:
                                res_tier = config.res_tier2_name
                            else:
                                res_tier = config.res_tier3_name
                        details_parts.append(f"{res_lbl}: {res_tier}")
                        
                    elif key == "date":
                        date_lbl = Text.get("listbox_date")
                        date_val = item['meta'].creation_date or "None"
                        details_parts.append(f"{date_lbl}: {date_val}")

            if details_parts:
                details_str = " | " + " | ".join(details_parts)
                info_str = f"{warn_str}{item['display_name']}{details_str}"
            else:
                details_str = ""
                info_str = f"{warn_str}{item['display_name']}"

            lines.append(f"{chk_str} {prefix_str} {info_str}")
            item["temp_details_len"] = len(details_str)
            item["temp_warn_len"] = len(warn_str)
            
        self.file_listbox.insert("1.0", "\n".join(lines))
        
        # Apply tags
        for idx, item in enumerate(self.scanned_files):
            line_num = idx + 1
            is_checked = item.get("checked", True)
            
            box_start = f"{line_num}.0"
            box_end = f"{line_num}.3"
            chk_tag = "checked_box" if is_checked else "unchecked_box"
            self.file_listbox.tag_add(chk_tag, box_start, box_end)
            
            if item["meta"].has_existing_xmp:
                self.file_listbox.tag_add("xmp_prefix", f"{line_num}.4", f"{line_num}.9")
                
            details_len = item.get("temp_details_len", 0)
            warn_len = item.get("temp_warn_len", 0)
            if show_details_val and details_len > 0:
                details_start = 10 + warn_len + len(item['display_name'])
                details_end = details_start + details_len
                self.file_listbox.tag_add("listbox_details", f"{line_num}.{details_start}", f"{line_num}.{details_end}")
                
        # Highlight selected line
        if self.scanned_files:
            idx = self.current_selected_idx
            self.file_listbox.tag_add("selected_line", f"{idx + 1}.0", f"{idx + 1}.end")
            
        self.file_listbox.configure(state="disabled")

    def _on_file_click(self, event):
        if not self.scanned_files:
            return
            
        index = self.file_listbox.index(f"@{event.x},{event.y}")
        try:
            line_num = int(index.split(".")[0]) - 1
            col_num = int(index.split(".")[1])
        except (ValueError, IndexError):
            return
            
        if not (0 <= line_num < len(self.scanned_files)):
            return
            
        item = self.scanned_files[line_num]
        
        if col_num < 4:
            # Clicked on checkbox: toggle check
            is_checked = not item.get("checked", True)
            item["checked"] = is_checked
            
            self.file_listbox.configure(state="normal")
            char = "X" if is_checked else " "
            start_idx = f"{line_num + 1}.1"
            end_idx = f"{line_num + 1}.2"
            self.file_listbox.delete(start_idx, end_idx)
            self.file_listbox.insert(start_idx, char)
            
            # Toggle tag
            box_start = f"{line_num + 1}.0"
            box_end = f"{line_num + 1}.3"
            tag_remove = "unchecked_box" if is_checked else "checked_box"
            tag_add = "checked_box" if is_checked else "unchecked_box"
            self.file_listbox.tag_remove(tag_remove, box_start, box_end)
            self.file_listbox.tag_add(tag_add, box_start, box_end)
            
            # Maintain selected line tag if it was selected
            if self.current_selected_idx == line_num:
                self.file_listbox.tag_remove("selected_line", f"{line_num + 1}.0", f"{line_num + 1}.end")
                self.file_listbox.tag_add("selected_line", f"{line_num + 1}.0", f"{line_num + 1}.end")
                
            self.file_listbox.configure(state="disabled")
            self.update_process_button_text()
        else:
            # Clicked on metadata line: update preview selection
            self.current_selected_idx = line_num
            self._update_highlight_and_preview(line_num)

    def _on_key_nav(self, event):
        if not self.scanned_files:
            return
        index = self.file_listbox.index("insert")
        try:
            line_num = int(index.split(".")[0]) - 1
        except (ValueError, IndexError):
            return
        if 0 <= line_num < len(self.scanned_files):
            self.current_selected_idx = line_num
            self._update_highlight_and_preview(line_num)

    def _on_delete_key(self, event=None):
        if not self.scanned_files or getattr(self, "is_processing", False):
            return
        idx = self.current_selected_idx
        if not (0 <= idx < len(self.scanned_files)):
            return
            
        item = self.scanned_files[idx]
        filename = item["filename"]
        filepath = item["path"]
        
        # Confirmation box
        confirm = messagebox.askyesno(
            Text.get("msg_title_delete_image"),
            Text.get("msg_delete_image", name=filename),
            parent=self
        )
        if not confirm:
            return
            
        # Perform native Windows recycle bin delete using ctypes
        ok = False
        try:
            import ctypes
            from ctypes import wintypes
            
            class SHFILEOPSTRUCTW(ctypes.Structure):
                _fields_ = [
                    ("hwnd", wintypes.HWND),
                    ("wFunc", wintypes.UINT),
                    ("pFrom", wintypes.LPCWSTR),
                    ("pTo", wintypes.LPCWSTR),
                    ("fFlags", ctypes.c_ushort),
                    ("fAnyOperationsAborted", wintypes.BOOL),
                    ("hNameMappings", wintypes.LPVOID),
                    ("lpszProgressTitle", wintypes.LPCWSTR),
                ]
                
            p_from = os.path.abspath(filepath) + "\x00\x00"
            fileop = SHFILEOPSTRUCTW()
            fileop.hwnd = None
            fileop.wFunc = 3 # FO_DELETE
            fileop.pFrom = p_from
            fileop.pTo = None
            fileop.fFlags = 0x0040 | 0x0010 | 0x0004 | 0x0400 # FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT | FOF_NOERRORUI
            
            result = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(fileop))
            ok = (result == 0)
        except Exception as e:
            print(f"Error calling SHFileOperationW: {e}")
            ok = False
            
        if ok:
            # Remove item from scanned list
            self.scanned_files.pop(idx)
            
            # Select appropriate next index
            if not self.scanned_files:
                self.current_selected_idx = -1
                # Clear preview and status
                try:
                    self.lbl_thumb._label.configure(image="")
                except Exception:
                    pass
                self.lbl_thumb.configure(image=None, text="[Vorschaubild]")
                self.current_thumb_image = None
                self.tag_preview_box.configure(state="normal")
                self.tag_preview_box.delete("1.0", "end")
                self.tag_preview_box.configure(state="disabled")
                self.lbl_status_badge.configure(text=Text.get("status_badge_no_images"), fg_color="#495057", cursor="")
                self.lbl_info_filename.configure(text=Text.get("lbl_info_filename"))
                self.lbl_info_resolution.configure(text=Text.get("lbl_info_resolution"))
                self.lbl_info_date.configure(text=Text.get("lbl_info_date"))
                self.lbl_info_models.configure(text=Text.get("lbl_info_models"))
                self.lbl_info_loras.configure(text=Text.get("lbl_info_loras"))
                self.lbl_info_sampler.configure(text=Text.get("lbl_info_sampler"))
                self.lbl_status.configure(text=Text.get("lbl_status_image_deleted", filename=filename))
            else:
                if self.current_selected_idx >= len(self.scanned_files):
                    self.current_selected_idx = len(self.scanned_files) - 1
                
                # Update status
                self.lbl_status.configure(text=Text.get("lbl_status_image_deleted", filename=filename))
                
                # Re-render listbox and update preview
                self._render_file_listbox()
                self._update_highlight_and_preview(self.current_selected_idx)
                
                # Sync insertion cursor position in textbox to prevent arrow keys desync
                try:
                    self.file_listbox.configure(state="normal")
                    self.file_listbox.mark_set("insert", f"{self.current_selected_idx + 1}.0")
                    self.file_listbox.configure(state="disabled")
                except Exception:
                    pass
                
            # Update scan summary counts
            total_scanned = len(self.scanned_files)
            xmp_count = sum(1 for it in self.scanned_files if it["meta"].has_existing_xmp)
            if total_scanned > 0:
                self.lbl_scan_summary.configure(text=Text.get("lbl_scan_summary_count", total=total_scanned, xmp=xmp_count))
            else:
                self.lbl_scan_summary.configure(text="")
            
            # Update process button text
            self.update_process_button_text()
        else:
            messagebox.showwarning(
                Text.get("msg_title_warning"),
                Text.get("msg_delete_image_error", name=filename),
                parent=self
            )

    def _on_scan_complete(self, valid_count, total_count, cancelled=False):
        self.scanning_active = False
        self.cancel_scanning = False

        # Restore scan button style
        self.btn_scan.configure(
            text=Text.get("btn_scan"),
            fg_color=self.get_theme_color("color_primary_btn"),
            hover_color=self.get_theme_color("color_primary_hover"),
            state="normal"
        )
        self.btn_browse.configure(state="normal")
        self.btn_process.configure(state="normal")
        self._update_next_folder_btn()

        if cancelled:
            self.progress_bar.set(valid_count / total_count if total_count > 0 else 0)
            self.set_status("lbl_status_scan_cancelled", valid=valid_count, total=total_count)
        else:
            self.progress_bar.set(1.0)
            self.set_status("lbl_status_scan_complete", valid=valid_count, total=total_count)

        # Update scan summary
        self._update_scan_summary()

        if not self.scanned_files:
            self.update_process_button_text()
            return

        # Initialize checked state on all items
        for item in self.scanned_files:
            if "checked" not in item:
                item["checked"] = True

        self.current_selected_idx = 0
        self._render_file_listbox()
        self._update_highlight_and_preview(0)
        self.update_process_button_text()

    def register_widget(self, widget, key, prefix=""):
        self.translatable_widgets.append((widget, key, prefix))
        try:
            widget.configure(text=prefix + Text.get(key))
        except Exception:
            pass
        return widget

    def set_status(self, key, **kwargs):
        self.last_status_info = (key, kwargs)
        self.lbl_status.configure(text=Text.get(key, **kwargs))

    def _on_language_changed(self, lang):
        Text.set_lang(lang)
        self.retranslate_ui()
        self.on_setting_changed()

    def _on_show_details_changed(self):
        self._refresh_details_config_ui()
        self._render_file_listbox()
        self.on_setting_changed()

    def _update_scan_summary(self):
        if not hasattr(self, "lbl_scan_summary") or not self.lbl_scan_summary:
            return
        if not self.scanned_files:
            self.lbl_scan_summary.configure(text="")
            if hasattr(self, "lbl_scan_summary_warn") and self.lbl_scan_summary_warn:
                self.lbl_scan_summary_warn.configure(text="")
            return
            
        total_scanned = len(self.scanned_files)
        xmp_count = sum(1 for item in self.scanned_files if item["meta"].has_existing_xmp)
        
        self.lbl_scan_summary.configure(text=Text.get("lbl_scan_summary_count", total=total_scanned, xmp=xmp_count, warn_str=""))
        
        # Update warnings label packed next to it
        show_warnings_val = getattr(self, "var_ui_show_listbox_warnings", None)
        show_warnings_bool = show_warnings_val.get() if show_warnings_val else True
        
        warn_count = 0
        if show_warnings_bool:
            warn_count = sum(1 for item in self.scanned_files if self._has_metadata_warnings(item["meta"]))
            
        if hasattr(self, "lbl_scan_summary_warn") and self.lbl_scan_summary_warn:
            if warn_count > 0:
                warn_lbl = Text.get("summary_warnings") if warn_count > 1 else Text.get("summary_warning")
                self.lbl_scan_summary_warn.configure(text=f" | ⚠ {warn_count} {warn_lbl}")
            else:
                self.lbl_scan_summary_warn.configure(text="")

    def _on_show_warnings_changed(self):
        self._render_file_listbox()
        self._update_scan_summary()
        self.on_setting_changed()

    def _has_metadata_warnings(self, meta) -> bool:
        # Check prompts
        if self.var_prompts.get():
            if not meta.prompt_tags or len(meta.prompt_tags) < 3:
                return True
        # Check checkpoints
        if self.var_models.get() and not meta.checkpoints:
            return True
        # Check samplers
        if self.var_samplers.get() and (not meta.samplers or not meta.schedulers):
            return True
        return False

    def _refresh_details_config_ui(self):
        if not hasattr(self, "frame_details_config"):
            return
            
        for widget in self.frame_details_config.winfo_children():
            widget.destroy()
            
        show_details = self.var_ui_show_details.get()
        state = "normal" if show_details else "disabled"
        
        lbl_header = ctk.CTkLabel(
            self.frame_details_config,
            text=Text.get("lbl_details_config_header"),
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="gray" if not show_details else None
        )
        lbl_header.grid(row=0, column=0, columnspan=3, padx=0, pady=(2, 4), sticky="w")
        
        for idx, item in enumerate(self.detail_items):
            key = item["key"]
            label = Text.get(item["label_key"])
            visible = item["visible"]
            
            # Checkbox
            var_chk = tk.BooleanVar(value=visible)
            chk = ctk.CTkCheckBox(
                self.frame_details_config,
                text=label,
                variable=var_chk,
                state=state,
                font=ctk.CTkFont(size=11),
                command=lambda k=key, v=var_chk: self._toggle_detail_visibility(k, v.get()),
                height=20
            )
            chk.grid(row=idx+1, column=0, padx=(0, 10), pady=2, sticky="w")
            
            # Move Up Button
            btn_up = ctk.CTkButton(
                self.frame_details_config,
                text="▲",
                width=24,
                height=20,
                state="disabled" if not show_details or idx == 0 else "normal",
                command=lambda i=idx: self._move_detail_item(i, -1)
            )
            btn_up.grid(row=idx+1, column=1, padx=2, pady=2)
            
            # Move Down Button
            btn_down = ctk.CTkButton(
                self.frame_details_config,
                text="▼",
                width=24,
                height=20,
                state="disabled" if not show_details or idx == len(self.detail_items) - 1 else "normal",
                command=lambda i=idx: self._move_detail_item(i, 1)
            )
            btn_down.grid(row=idx+1, column=2, padx=2, pady=2)

    def _toggle_detail_visibility(self, key, is_visible):
        for item in self.detail_items:
            if item["key"] == key:
                item["visible"] = is_visible
                break
        self._render_file_listbox()
        self.on_setting_changed()

    def _move_detail_item(self, idx, direction):
        target_idx = idx + direction
        if 0 <= target_idx < len(self.detail_items):
            self.detail_items[idx], self.detail_items[target_idx] = self.detail_items[target_idx], self.detail_items[idx]
            self._refresh_details_config_ui()
            self._render_file_listbox()
            self.on_setting_changed()

    def _on_thumb_size_changed(self, val_str):
        lang = Text.get_lang()
        for size_val, lang_map in THUMB_SIZE_MAP.items():
            if val_str == lang_map.get(lang) or val_str == lang_map.get("en") or val_str == lang_map.get("de"):
                self.var_ui_thumb_size.set(size_val)
                break
        
        size_val = int(self.var_ui_thumb_size.get())
        if hasattr(self, "lbl_thumb"):
            self.lbl_thumb.configure(width=size_val, height=size_val)

        if hasattr(self, "lbl_analyzer_thumb") and self.lbl_analyzer_thumb:
            self.lbl_analyzer_thumb.configure(width=size_val, height=size_val)
            self._update_analyzer_thumbnail()
            
        if self.scanned_files and self.current_selected_idx >= 0:
            self._update_highlight_and_preview(self.current_selected_idx)
            
        self.on_setting_changed()

    def _update_thumb_option_menu_selection(self):
        if not hasattr(self, "option_thumb_size"):
            return
        lang = Text.get_lang()
        size_val = self.var_ui_thumb_size.get()
        display_values = [
            THUMB_SIZE_MAP["145"][lang],
            THUMB_SIZE_MAP["200"][lang],
            THUMB_SIZE_MAP["320"][lang]
        ]
        self.option_thumb_size.configure(values=display_values)
        current_display = THUMB_SIZE_MAP.get(size_val, THUMB_SIZE_MAP["200"])[lang]
        self.option_thumb_size.set(current_display)

    def retranslate_ui(self):
        # 1. Update window title
        self.title(Text.get("app_title"))
        
        # 2. Main tabs
        try:
            self.tabview._segmented_button._buttons_dict["tab_process"].configure(text=Text.get("tab_process"))
            self.tabview._segmented_button._buttons_dict["tab_settings"].configure(text=Text.get("tab_settings"))
            self.tabview._segmented_button._buttons_dict["tab_analyzer"].configure(text=Text.get("tab_analyzer"))
            self.tabview._segmented_button._buttons_dict["tab_layout"].configure(text=Text.get("tab_layout"))
            self.tabview._segmented_button._buttons_dict["tab_help"].configure(text=Text.get("tab_help"))
        except Exception:
            pass

        # Update Help Segmented Button
        if hasattr(self, "help_seg") and self.help_seg:
            current_value = self.var_help_seg.get()
            selected_key = "getting_started"
            from backend.localization import LOCALIZATION
            for k in ["getting_started", "tagging_rules", "shortcuts", "about"]:
                t_key = f"help_seg_{k}"
                if current_value == LOCALIZATION["en"].get(t_key) or current_value == LOCALIZATION["de"].get(t_key) or current_value == k:
                    selected_key = k
                    break

            localized_values = [
                Text.get("help_seg_getting_started"),
                Text.get("help_seg_tagging_rules"),
                Text.get("help_seg_shortcuts"),
                Text.get("help_seg_about")
            ]
            self.help_seg.configure(values=localized_values)
            self.var_help_seg.set(Text.get(f"help_seg_{selected_key}"))

        # Update Selected Sample File Label in Analyzer Tab
        if hasattr(self, "selected_sample_filename") and hasattr(self, "lbl_sample_file"):
            if self.selected_sample_filename:
                self.lbl_sample_file.configure(text=Text.get("lbl_sample_file_val", filename=self.selected_sample_filename))
            else:
                self.lbl_sample_file.configure(text=Text.get("lbl_sample_file_placeholder"))

        # Update Info/Instruction Label in Analyzer Tab
        if hasattr(self, "lbl_analyzer_info") and self.lbl_analyzer_info:
            if hasattr(self, "analyzer_state"):
                if self.analyzer_state == "initial":
                    self.lbl_analyzer_info.configure(text=Text.get("lbl_analyzer_instruction"), text_color="gray85")
                elif self.analyzer_state == "success":
                    self.lbl_analyzer_info.configure(text=Text.get("lbl_analyzer_intro"), text_color="gray85")
                elif self.analyzer_state == "no_meta":
                    self.lbl_analyzer_info.configure(text=Text.get("lbl_analyzer_no_meta"), text_color="#ff8787")

        # 3. Translate all registered widgets
        for widget, key, prefix in self.translatable_widgets:
            try:
                widget.configure(text=prefix + Text.get(key))
            except Exception:
                pass
                
        # 4. Folder Entry placeholder
        if hasattr(self, "folder_entry"):
            self.folder_entry.configure(placeholder_text=Text.get("scan_dir_placeholder"))

        # 5. Process Button / Status Bar
        self.update_process_button_text()
        if hasattr(self, "last_status_info") and self.last_status_info:
            key, kwargs = self.last_status_info
            self.lbl_status.configure(text=Text.get(key, **kwargs))
        else:
            self.lbl_status.configure(text=Text.get("lbl_status_ready"))
        
        self._update_thumb_option_menu_selection()
        if hasattr(self, "_refresh_details_config_ui"):
            self._refresh_details_config_ui()
        
        # Update scan status labels & summary if files exist
        if self.scanned_files:
            self._update_scan_summary()
            self._update_highlight_and_preview(self.current_selected_idx)
        else:
            if hasattr(self, "lbl_status_badge") and self.lbl_status_badge:
                self.lbl_status_badge.configure(text=Text.get("status_badge_no_images"))
            if hasattr(self, "lbl_info_filename") and self.lbl_info_filename:
                self.lbl_info_filename.configure(text=Text.get("lbl_info_filename"))
            if hasattr(self, "lbl_info_resolution") and self.lbl_info_resolution:
                self.lbl_info_resolution.configure(text=Text.get("lbl_info_resolution"))
            if hasattr(self, "lbl_info_date") and self.lbl_info_date:
                self.lbl_info_date.configure(text=Text.get("lbl_info_date"))
            if hasattr(self, "lbl_info_models") and self.lbl_info_models:
                self.lbl_info_models.configure(text=Text.get("lbl_info_models"))
            if hasattr(self, "lbl_info_loras") and self.lbl_info_loras:
                self.lbl_info_loras.configure(text=Text.get("lbl_info_loras"))
            if hasattr(self, "lbl_info_sampler") and self.lbl_info_sampler:
                self.lbl_info_sampler.configure(text=Text.get("lbl_info_sampler"))

    def select_all_files(self):
        for item in self.scanned_files:
            item["checked"] = True
        self._render_file_listbox()
        self.update_process_button_text()

    def select_no_files(self):
        for item in self.scanned_files:
            item["checked"] = False
        self._render_file_listbox()
        self.update_process_button_text()

    def update_process_button_text(self):
        checked_count = sum(1 for item in self.scanned_files if item.get("checked", True))
        is_reset_mode = self.var_reset_tags.get()
        
        if is_reset_mode:
            if checked_count > 0:
                self.btn_process.configure(
                    text=Text.get("btn_process_remove_count", count=checked_count),
                    state="normal"
                )
            else:
                self.btn_process.configure(
                    text=Text.get("btn_process_remove_none"),
                    state="disabled"
                )
        else:
            if checked_count > 0:
                self.btn_process.configure(
                    text=Text.get("btn_process_apply_count", count=checked_count),
                    state="normal"
                )
            else:
                self.btn_process.configure(
                    text=Text.get("btn_process_apply_none"),
                    state="disabled"
                )

    def _update_highlight_and_preview(self, idx):
        if idx < 0 or idx >= len(self.scanned_files):
            return

        # Update selected line tag in listbox
        self.file_listbox.tag_remove("selected_line", "1.0", "end")
        self.file_listbox.tag_add("selected_line", f"{idx + 1}.0", f"{idx + 1}.end")
            
        self.prev_selected_idx = idx

        item = self.scanned_files[idx]
        display_name = item["display_name"]
        file_path = item["path"]

        # 1. Render Thumbnail Image on the Right Frame
        # On Windows, newly written/replaced files can be temporarily locked by anti-virus software.
        # We try to load the thumbnail, and if it fails due to a sharing lock, we retry after a brief delay.
        def load_thumb(retries=3, delay_ms=150):
            try:
                with Image.open(file_path) as img:
                    img_copy = img.copy()
                    try:
                        thumb_size = int(self.var_ui_thumb_size.get())
                    except Exception:
                        thumb_size = 200
                    img_copy.thumbnail((thumb_size, thumb_size), Image.Resampling.LANCZOS)
                    ctk_img = ctk.CTkImage(light_image=img_copy, dark_image=img_copy, size=img_copy.size)
                    self.current_thumb_image = ctk_img
                    self.lbl_thumb.configure(image=ctk_img, text="")
            except Exception as e:
                if retries > 0:
                    self.after(delay_ms, lambda: load_thumb(retries - 1, delay_ms))
                else:
                    self.lbl_thumb.configure(image=None, text=Text.get("lbl_thumbnail_placeholder"))
        
        load_thumb()

        # 2. Parse ComfyUI metadata for current selected file
        meta = parse_comfy_png(
            file_path,
            min_lora_strength=self.get_min_strength(),
            ignore_inactive_nodes=self.var_ignore_inactive.get(),
            blacklist_tags=self.get_blacklist_set(),
            whitelist_tags=self.get_whitelist_set(),
            custom_prompt_keys=self.get_prompt_keys_list(),
            ignore_numeric_tags=self.var_ignore_numeric.get(),
            max_tag_length=self.get_max_tag_length(),
            word_based_tagging=self.var_word_based_tagging.get()
        ) or item["meta"]
        item["meta"] = meta

        config = self._get_current_config()
        xmp_xml, flat_tags, h_tags = generate_xmp_payload(meta, config)
        
        self.lbl_preview_title.configure(text=Text.get("lbl_preview_title_formatted", current=idx+1, total=len(self.scanned_files), filename=item['filename']))

        # 3. Update Left Metadata Labels & Interactive Status Badge
        if meta.has_existing_xmp:
            tags_count = len(meta.existing_xmp_tags)
            self.lbl_status_badge.configure(
                text=Text.get("status_badge_tagged"),
                fg_color=self.get_theme_color("color_danger_btn"),
                cursor="hand2"
            )
            if self.status_tooltip:
                sample_str = f" (z. B. {meta.existing_xmp_tags[0]})" if meta.existing_xmp_tags else ""
                self.status_tooltip.update_text(Text.get("status_badge_tooltip_tagged", count=tags_count, sample=sample_str))
        else:
            self.lbl_status_badge.configure(
                text=Text.get("status_badge_untagged"),
                fg_color=self.get_theme_color("color_badge_untagged"),
                cursor=""
            )
            if self.status_tooltip:
                self.status_tooltip.update_text(Text.get("status_badge_tooltip_untagged"))

        self.lbl_info_filename.configure(text=Text.get("lbl_info_filename_val", filename=display_name))

        if meta.width and meta.height and meta.megapixels:
            self.lbl_info_resolution.configure(text=Text.get("lbl_info_resolution_val", w=meta.width, h=meta.height, mp=meta.megapixels))
        else:
            self.lbl_info_resolution.configure(text=Text.get("lbl_info_resolution"))

        # 2b. Determine and display date (XMP CreateDate or OS fallback)
        display_date = None
        if meta.raw_xmp_str:
            try:
                xmp_props = extract_all_xmp_properties(meta.raw_xmp_str)
                for k, v in xmp_props.items():
                    k_lower = k.lower()
                    if "createdate" in k_lower or "datetime" in k_lower or "date" in k_lower:
                        display_date = v
                        break
            except Exception:
                pass

        if not display_date and meta.creation_date:
            display_date = meta.creation_date

        if display_date:
            display_date = display_date.replace("T", " ")
            if "+" in display_date:
                display_date = display_date.split("+")[0]
            elif "-" in display_date.split(" ")[-1]:
                parts = display_date.rsplit("-", 1)
                if len(parts) > 1 and ":" in parts[1]:
                    display_date = parts[0]
            if display_date.endswith("Z"):
                display_date = display_date[:-1]
            self.lbl_info_date.configure(text=Text.get("lbl_info_date_val", date=display_date))
        else:
            self.lbl_info_date.configure(text=Text.get("lbl_info_date"))

        none_val = Text.get("val_none")
        self.lbl_info_models.configure(text=Text.get("lbl_info_models_val", models=', '.join(meta.checkpoints) if meta.checkpoints else none_val))
        self.lbl_info_loras.configure(text=Text.get("lbl_info_loras_val", loras=', '.join(meta.loras) if meta.loras else none_val))
        
        samplers_str = ', '.join(meta.samplers) if meta.samplers else none_val
        sched_str = ', '.join(meta.schedulers) if meta.schedulers else none_val
        self.lbl_info_sampler.configure(text=Text.get("lbl_info_sampler_val", samplers=samplers_str, schedulers=sched_str))

        # 4. Render clean, grouped XMP Tags with vertical spacing in Text Box
        self.tag_preview_box.configure(state="normal")
        self.tag_preview_box.delete("1.0", tk.END)

        if self.var_reset_tags.get():
            self.tag_preview_box.insert("end", Text.get("preview_reset_header"), "header")
            for widget in [self.tag_preview_box, getattr(self.tag_preview_box, "_textbox", None)]:
                if widget and hasattr(widget, "tag_config"):
                    try:
                        widget.tag_config("deleted", foreground=self.get_theme_color("color_tag_deleted"))
                        widget.tag_config("header", foreground="#adb5bd")
                    except Exception:
                        pass
            
            if meta.has_existing_xmp and meta.existing_xmp_tags:
                current_cat = None
                for ex in sorted(meta.existing_xmp_tags):
                    if "/" in ex:
                        prefix, val = ex.split("/", 1)
                        if current_cat is not None and prefix != current_cat:
                            self.tag_preview_box.insert("end", "\n")
                        current_cat = prefix
                        self.tag_preview_box.insert("end", f"  - {prefix}: {val}\n", "deleted")
                    else:
                        if current_cat is not None and "Other" != current_cat:
                            self.tag_preview_box.insert("end", "\n")
                        current_cat = "Other"
                        self.tag_preview_box.insert("end", f"  - {ex}\n", "deleted")
            else:
                self.tag_preview_box.insert("end", Text.get("preview_no_tags_to_reset"))
            self.tag_preview_box.configure(state="disabled")
            return

        # Configure custom Tkinter tags for text highlighting (try both widget and underlying text widget)
        for widget in [self.tag_preview_box, getattr(self.tag_preview_box, "_textbox", None)]:
            if widget and hasattr(widget, "tag_config"):
                try:
                    widget.tag_config("new", foreground=self.get_theme_color("color_tag_new"))
                    widget.tag_config("existing", foreground=self.get_theme_color("color_tag_existing"))
                    widget.tag_config("header", foreground="#adb5bd")
                    widget.tag_config("warning", foreground=self.get_theme_color("color_tag_warning"))
                    widget.tag_config("low_warning", foreground=self.get_theme_color("color_tag_low_warning"))
                    widget.tag_config("prompt_body", foreground=self.get_theme_color("color_textbox_prompt_body"))
                except Exception:
                    pass

        self.tag_preview_box.insert("end", Text.get("preview_hierarchical_header"), "header")

        existing_hierarchical_set = set()
        existing_flat_set = set()
        if meta.has_existing_xmp and meta.existing_xmp_tags:
            for ex in meta.existing_xmp_tags:
                ex_clean = ex.strip().lower()
                existing_hierarchical_set.add(ex_clean)
                existing_flat_set.add(ex_clean)
                if "/" in ex_clean:
                    leaf = ex_clean.rsplit("/", 1)[-1]
                    if leaf:
                        existing_flat_set.add(leaf)

        is_overwrite_active = self.var_overwrite_tags.get()

        current_cat = None
        for ht in h_tags:
            is_existing = (not is_overwrite_active) and (ht.strip().lower() in existing_hierarchical_set)
            tag_style = "existing" if is_existing else "new"

            if "/" in ht:
                prefix, val = ht.split("/", 1)
                if current_cat is not None and prefix != current_cat:
                    self.tag_preview_box.insert("end", "\n")
                current_cat = prefix
                self.tag_preview_box.insert("end", f"  - {prefix}: {val}\n", tag_style)
            else:
                if current_cat is not None and "Other" != current_cat:
                    self.tag_preview_box.insert("end", "\n")
                current_cat = "Other"
                self.tag_preview_box.insert("end", f"  - {ht}\n", tag_style)

        if config.write_flat_dc:
            self.tag_preview_box.insert("end", Text.get("preview_flat_header"), "header")
            for ft in flat_tags:
                is_existing = (not is_overwrite_active) and (ft.strip().lower() in existing_flat_set)
                tag_style = "existing" if is_existing else "new"
                self.tag_preview_box.insert("end", f"  - {ft}\n", tag_style)

        # If overwrite mode is active, display the list of tags that will be deleted in RED
        if is_overwrite_active and meta.has_existing_xmp and meta.existing_xmp_tags:
            h_tags_lower = {t.strip().lower() for t in h_tags}
            deleted_tags = [t for t in meta.existing_xmp_tags if t.strip().lower() not in h_tags_lower]
            if deleted_tags:
                self.tag_preview_box.insert("end", Text.get("preview_overwrite_header"), "header")
                current_del_cat = None
                for dt in sorted(deleted_tags):
                    if "/" in dt:
                        prefix, val = dt.split("/", 1)
                        if current_del_cat is not None and prefix != current_del_cat:
                            self.tag_preview_box.insert("end", "\n")
                        current_del_cat = prefix
                        self.tag_preview_box.insert("end", f"  - {prefix}: {val}\n", "deleted")
                    else:
                        if current_del_cat is not None and "Other" != current_del_cat:
                            self.tag_preview_box.insert("end", "\n")
                        current_del_cat = "Other"
                        self.tag_preview_box.insert("end", f"  - {dt}\n", "deleted")

        # Check if prompts are enabled but no prompt tags were extracted
        if self.var_prompts.get():
            if not meta.prompt_tags:
                self.tag_preview_box.insert("end", Text.get("preview_warn_no_prompts_header"), "warning")
                self.tag_preview_box.insert("end", Text.get("preview_warn_no_prompts_body"), "warning")
            elif len(meta.prompt_tags) < 3:
                self.tag_preview_box.insert("end", Text.get("preview_warn_few_prompts_header"), "low_warning")
                self.tag_preview_box.insert("end", Text.get("preview_warn_few_prompts_body"), "low_warning")

        # Check if checkpoints are enabled but missing
        if self.var_models.get() and not meta.checkpoints:
            self.tag_preview_box.insert("end", Text.get("preview_warn_no_models_header"), "warning")
            self.tag_preview_box.insert("end", Text.get("preview_warn_no_models_body"), "warning")
            
        # Check if samplers are enabled but missing
        if self.var_samplers.get() and (not meta.samplers or not meta.schedulers):
            self.tag_preview_box.insert("end", Text.get("preview_warn_no_samplers_header"), "warning")
            self.tag_preview_box.insert("end", Text.get("preview_warn_no_samplers_body"), "warning")
        if meta.positive_prompts:
            self.tag_preview_box.insert("end", Text.get("preview_original_prompt_header"), "header")
            for prompt_text in meta.positive_prompts:
                source_str = ""
                if hasattr(meta, "positive_prompts_sources"):
                    source_id = meta.positive_prompts_sources.get(prompt_text)
                    if source_id:
                        source_str = f"({source_id}): "
                self.tag_preview_box.insert("end", f"{source_str}{prompt_text.strip()}\n", "prompt_body")

        # Load existing binary EXIF tags first to compare against new targets
        exif_props = {}
        if file_path and os.path.exists(file_path):
            try:
                from PIL import Image, ExifTags
                with Image.open(file_path) as img:
                    exif_data = img.getexif()
                    for tag, val in exif_data.items():
                        if tag in [0x8769, 34665, 0x8825, 34853]:
                            continue
                        tag_name = ExifTags.TAGS.get(tag, str(tag))
                        exif_props[tag_name] = val
                    try:
                        sub_ifd = exif_data.get_ifd(0x8769)
                        if sub_ifd:
                            for sub_tag, sub_val in sub_ifd.items():
                                tag_name = ExifTags.TAGS.get(sub_tag, str(sub_tag))
                                if sub_tag == 0x8822: # ExposureProgram
                                    prog_names = {
                                        0: "Not defined",
                                        1: "Manual",
                                        2: "Normal program",
                                        3: "Aperture priority",
                                        4: "Shutter priority",
                                        5: "Creative program (Biased toward depth of field)",
                                        6: "Action program (Biased toward fast shutter speed)",
                                        7: "Portrait mode",
                                        8: "Landscape mode"
                                    }
                                    sub_val = f"{sub_val} ({prog_names.get(sub_val, 'Unknown')})"
                                exif_props[tag_name] = sub_val
                    except Exception:
                        pass
            except Exception:
                pass

        def get_exif_val_clean(key):
            val = exif_props.get(key)
            if val is None:
                for k, v in exif_props.items():
                    if k.lower() == key.lower():
                        val = v
                        break
            if val is None:
                return ""
            if isinstance(val, bytes):
                try:
                    val = val.decode("utf-8", errors="ignore")
                except Exception:
                    val = str(val)
            return str(val).replace("\x00", "").strip()

        # Display extra metadata to be written
        if self.var_ui_preview_extra_meta.get():
            extra_meta_items = []
            
            creator = self.var_custom_creator.get().strip()
            if creator:
                is_existing = meta.existing_xmp_properties.get("dc:creator", "").strip() == creator
                extra_meta_items.append(("Creator / Author (dc:creator)", creator, is_existing))
                
            copyright_val = self.var_custom_copyright.get().strip()
            if copyright_val:
                is_existing = meta.existing_xmp_properties.get("dc:rights", "").strip() == copyright_val
                extra_meta_items.append(("Copyright (dc:rights)", copyright_val, is_existing))
                
            make = self.var_custom_camera_make.get().strip()
            if make:
                is_existing = meta.existing_xmp_properties.get("tiff:Make", "").strip() == make
                extra_meta_items.append(("Camera Make (tiff:Make)", make, is_existing))
                
            if self.var_write_camera_model.get() and meta.checkpoints:
                checkpoint = meta.checkpoints[0]
                is_existing = meta.existing_xmp_properties.get("tiff:Model", "").strip() == checkpoint
                extra_meta_items.append(("Camera Model (tiff:Model)", checkpoint, is_existing))
                
            software = self.var_custom_software.get().strip()
            if software:
                is_existing = meta.existing_xmp_properties.get("xmp:CreatorTool", "").strip() == software
                extra_meta_items.append(("Software (xmp:CreatorTool)", software, is_existing))
                
            comment = self.var_custom_comment.get().strip()
            if comment:
                is_existing = meta.existing_xmp_properties.get("exif:UserComment", "").strip() == comment
                extra_meta_items.append(("User Comment (exif:UserComment)", comment, is_existing))
                
            if self.var_write_created_date.get() and meta.creation_date:
                is_existing = meta.existing_xmp_properties.get("xmp:CreateDate", "").strip() == meta.creation_date
                extra_meta_items.append(("Creation Date (xmp:CreateDate)", meta.creation_date, is_existing))
                
            if self.var_write_description.get() and meta.positive_prompts:
                desc_text_comp = "\n\n".join([p.strip() for p in meta.positive_prompts if p.strip()])
                is_existing = meta.existing_xmp_properties.get("dc:description", "").strip() == desc_text_comp.strip()
                
                desc_text_display = " / ".join([p.strip() for p in meta.positive_prompts if p.strip()])
                if len(desc_text_display) > 80:
                    desc_text_display = desc_text_display[:77] + "..."
                extra_meta_items.append(("Description (dc:description)", desc_text_display, is_existing))

            # Display binary EXIF tags to be written in embed mode
            if self.var_mode.get() == "embed":
                if meta.checkpoints:
                    cp_model = meta.checkpoints[0]
                    is_existing = get_exif_val_clean("Make").lower() == cp_model.strip().lower()
                    extra_meta_items.append(("Camera Make (EXIF Make)", cp_model, is_existing))

                samp_sched = None
                if meta.samplers and meta.schedulers:
                    samp_sched = f"{meta.samplers[0]} + {meta.schedulers[0]}"
                elif meta.samplers:
                    samp_sched = meta.samplers[0]
                
                if samp_sched:
                    is_existing = get_exif_val_clean("Model").lower() == samp_sched.strip().lower()
                    extra_meta_items.append(("Camera Model (EXIF Model)", samp_sched, is_existing))

                if self.var_include_resolution.get() and meta.width and meta.height:
                    exposure_prog = None
                    mp = (meta.width * meta.height) / 1000000.0
                    try:
                        t1_mp = float(self.entry_res_t1_mp.get().strip())
                        t2_mp = float(self.entry_res_t2_mp.get().strip())
                    except Exception:
                        t1_mp, t2_mp = 1.0, 2.5
                        
                    if mp < t1_mp:
                        exposure_prog = self.entry_res_t1_name.get().strip() or "Preview"
                    elif mp < t2_mp:
                        exposure_prog = self.entry_res_t2_name.get().strip() or "Standard"
                    else:
                        exposure_prog = self.entry_res_t3_name.get().strip() or "Upscale"

                    if exposure_prog:
                        # 0xa434 in EXIF is LensModel
                        is_existing = get_exif_val_clean("LensModel").lower() == exposure_prog.strip().lower()
                        extra_meta_items.append(("Lens Model (EXIF LensModel)", exposure_prog, is_existing))

            if extra_meta_items:
                self.tag_preview_box.insert("end", Text.get("preview_extra_metadata_header"), "header")
                for key, val, is_existing in extra_meta_items:
                    tag_style = "existing" if is_existing else "extra_meta"
                    self.tag_preview_box.insert("end", f"  - {key}: {val}\n", tag_style)

        # Display existing binary EXIF tags under the original prompt
        if exif_props:
            self.tag_preview_box.insert("end", Text.get("preview_exif_header"), "header")
            for key in sorted(exif_props.keys()):
                val = exif_props[key]
                self.tag_preview_box.insert("end", f"  - {key}: {val}\n", "existing")

        self.tag_preview_box.configure(state="disabled")

    def _get_current_config(self) -> XMPConfig:
        t1_mp = 1.0
        t2_mp = 2.5
        try: t1_mp = float(self.entry_res_t1_mp.get().strip())
        except Exception: pass
        try: t2_mp = float(self.entry_res_t2_mp.get().strip())
        except Exception: pass

        return XMPConfig(
            include_models=self.var_models.get(),
            include_loras=self.var_loras.get(),
            include_samplers=self.var_samplers.get(),
            include_prompts=self.var_prompts.get(),
            include_resolution=self.var_include_resolution.get(),
            prefix_model=self.entry_prefix_model.get().strip() or "Model",
            prefix_lora=self.entry_prefix_lora.get().strip() or "Lora",
            prefix_prompt=self.entry_prefix_prompt.get().strip() or "Prompt",
            prefix_sampler=self.entry_prefix_sampler.get().strip() or "Sampler",
            prefix_resolution=self.entry_prefix_resolution.get().strip() or "Resolution",
            res_tier1_mp=t1_mp,
            res_tier1_name=self.entry_res_t1_name.get().strip() or "Preview",
            res_tier2_mp=t2_mp,
            res_tier2_name=self.entry_res_t2_name.get().strip() or "Standard",
            res_tier3_name=self.entry_res_t3_name.get().strip() or "Upscale",
            write_flat_dc=self.var_write_flat.get(),
            overwrite_existing_tags=self.var_overwrite_tags.get(),
            write_created_date=self.var_write_created_date.get(),
            write_camera_model=self.var_write_camera_model.get(),
            write_description=self.var_write_description.get(),
            custom_creator=self.var_custom_creator.get().strip(),
            custom_copyright=self.var_custom_copyright.get().strip(),
            custom_camera_make=self.var_custom_camera_make.get().strip(),
            custom_software=self.var_custom_software.get().strip(),
            custom_comment=self.var_custom_comment.get().strip(),
            lowercase_prompt_tags=self.var_lowercase_prompt_tags.get()
        )

    def start_batch_processing(self):
        if self.is_processing:
            self.cancel_processing = True
            self.btn_process.configure(text=Text.get("btn_cancelling"), state="disabled")
            self.set_status("lbl_status_cancelling")
            return

        if not self.scanned_files:
            messagebox.showwarning(Text.get("msg_title_warning"), Text.get("msg_no_scanned_files"))
            return

        checked_files = [item for item in self.scanned_files if item.get("checked", True)]
        if not checked_files:
            messagebox.showwarning(Text.get("msg_title_warning"), Text.get("msg_no_checked_files"))
            return

        is_reset_mode = self.var_reset_tags.get()
        mode = self.var_mode.get()

        show_confirm = self.var_ui_show_tagging_confirm.get()
        if show_confirm:
            if is_reset_mode:
                if not messagebox.askyesno(Text.get("msg_reset_tags_warn"), Text.get("msg_reset_tags_body", count=len(checked_files))):
                    return
            else:
                already_tagged_count = sum(1 for item in checked_files if item["meta"].has_existing_xmp)
                msg = Text.get("msg_process_body", count=len(checked_files))
                if already_tagged_count > 0:
                    msg += Text.get("msg_process_already_tagged", count=already_tagged_count)
                if not messagebox.askyesno(Text.get("msg_process_confirm"), msg):
                    return

        self.is_processing = True
        self.cancel_processing = False
        
        self.btn_process.configure(
            text=Text.get("btn_process_cancel"),
            fg_color="#c92a2a",
            hover_color="#a61e1e"
        )
        self.btn_scan.configure(state="disabled")
        self.btn_browse.configure(state="disabled")
        self.btn_next_folder.configure(state="disabled")

        config = self._get_current_config()
        min_str = self.get_min_strength()
        max_len = self.get_max_tag_length()
        ignore_in = self.var_ignore_inactive.get()
        ignore_num = self.var_ignore_numeric.get()
        black = self.get_blacklist_set()
        white = self.get_whitelist_set()
        p_keys = self.get_prompt_keys_list()
        word_based = self.var_word_based_tagging.get()
        stop_words_set = load_custom_stop_words() if word_based else None
        adjectives_set = load_custom_adjectives() if word_based else None
        short_words_set = load_custom_short_words() if word_based else None

        import time
        start_time = time.time()

        def _do_batch():
            total = len(checked_files)
            success_count = 0
            aborted = False

            for i, item in enumerate(checked_files):
                if self.cancel_processing:
                    aborted = True
                    break

                full_path = item["path"]

                if is_reset_mode:
                    ok = remove_xmp_tags_from_file(full_path, mode=mode)
                    if ok:
                        item["meta"].has_existing_xmp = False
                        item["meta"].existing_xmp_tags = []
                        item["meta"].raw_xmp_str = None
                        success_count += 1
                else:
                    meta = parse_comfy_png(
                        full_path,
                        min_lora_strength=min_str,
                        ignore_inactive_nodes=ignore_in,
                        blacklist_tags=black,
                        whitelist_tags=white,
                        custom_prompt_keys=p_keys,
                        ignore_numeric_tags=ignore_num,
                        max_tag_length=max_len,
                        word_based_tagging=word_based,
                        stop_words=stop_words_set,
                        adjectives=adjectives_set,
                        short_words=short_words_set,
                        lowercase_prompt_tags=self.var_lowercase_prompt_tags.get()
                    ) or item["meta"]
                    
                    xmp_xml, _, _ = generate_xmp_payload(meta, config)

                    exposure_prog = None
                    if config.include_resolution and meta.width and meta.height:
                        mp = (meta.width * meta.height) / 1000000.0
                        if mp < config.res_tier1_mp:
                            exposure_prog = config.res_tier1_name
                        elif mp < config.res_tier2_mp:
                            exposure_prog = config.res_tier2_name
                        else:
                            exposure_prog = config.res_tier3_name

                    cp_model = meta.checkpoints[0] if meta.checkpoints else None
                    samp_sched = None
                    if meta.samplers and meta.schedulers:
                        samp_sched = f"{meta.samplers[0]} + {meta.schedulers[0]}"
                    elif meta.samplers:
                        samp_sched = meta.samplers[0]

                    if mode == "embed":
                        ok = embed_xmp_in_png(
                            full_path,
                            xmp_xml,
                            checkpoint_model=cp_model,
                            sampler_scheduler=samp_sched,
                            lens_model=exposure_prog
                        )
                    else:
                        ok = write_xmp_sidecar(full_path, xmp_xml)

                    if ok:
                        item["meta"] = meta
                        item["meta"].has_existing_xmp = True
                        success_count += 1

                progress = (i + 1) / total
                if is_reset_mode:
                    status_text = Text.get("lbl_status_processing_reset", current=i+1, total=total, filename=item['display_name'])
                else:
                    status_text = Text.get("lbl_status_processing_tag", current=i+1, total=total, filename=item['display_name'])
                self.after(0, lambda p=progress, s=status_text: self._update_progress(p, s))

            elapsed_time = time.time() - start_time
            self.after(0, lambda: self._on_batch_complete(success_count, total, is_reset_mode, aborted, elapsed_time))

        threading.Thread(target=_do_batch, daemon=True).start()

    def _update_progress(self, progress, status_text):
        self.progress_bar.set(progress)
        self.lbl_status.configure(text=status_text)

    def _on_batch_complete(self, success_count, total, is_reset_mode, aborted, elapsed_time):
        self.is_processing = False
        self.btn_process.configure(state="normal")
        self.btn_scan.configure(state="normal")
        self.btn_browse.configure(state="normal")
        self._update_next_folder_btn()

        # Restore process button text & style
        self._on_reset_checkbox_toggled()

        # Format elapsed time
        if elapsed_time < 60.0:
            time_str = Text.get("val_seconds", seconds=elapsed_time)
        else:
            mins = int(elapsed_time // 60)
            secs = int(elapsed_time % 60)
            time_str = Text.get("val_minutes_seconds", mins=mins, secs=secs)

        if aborted:
            self.set_status("lbl_status_aborted_summary", count=success_count, total=total, time=time_str)
        else:
            if is_reset_mode:
                self.set_status("lbl_status_reset_done_summary", count=success_count, total=total, time=time_str)
            else:
                self.set_status("lbl_status_success_summary", count=success_count, total=total, time=time_str)

        # Update prefix list indicators by re-rendering listbox
        self._render_file_listbox()

        # Update scan summary
        self._update_scan_summary()

        # Update preview for selected image
        if self.scanned_files:
            self._update_highlight_and_preview(self.current_selected_idx)

def main():
    app = App()
    app.mainloop()

if __name__ == "__main__":
    main()
