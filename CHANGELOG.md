# Changelog - ComfyUI XMP Tagger

This document lists the chronological development, milestones, new features, and bug fixes for the **ComfyUI XMP Tagger** designed to prepare Stable Diffusion images for digiKam.

---

## 🔍 Milestone 14: Workflow Analyzer & Key Extraction (Current)

Introduces an automated visual and metadata analysis tab that enables ComfyUI users to select a sample image, inspect positive prompt candidate text blocks inside its workflow, and instantly inject their configurations into settings without manual JSON searching.

* **Dedicated "Workflow Analyzer" Tab**:
  - Implemented a standalone tab ("Workflow-Analysator" / "Workflow Analyzer") to analyze the embedded graph metadata of ComfyUI-generated PNG files.
* **Candidate-Discovery Algorithm**:
  - Scans both the API execution graph (`prompt`) and the UI nodes structure (`workflow`), dynamically filtering out negative keywords, asset paths, and extensions to isolate positive prompt text fields.
* **Tacit Shortcut Injection (Buttons)**:
  - Displays discovered candidates in card-shaped elements with selectable and copyable raw text boxes.
  - Equips each card with quick-action buttons to directly add the exact **Node ID** (`+ ID`), **Widget Key** (`+ Key`), or **Custom Node Name** (`+ Name`) to the Custom Prompt Field Names in the Settings tab.
  - **Dynamic Visual Button Feedback**: Pre-scans settings and disables keys that are already added (marked with a green `✓`). When clicked, buttons transition instantly to disabled state with a green checkmark and green color, providing silent, satisfying visual feedback without interrupting popups.
* **Synchronized Live Image Preview**:
  - Embeds the image thumbnail in the top-right corner to allow instant visual confirmation of the scanned image contents.
  - Dynamically resizes the thumbnail in real-time when global image display size settings are updated.
* **Optimized Grid Layout**:
  - Organized the controls, detailed instructions, and thumbnail inside a balanced header frame, allowing the scroll container to span the full window width, positioning the scrollbar on the rightmost edge and avoiding empty space gaps.
* **Comprehensive Instruction Tooltips**:
  - Rewrote the initial instruction texts in both German and English to clearly explain the workflow analyzer's mechanics and how to use it to optimize key extraction.
* **New Feature: ❓ Help & About Tab**:
  - Added a dedicated "Help & About" (Hilfe & Info) tab to provide guidance and manual information without overwhelming the user.
  - Implemented an interactive layout featuring a segmented selector button (`🚀 Erste Schritte`, `🏷️ Tag-Regeln`, `⌨️ Tastenkürzel`, `ℹ️ Info`) to toggle different help pages dynamically.
  - Formatted content using card-based designs with stylized consolas-font keyboard shortcuts badges (e.g. `Entf`, `F5`, `Leertaste`).
  - Added a `"View Changelog..."` button that opens the full version history directly in a read-only, scrollable pop-up window.
  - Expanded the `"Getting Started"` (Erste Schritte) guide with a new introductory card detailing the background and purpose of XMP tag conversion for photo managers like DigiKam.
  - Significantly rewrote and expanded steps 1 to 4 to provide comprehensive, beginner-friendly instructions for scanning, preview highlights, and ultra-fast lossless byte writing.
* **QoL Optimization: Active Scan Cancellation & Panel Resets**:
  - Implemented the ability to cancel an active folder scan. The button dynamically switches to a red `"❌ Scan abbrechen"` / `"❌ Cancel Scan"` button, allowing the user to gracefully abort large folder reads while keeping already parsed files.
  - Added instant resets for the Thumbnail & Details Preview panel and the XMP Tags listbox during directory scans, preventing outdated metadata from being displayed.
  - Added instant resets for the warnings count summary above the file listbox during scans.
  - Fixed XMP tag rendering to dynamically manage disabled widget states, ensuring previews update correctly after directory loads.
  - Replaced composite emoji symbols with bare warning unicode characters (`⚠`) to fix Windows/Tkinter text alignment spacing bugs.
  - Fixed a CustomTkinter garbage collection bug where reusing the same label for subsequent directory scans (e.g. after clicking "Next Folder") caused a `TclError` due to stale image references. Added underlying Tkinter label image dissociation (`_label.configure(image="")`) before clearing references.

