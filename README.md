[![Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Release](https://img.shields.io/badge/release-v1.0.0-green.svg)](releases/V1.0.0.0)

A high-performance desktop utility designed to automatically extract **ComfyUI workflows, prompts, models, and samplers** from generated PNG files and embed them as standardized hierarchical and flat XMP metadata tags. 

Perfect for organizing, filtering, and indexing thousands of Stable Diffusion images inside photo management suites like **DigiKam**, **Adobe Lightroom**, or **Bridge**.

---
<img width="1196" height="1048" alt="ComfyUI-XMP-Tagger_v100_mainview_01" src="https://github.com/user-attachments/assets/c68b9753-3630-488c-96bc-16f1437430df" />

<a href="[DEIN_BILD_PFAD.png](https://github.com/user-attachments/assets/c68b9753-3630-488c-96bc-16f1437430df)">
  <img src="[DEIN_BILD_PFAD.png](https://github.com/user-attachments/assets/c68b9753-3630-488c-96bc-16f1437430df)" alt="App Preview" width="400">
</a>
---

## 💡 Why use ComfyUI XMP Tagger?

AI image generators like ComfyUI embed detailed generation parameters (prompts, models, samplers) inside PNG files, but standard photo managers cannot read or index this internal data. 

**ComfyUI XMP Tagger** bridges this gap:
1. It reads the embedded prompt API execution graph and UI nodes losslessly.
2. It extracts checkpoints, LoRAs, samplers, and prompts.
3. It converts them into standard hierarchical XMP keywords (e.g., `Model/juggernaut`, `Lora/detail_enhancer`).
4. Once processed, you can import your images into photo managers to instantly search, filter, and organize your generated images by their exact generation parameters!

---

## ⚡ Core Features

* **🚀 Ultra-Fast Byte-Level Editing (`embed` mode)**: Direct binary PNG chunk editor. Modifies metadata chunks in just **30ms per image** without decompressing or re-encoding pixels. Completely lossless and preserves existing star ratings.
* **📂 Sidecar Support (`sidecar` mode)**: Option to generate separate `.xmp` sidecar files in the same folder instead of modifying the PNG files directly.
* **🔍 Integrated Workflow Analyzer**: Inspect ComfyUI workflows of any sample image inside the app. Easily discover and click shortcut buttons to inject custom prompt field names, node IDs, or widget keys into your config.
* **🔤 Word-Based Prompt Tagging**: Automatically tokenizes entire prompts into individual tags. Filters out stopwords using custom word lists.
* **🏷️ Customizable Dictionaries**: Easily edit stopwords (`stopwords.txt`), adjective merges (`adjectives.txt`), and short-word exceptions (`short_words.txt`) directly through direct links in the UI.
* **🎨 Resolution Megapixel Tiers**: Automatically tags images with resolution categories (e.g., standard, upscale) and couples them with the standardized EXIF `ExposureProgram` field for easy tooltips in DigiKam.
* **🛡️ Windows GDI Safety**: Features a high-performance single-widget virtual file listbox. Safe from Windows GDI handle exhaustion, ensuring 100% stability even with folders of 10,000+ images.
* **💾 Presets & Persistence**: Save and load custom tagging rules with quick-save support. The app remembers your window size, position, slider ratio, and last active preset on launch.

---

## 🛠️ Installation & Setup

### Prerequisites
* **Windows OS** (optimized for Windows GDI handle safety).
* **Python 3.10** or newer. Make sure to check **"Add Python to PATH"** during installation.

### Quick Start (Launchers)
1. Download the latest release from the [Release Page](releases/V1.0.0.0).
2. Extract the files.
3. Double-click `Start.vbs` to launch the application completely hidden in the background (no console windows flashing).
   * *Alternatively, you can run `Start.bat` to see the setup console.*

### Manual Installation
If you prefer to run it via command line:
1. Clone the repository or navigate to the directory:
   ```bash
   cd comfyui-xmp-tagger
   ```
2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the application:
   ```bash
   python main.py
   ```

---

## 📖 How to Use

1. **Select Folder**: Browse to your target ComfyUI PNG directory. Toggle `Recursive` if you want to include subfolders.
2. **Scan**: Click **Scan Folder** to load the files. Check the listbox to verify warnings or existing XMP tags.
3. **Configure Rules**: In the **Settings & Tag Rules** tab, customize which parameters to extract (Models, LoRAs, Samplers, Prompts) and set their prefixes.
4. **Inspect Workflow (Optional)**: If some prompts are not loading, load an image in the **Workflow Analyzer** tab and click `+ ID` or `+ Key` to teach the tagger where your prompt text is stored.
5. **Apply**: Click **⚡ Apply XMP tags** to begin batch processing.

---

## 📚 Documentation & References

* [**Technical Manual & Architecture Guide**](TECHNICAL_MANUAL.md): Explains the binary PNG chunk editor, ComfyUI graph parsing algorithms, GDI handle limit safety, and project file structure.
* [**Version Documentation**](VERSION_DOCS.txt): Detailed user guide and feature summary written in German.
* [**Changelog & Milestones**](CHANGELOG.md): History of version iterations, milestones, and bug fixes.

---

## 📄 License

This project is licensed under the GPL-3.0 License - see the [LICENSE](LICENSE) file for details.
