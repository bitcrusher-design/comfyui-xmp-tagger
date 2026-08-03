# ComfyUI PNG to DigiKam XMP Image Tagger



A high-performance, non-destructive metadata extractor and XMP tagger designed specifically for **ComfyUI-generated PNG images**. 

This desktop application automatically reads complex ComfyUI workflow graphs, extracts prompts, samplers, checkpoints, and LoRAs, and converts them into standardized, hierarchical **XMP/Dublin-Core metadata**. Your generated AI art becomes instantly searchable and neatly organized in professional digital asset managers like **digiKam** and **Adobe Lightroom**.

---

## 📸 Overview & Key Features

- **⚡ Lossless Byte-Level Writing (`embed` mode)**
  Injects XMP metadata directly into PNG chunks in ~30ms per image without decompressing or re-compressing pixels—preserving original ComfyUI workflow data intact.
- **📁 Dual Tagging Modes**
  Choose between direct binary embedding into the PNG or generating external `.xmp` sidecar files.
- **🧠 Intelligent ComfyUI Workflow Parsing**
  Handles complex graphs, muted/bypassed nodes, custom nodes, and special loaders like `Power Lora Loader (rgthree)`. Automatically pairs samplers with their respective schedulers (e.g., `euler / normal`).
- **🔤 Flexible Prompt Tokenization & Filtering**
  Extract tags using comma-delimited or word-level splits. Filter out negative prompts, quality buzzwords, and customizable stopwords (`stopwords.txt`, `adjectives.txt`, `short_words.txt`).
- **🛡️ High-Performance GUI (GDI Handle Safe)**
  CustomTkinter interface optimized for huge folders. Uses a virtualized single-textbox renderer to prevent OS handle limits and Windows memory crashes.
- **🔍 Built-in Workflow Analyzer**
  Inspect raw image chunks, auto-detect positive prompt nodes, and inject custom Node IDs directly into your config with one click.
- **🎨 Visual Metadata Diff & Smart Colors**
  Live preview highlighting:
  - **Green**: New tags to be written
  - **Gray**: Existing tags already present
  - **Red**: Tags queued for deletion (overwrite mode)
- **📅 EXIF & Creation Date Fallback**
  Prioritizes standard EXIF metadata, falls back to XMP creation dates, or utilizes file system timestamps to ensure accurate sorting.
- **🌍 Localization & Custom Themes**
  Full English & German UI support, preset management, and real-time customizable color themes.

---

## 🛠️ Prerequisites & Installation

### System Requirements
- **Python**: `3.10` or higher
- **OS**: Windows (optimized with GDI handle safety), macOS, or Linux

### Main Python Dependencies
The app relies on the following key libraries (installed automatically via `requirements.txt`):
- `customtkinter` (Modern UI framework)
- `Pillow` (Image metadata & file processing)
- `packaging` (Version checking)

## 🛠️Installation

1. **Clone the Repository**
   ```bash
   git clone [https://github.com/your-username/comfyui-png-xmp-tagger.git](https://github.com/your-username/comfyui-png-xmp-tagger.git)
   cd comfyui-png-xmp-tagger
   

### Quick Start (Windows)

Windows One-Click Launchers:

    Double-click Start.bat to launch via terminal.

    Double-click Start.vbs to launch silently in the background (no command prompt window).

### Use Start.bat or Start.vbs (for launching without console window).  
```bash
Run "Start.bat"/"Start.vbs" to check/install requirements.txt and launch the Software.  
```


### Manual:

#### Windows
  ```bash
  python -m venv venv
  venv\Scripts\activate
  pip install -r requirements.txt
```


#### Linux / macOS
```bash
python3 -m venv venv
source venv/bin/activate
venv\Scripts ctivate # Windows
pip install -r requirements.txt
```
---

## 🏗️ Architecture Flow

```mermaid
graph TD
    A[Scan Folder / Select PNG] --> B[comfy_parser: Read PNG Chunks]
    B --> C[Extract Checkpoints, LoRAs, Samplers, Dimensions]
    B --> D[Extract Positive Prompt Strings & Tokenize]
    B --> E[Extract Existing EXIF/XMP Tags]
    C & D & E --> F[GUI: Render Live Preview & Diff Comparison]
    F --> G[xmp_builder: Construct XMP/XML Payload]
    G --> H{Write Mode}
    H -->|Embed Mode| I[Lossless Byte-Level PNG Chunk Injection]
    H -->|Sidecar Mode| J[Generate .xmp Sidecar File]