---

## 🖼️ Milestone 13: XMP/EXIF Metadata Preview Block

Adds a live preview section for non-tag metadata (Author, Copyright, Camera Make/Model, Software, User Comment, Creation Date, Description) directly in the tag preview panel, styled with its own distinct color.

* **Live Extra Metadata Preview**:
  - Displays extra XMP and EXIF metadata that will be written to the image, directly below the "Original Prompt" section.
  - Formatted clearly (e.g. `Creator / Author (dc:creator): <val>`).
  - **Dynamic Casing/Highlight Behavior**: If a metadata field already exists in the image and its value matches the new target value exactly, it is highlighted in gray (standard `existing` tag color). If the field is new or its value will be changed/updated, it is highlighted in the distinct `color_tag_extra_meta` theme color. This gives the user instant visual feedback on what will actually change in the file.
  - **EXIF Target Preview Fields**: Added target EXIF Make, EXIF Model, and EXIF LensModel fields (written in `embed` mode) to the `[Extra Metadata to be written]` preview list.
  - **Robust EXIF Matching (`get_exif_val_clean`)**: Implemented a string cleaning helper to resolve comparison mismatches caused by trailing null bytes (`\x00`), bytes-to-string format differences, or case sensitivity (e.g. `lcm + karras` vs `LCM + Karras`), guaranteeing that written EXIF values correctly turn gray in the preview.
* **Node ID Source for Original Prompts**:
  - Added Node ID indicators (e.g., `(ID: 6): 1girl, sitting in green nature...`) before each positive prompt string inside the `Original Prompt:` preview block. This makes it instantly visible which node in the ComfyUI workflow was extracted as the positive prompt source, allowing easier troubleshooting and adjustment of the prompt keys configuration.
* **Robust EXIF Writer Fallback**:
  - Added fallback handling in the PNG byte editor. If merging new metadata with a corrupt or invalid existing EXIF header (e.g. due to broken timestamps like `026:07:21`) fails in Pillow, the tool falls back to generating a fresh, valid EXIF chunk with the new values, ensuring tags are reliably written.
* **Settings Toggle Checkbox**:
  - Added new setting `"Show extra XMP/EXIF metadata (creator, copyright, etc.) in preview"` under the Layout tab.
  - Automatically saved to settings and loaded on startup.
* **Harmonious Theme Color Highlight (`color_tag_extra_meta`)**:
  - Introduced a separate distinct color for the extra metadata lines in all default themes:
    - *Standard Dark*: Soft lavender (`#b197fc`)
    - *Nordic Frost*: Nordic purple (`#b48ead`)
    - *Sunset Orange*: Amethyst purple (`#9b59b6`)
    - *Cyberpunk Neon*: Neon magenta-purple (`#cc00ff`)
  - Registered in the theme customizer dialog so users can tweak this color dynamically.
* **Tooltip Improvements & Localization Fixes**:
  - Increased the font size of the info/tooltip icons (`🛈`) from `14` to `22` for significantly better readability and visibility in the settings headers.
  - Increased the font size of all five list editing label links (whitelist, blacklist, stopwords, adjectives, short words) from `11` to `13` to make them clearer and much easier to read.
  - Fixed a translation system bug by adding missing localization keys (`lbl_sec_storage_mode`, `lbl_sec_custom_prompt_keys`, `lbl_sec_extra_meta`, `lbl_sec_layout_list` and their tooltips) in both English and German to `localization.py`, ensuring all headers and tooltips translate correctly.
* **Custom Whitelist File (`whitelist.txt`)**:
  - Integrated `config/whitelist.txt` file support for managing large and complex whitelist collections.
  - Automatically merges keywords loaded from `whitelist.txt` with the comma-separated words in the UI input field, allowing users to use both mechanisms concurrently.
  - Added a clickable UI button/link `📄 Whitelist-Datei bearbeiten (whitelist.txt)` directly below the Whitelist entry field to quickly open and edit the file in the default text editor.
  - Implemented automatic file initialization with default comments and example items, full theme color linking, and error dialogs for platform-agnostic file opening.
* **Custom Blacklist File (`blacklist.txt`)**:
  - Integrated `config/blacklist.txt` file support for managing large and complex blacklist collections.
  - Automatically merges keywords loaded from `blacklist.txt` with the comma-separated words in the UI input field, allowing users to use both mechanisms concurrently.
  - Added a clickable UI button/link `📄 Blacklist-Datei bearbeiten (blacklist.txt)` directly below the Blacklist entry field to quickly open and edit the file in the default text editor.
  - Implemented automatic file initialization with default comments and example items, full theme color linking, and error dialogs for platform-agnostic file opening.
* **Dedicated Language Settings Section**:
  - Separated the Language settings dropdown into its own dedicated `Language Settings` (Spracheinstellungen) category section in the `Layout & Design` tab, complete with its own info/tooltip icon (`🌐`).
  - Shifted theme selectors inside `sec_list` up in the grid to maintain compact spacing, greatly improving the layout clarity.
* **Preview Thumbnail Display Size Selector**:
  - Implemented a dropdown setting for the preview image size (`145x145`, `200x200`, `320x320`) in the `Layout & Design` settings.
  - Automatically resizes the thumbnail display frame and scales the loaded image to fit the new dimensions immediately when the setting is changed.
  - Full setting persistence (saves and restores on launch) and dynamic localization support.
* **Power Lora Loader Support**:
  - Added support for parsing LoRAs loaded via ComfyUI's custom `Power Lora Loader (rgthree)` node.
  - Correctly reads the activation status (`"on": true`/`"on": false`) of each LoRA in the loader, ensuring inactive/disabled LoRAs are ignored even if they specify a strength value.
  - Extracts active LoRA paths and filters them using the minimum strength threshold (`min_lora_strength`), matching both unified and split model/clip strength configurations.
* **Customizable File Listbox Details**:
  - Implemented configurable file details in the main file listbox, enabling users to toggle visibility and drag/reorder displayed metadata columns (Checkpoints, LoRAs, Resolution Category, and Creation Date).
  - Added a dynamic control panel in Layout settings with checkboxes and tactile Up/Down arrow buttons (`▲`/`▼`) for active details configuration.
  - Dynamically updates text tagging offsets and highlights for details formatting based on active sequence and length parameters.
  - Fully integrated setting serialization for presets and launch persistence.
* **File List Metadata Warning Indicators**:
  - Added warning icons (`⚠️`) directly next to filenames in the file list for files with missing or sparse metadata.
  - Automatically raises warnings when prompt tags are sparse/empty (under 3 tags), when checkpoint/model data is missing (if models are enabled), or when sampler/scheduler settings are missing (if samplers are enabled).
  - Added a configuration setting `"Show warnings for missing/few metadata details in file list"` in the Layout & Design settings to let users toggle listbox warnings.
  - Added matching warning blocks to the live tag preview panel for missing model/checkpoint and sampler details.
  - Added a dynamic warnings summary count in the file list status header (e.g. `28 images | 0 with XMP tags | ⚠️ 6 warnings`), split side-by-side to highlight the warnings section with the exact warning theme color (`color_tag_warning`).
  - Globally removed variation selectors (`\ufe0f`) from all emojis (`🗑`, `🏷`, `✍`, `⚙`, `ℹ`, `⚠️`, `🖼`) across all localization keys. This completely resolves Tkinter layout engine spacing bugs where excessive whitespace gaps were introduced after icons, ensuring clean, uniform text alignment across the entire application interface.
  - Restructured the "Layout & Design" settings tab into four logical categories: "File List & View Settings" (Dateiliste & Ansichts-Einstellungen), "XMP Preview Settings" (XMP-Vorschau-Einstellungen), "Appearance Settings" (Erscheinungsbild-Einstellungen), and "Language Settings" (Spracheinstellungen).
  - Shifted the font size controls, preview thumbnail image size dropdown, theme configuration, and language selector into their respective containers, making the layout much cleaner and easier to navigate.
* **Startup Localization Bugfix**:
  - Resolved an initialization bug where metadata fields and the status pill in the live preview panel defaulted to German at startup regardless of saved language settings.
  - Registered all info panel labels in the widget translation system, replacing hardcoded startup placeholders and ensuring full translation sync on load and language toggle even without scanned files.
* **Paired Sampler & Scheduler XMP Tags**:
  - Enhanced the XMP tag builder to pair samplers with their corresponding schedulers using index-based lookup (e.g., generating `Sampler: euler / normal` or `Sampler: lcm / karras`).
  - Ensures these combined sampler/scheduler values are written as flat and hierarchical XMP metadata tags, matching the visual layout of the live preview panel.
* **Optional Process Confirmation Dialog**:
  - Added a configuration checkbox `"Show confirmation dialog before writing XMP tags"` in Settings & Tag Rules (under the renamed `"Storage & Process Options"` section).
  - When unchecked, the batch tagging process starts immediately when clicking the `"Apply XMP tags..."` button, bypassing confirmation prompts for a faster workflow.
* **Recursive Scan Tooltip**:
  - Added a descriptive mouse-hover tooltip to the `"Recursive"` checkbox next to the Scan Folder button in the main tab, explaining its folder-traversal behavior in both languages.
* **Detailed Right-Column Settings Tooltips**:
  - Rewrote and expanded tooltips in the right column of Settings & Tag Rules (Custom Prompt Keys, Whitelist, Filter & Blacklist, and Global Metadata Options) in both English and German.
  - Added explicit line breaks (`\n`) to control the tooltip box width, ensuring paragraph-like readability instead of overflowing the screen.
  - Offers clear documentation on key parsing functionality, comma-separated lists, lowercase normalization, and global metadata generation directly within the UI helper overlays.
* **Language Settings Position**:
  - Reordered the Layout & Design settings sections to place `"Language Settings"` (Spracheinstellungen) at the very top (row 0), shifting other sections downwards for enhanced accessibility.

---

## 🔡 Milestone 12: Lowercase Tag Normalization

Addresses duplicate tags in DigiKam caused by inconsistent casing in ComfyUI prompts (e.g. `"Portrait"`, `"portrait"`, and `"PORTRAIT"` would previously create three separate tags).

* **New setting: "Normalize prompt tags to lowercase"** (Settings → Filter & Blacklist section):
  - When enabled, all extracted **prompt tags** are converted to lowercase before being written as XMP tags.
  - **Model names, LoRA names, sampler, and scheduler names are intentionally excluded** and remain in their original casing (e.g. `DreamShaper_8`, `Pony XL` are preserved).
  - The normalization is applied at the earliest possible point inside `extract_prompt_tags()` so it consistently affects all code paths (scan preview and batch processing).
  - Duplicate detection already operates case-insensitively, so enabling this option also closes the edge case where `"Portrait"` and `"portrait"` from *different images* were previously kept as distinct tags.
* **Implementation details**:
  - New `lowercase_prompt_tags: bool` parameter added to `extract_prompt_tags()` and `parse_comfy_png()` in `backend/comfy_parser.py`.
  - New field `lowercase_prompt_tags` added to `XMPConfig` in `backend/xmp_builder.py`.
  - New default setting `"lowercase_prompt_tags": false` added to `backend/settings_manager.py`.
  - New UI checkbox `chk_lowercase_prompt_tags` added to the Settings tab (Filter & Blacklist section), with EN and DE localization.
  - Setting is persisted to `settings.json` and respects preset save/load.

---

## 📐 Milestone 11: Compact Layout Optimization for Small Screens


Focused layout refinements to improve usability on notebooks and smaller displays without altering the fundamental structure of the UI. A backup of the original layout is preserved as `gui/app_layout_backup.py`.

* **Header**:
  - Reduced outer padding from `(15, 5)` to `(8, 2)`.
  - Title font size reduced from `22px` to `18px` to save vertical space.
* **Folder Selection Bar**:
  - Container padding reduced from `pady=10` to `pady=5`.
  - All elements in the directory row (label, entry field, buttons) reduced from `pady=(10, 2)` to `pady=(6, 1)`.
  - Renamed label from `"ComfyUI Images Directory:"` to `"Directory:"` (DE: `"Verzeichnis:"`) to free up horizontal space.
  - **Recursive checkbox moved** from a second row below the entry field into the same row as the buttons (column 5), eliminating the second row entirely and saving one full line of vertical height.
  - Checkbox label shortened from `"Scan subfolders recursively"` to `"Recursive"` (DE: `"Rekursiv"`) — function is self-explanatory.
* **Bottom Action Bar** (Checkboxes + Process Button):
  - Container outer padding reduced from `pady=5` to `pady=3`.
  - Internal checkbox row padding reduced from `pady=3` to `pady=1/2`.
  - Process button height reduced from `42px` to `36px`; grid padding from `pady=12` to `pady=3`.
* **Status & Progress Bar**:
  - Bottom frame outer padding reduced from `(0, 8)` to `(0, 5)`.
  - Progress bar internal padding reduced from `(6, 3)` to `(4, 2)`.
  - Status label bottom padding reduced from `(0, 6)` to `(0, 5)`.
* **Image Metadata Panel** (left info area):
  - Container padding reduced from `pady=10` to `pady=6`.
  - Status badge bottom margin reduced from `6px` to `4px`.
  - All metadata labels (`pady=1` → `pady=0`).
  - Added explicit `height` constraints (`height=20` for 11px labels, `height=22` for 12px bold label) to override CTkLabel's internal default height of ~28px, closing the visual gaps between label rows.

**Total vertical space saved: approx. 130–150 px**, allowing significantly more XMP tag preview lines to be visible on smaller screens.

---

## 🎨 Milestone 10: Dynamic Color Theme Customizer & Preset Selector

* **Dynamic Theme Manager**:
  - Introduced a flexible color theme manager supporting default styles (*Standard Dark*, *Nordic Frost*, *Sunset Orange*, *Cyberpunk Neon*) and user-created custom presets.
* **Color Editor Modal Popup & Expanded Customization (25 components)**:
  - Expanded the `ThemeEditorDialog` color editor with additional options for **general text & label color** (`color_label_text`), **file list selection highlight color** (`color_listbox_selected_bg`), **progress bar accent color** (`color_progress_bar`), and **metadata date text color** (`color_info_date`).
* **Real-Time Hot-Reloading & Live Preview**:
  - Color changes are applied instantly via hot-reload to all GUI labels, buttons, text boxes, checkboxes, and the progress bar without requiring a restart.
* **Selected Image Date Display**:
  - Displays the image creation date directly below the resolution in the metadata panel.
  - Prioritizes XMP embedded creation date (`xmp:CreateDate`), falling back to the filesystem creation date.
  - Automatically formats the timestamp into a compact, standardized `YYYY-MM-DD HH:MM:SS` representation.
  - Fully customizable via the theme editor using the new `color_info_date` setting to allow quick visual scanning of image age.
* **XMP Preview Font Size**:
  - Added a separate dropdown in the Layout & Design tab to independently adjust the XMP preview panel font size (8pt–16pt), decoupled from the file list font size.
* **EXIF Metadata in Live Preview**:
  - Existing binary EXIF metadata (e.g. Make, Model, Software, LensModel) is now parsed and displayed at the bottom of the XMP preview panel for full transparency on already-tagged images.
* **Suppression of Completion Popups**:
  - Blocking completion and warning popup dialogs have been disabled. Elapsed processing time and success summaries are now displayed inline in the status bar at the bottom of the window.
* **⏭ Next Folder Button**:
  - Added a *Next Folder* button between *Browse* and *Scan Folder* in the directory selection row.
  - Clicking it loads the next sibling directory alphabetically (case-insensitive) from the same parent and automatically triggers a scan.
  - The button is disabled on startup, automatically enabled after a folder scan if a next sibling exists, and grayed out when the current folder is already the last one in its parent directory.
  - Also disabled during active scanning or batch processing to prevent concurrent operations.
* **Bug Fix: Thumbnail Preview After Tagging (Windows File Lock)**:
  - Fixed a Windows-specific issue where anti-virus or OS file locking would briefly block access to a newly written PNG file, causing the preview thumbnail to fall back to the `[Thumbnail]` placeholder immediately after tagging.
  - The GUI now retries loading the thumbnail up to 3 times at 150ms intervals using `after()`, ensuring reliable preview updates after batch processing completes.
* **Theme Session Persistence**:
  - The active theme is persisted in `config/settings.json` under `"active_theme"` and user-created custom themes are saved to `config/themes.json`.

---

## 🚀 Milestone 9: Short Words Exceptions, Metadata Viewer Expansion & Window Layout Persistence
* **Short Words Exception List (`short_words.txt`)**:
  * Introduced an editable text file (`config/short_words.txt`) to define short terms (< 4 characters, e.g., `cat`, `dog`, `red`, `car`, `hat`) that should be preserved as regular tags despite the word-based length restriction.
  * Added a direct visual link in the settings tab to open and edit short words in the system's default text editor.
* **Window & Splitter Persistence**:
  * The application now saves the exact window position (X/Y coordinates), size (width/height), and maximized status upon closing.
  * The splitter (sash) position is stored as a proportional ratio and restored synchronously on startup to prevent window-manager mapping race conditions.
* **EXIF Camera and Lens Mappings**:
  * **Lens (Objektiv)**: The active resolution tier name (e.g., `Preview`, `Standard`, or `Upscale`) is written as standard clear-text in the EXIF **`LensModel` tag (`0xa434` / `42036`)** in the Exif SubIFD. This displays the resolution tier directly in the "Lens" / "Objektiv" field in digiKam without needing any integer abstraction.
  * **Make (Hersteller)**: The active checkpoint model name is written to the standard EXIF **`Make` tag (`271` / `0x010f`)** in the main IFD0 directory. This places the checkpoint name first in digiKam's combined `Make Model` tooltip display, preventing it from being truncated.
  * **Model (Modell)**: The generation parameters **Sampler + Scheduler** (e.g., `euler_a + normal`) are written to the EXIF **`Model` tag (`272` / `0x0110`)** in the main IFD0 directory.
  * **Exposure Program Removed**: Cleaned up the legacy ExposureProgram tags (`0x8822` / `34850`) completely from both XMP and EXIF outputs to avoid cluttering or confusing the user, since the resolution tier is now cleanly tracked by the clear-text LensModel field.
* **Recycle Bin File Deletion**:
  * Bound the `<Delete>` (Entf) keyboard key to send the currently selected image to the Windows Recycle Bin (Papierkorb) using ctypes and native Shell API (`SHFileOperationW` with `FOF_ALLOWUNDO`), avoiding external library dependencies.
  * Includes a confirmation prompt to prevent accidental deletions. On deletion, the file is automatically removed from the listbox and memory scanned list, and the listbox focus, thumbnail/metadata preview, and scan summary are updated dynamically.
* **Expanded Metadata Detail Dialog & Sleeker Status Badge**:
  * Clickable status badge text shortened to `(🔍 Details)` when XMP tags are present to avoid text truncation on compact screen layouts.
  * Fixed absolute filepath resolution in `ExistingTagsDialog` to read binary EXIF tags directly from disk (instead of failing with a relative path).
  * Re-implemented the metadata dialog (`ExistingTagsDialog`) to display a detailed, structured, read-only view of *both* embedded XMP properties and binary EXIF tags dynamically parsed from the raw XMP and binary EXIF chunks.

---

## 📸 Milestone 8: Custom Metadata Popup & EXIF Extensions
* **Custom Metadata Dialog**:
  * Added a `✍️ Custom Metadaten...` button to the bottom processing bar.
  * Opens a modal dialog to populate global attributes: Creator (`dc:creator`), Copyright notice (`dc:rights`), Camera Maker (`tiff:Make`), Software (`xmp:CreatorTool`), and User Comment (`exif:UserComment`).
  * Empty fields are automatically skipped to avoid overwriting existing properties.
* **Additional EXIF Write Options**:
  * Optional embedding of file creation date (`xmp:CreateDate`), camera model (`tiff:Model` retrieved from the active checkpoint name), and description (`dc:description` containing the full original positive prompt).
* **UI Compactness**:
  * Renamed the bottom panel checkboxes to `🗑️ XMP-Tags löschen` and `🧹 XMP-Tags überschreiben` to optimize horizontal space.

---

## 🎨 Milestone 7: Original Prompt Preview & Usability Enhancements
* **Original Prompt Display**:
  * Added the fully extracted positive prompt in a light grey, subtle font at the very bottom of the live preview box for easy visual verification.
* **Cleaned Preview Panel**:
  * Hidden the notice warning for deactivated flat tags (`dc:subject`) to keep the live preview box clean and concise.
* **Scan Progress Bar**:
  * Enabled progress bar updates during folder scanning. Action buttons are disabled during scanning to prevent concurrent directory scans.

---

## 🧠 Milestone 6: Word-Based Tagging & Adjective Compounding
* **Word-Based Tagging**:
  * Added an optional setting to split full-text prompts (e.g., flow texts without comma delimiters) at word boundaries.
* **Customizable Stop-Words List (`stopwords.txt`)**:
  * Automatic exclusion of common filler words (like `with`, `from`, `have`) using a customizable text file located at `config/stopwords.txt` (includes a direct edit link in settings).
* **Adjective-Noun Compounding (`adjectives.txt`)**:
  * Consecutive adjectives (like colors, sizes, conditions defined in `config/adjectives.txt`) are automatically grouped with the trailing noun into a single tag (e.g., `dirty torn outfit`).
* **Two-Level Warning System**:
  * Displays a red warning if 0 prompt tags are found (indicating potential node misconfigurations).
  * Displays a yellow warning if < 3 tags are found (recommending the word-based tagging option for flow texts).

---

## 📁 Milestone 5: Layout Restructuring & Preset Management
* **Settings Tab Reorganization**:
  * Separated user interface custom settings into a dedicated tab named "🎨 Layout & Design".
  * Split main tagging settings into a clean two-column grid layout, eliminating the need for vertical scrolling.
* **Preset Profiles & Session Persistence**:
  * Save, quick-save, load, and delete custom settings profiles.
  * The application automatically remembers and loads the last active preset on subsequent launches.
* **🛈 Tooltip Help Buttons**:
  * Hovering over the blue `🛈` buttons displays clear explanations for all configuration sections.

---

## 🛠️ Milestone 4: Performance Boost & GDI Crash Fix
* **GDI Handle Leak Prevention**:
  * Completely re-implemented the file selection list using a single, optimized `CTkTextbox` widget with text-based checkbox parsing. This prevents Windows desktop crashes caused by GDI handle exhaustion when scanning large directories with thousands of images.
* **Keyboard Navigation Support**:
  * Added arrow-key keyboard navigation in the file list with instant, responsive image preview updates.
* **Folder Scan Statistics**:
  * Added a scan statistics label near the selection controls (e.g., `902 Bilder | 44 mit XMP-Tags`).

---

## 🔍 Milestone 3: Selective File Processing & Resolution Tiers
* **Manual File Checkboxes**:
  * Introduced selective checkboxes next to each file, alongside "Select All" and "Deselect All" options.
  * Processing operations only target selected files.
* **Resolution Megapixel Tiers**:
  * Generates resolution-specific tags based on image megapixel count across 3 custom tiers (e.g., `Preview`, `Standard`, `Upscale`) with a customizable prefix.
* **Global Substring Blacklist**:
  * Filter out unwanted strings from checkpoints, LoRAs, and prompts.

---

## ⚡ Milestone 2: Active LoRA Filtering & Target Node Configuration
* **Active LoRA Filter**:
  * Automatically detects and bypasses stumm/muted or bypassed ComfyUI nodes, as well as LoRAs whose strength falls below a minimum threshold (e.g., < 0.01).
* **Custom Node Identifiers**:
  * Resolves prompts by looking up specific Node-IDs or input titles (e.g., `text_positive`), ignoring general ShowText or note fields.
* **Interactive Status Badges**:
  * Displays a clickable status badge showing if a file already contains XMP tags. Clicking it opens a preview dialog displaying existing tags.

---

## 🏗️ Milestone 1: Core Foundation (Minimal Viable Product)
* **Metadata Extraction**:
  * Basic parsing of ComfyUI workflow JSON chunks embedded in PNG files.
* **XMP Writing & Sidecar Export**:
  * Injecting hierarchical keywords (`lr:hierarchicalSubject` & `digiKam:TagsList`) as well as flat tags (`dc:subject`) directly into the image file or exporting them as sidecar `.xmp` files.
* **Basic GUI**:
  * Initial layout comprising folder selection, configuration controls, a file list, and a live XMP payload preview.
