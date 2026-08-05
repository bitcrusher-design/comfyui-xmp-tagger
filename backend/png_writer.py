import os
import shutil
import tempfile
import re
import xml.etree.ElementTree as ET
from xml.dom import minidom
from typing import Optional
import struct
import zlib

def strip_tags_from_xmp_xml(raw_xml_str: str) -> Optional[str]:
    """
    Strips all tag/keyword elements (e.g. hierarchicalSubject, TagsList, subject, LastKeywordXMP, Keywords)
    across all Description blocks in an XMP XML packet, while preserving all other metadata (e.g. xmp:Rating, digiKam:ColorLabel).
    Returns None if no non-tag metadata remains.
    """
    try:
        RDF_NS = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
        cleaned_xml = re.sub(r'<\?xpacket.*?\?>', '', raw_xml_str, flags=re.DOTALL).strip()
        if not cleaned_xml:
            return None

        root = ET.fromstring(cleaned_xml)
        descriptions = root.findall(f".//{{{RDF_NS}}}Description")
        if not descriptions:
            return None

        has_any_remaining = False

        for desc in descriptions:
            # Remove tag elements
            to_remove = []
            for child in list(desc):
                tag_name_lower = child.tag.lower()
                if any(bad in tag_name_lower for bad in ["subject", "tags", "keyword"]):
                    to_remove.append(child)

            for child in to_remove:
                desc.remove(child)

            # Check if any child elements or attributes remain on this Description block
            remaining_children = list(desc)
            remaining_attribs = list(desc.attrib.keys())
            has_substantive_attribs = any("about" not in a for a in remaining_attribs)

            if remaining_children or has_substantive_attribs:
                has_any_remaining = True

        if not has_any_remaining:
            return None

        # Register namespaces to keep pretty XML prefixes standard
        ET.register_namespace("xmp", "http://ns.adobe.com/xap/1.0/")
        ET.register_namespace("rdf", "http://www.w3.org/1999/02/22-rdf-syntax-ns#")
        ET.register_namespace("dc", "http://purl.org/dc/elements/1.1/")
        ET.register_namespace("lr", "http://ns.adobe.com/lightroom/1.0/")
        ET.register_namespace("digiKam", "http://www.digikam.org/ns/1.0/")
        ET.register_namespace("x", "adobe:ns:meta/")

        rough_string = ET.tostring(root, "utf-8")
        reparsed = minidom.parseString(rough_string)
        pretty_xml = reparsed.toprettyxml(indent="  ")

        header = '<?xpacket begin="\ufeff" id="W5M0MpCehiHzreSzNTczkc9d"?>\n'
        footer = '<?xpacket end="w"?>'
        return header + pretty_xml + footer
    except Exception:
        return None

def embed_xmp_in_png(
    image_path: str,
    xmp_xml: str,
    backup: bool = False,
    exposure_program: Optional[str] = None,
    checkpoint_model: Optional[str] = None,
    sampler_scheduler: Optional[str] = None,
    lens_model: Optional[str] = None
) -> bool:
    """
    Embeds the XMP XML string as an 'iTXt' chunk with keyword 'XML:com.adobe.xmp' into the PNG image.
    If exposure_program, checkpoint_model, sampler_scheduler, or lens_model is provided,
    also embeds/updates the binary 'eXIf' chunk.
    This editor performs byte-level chunk manipulation, which is extremely fast and completely avoids
    pixel data re-compression.
    """
    if not os.path.exists(image_path):
        return False

    temp_path = None
    try:
        png_signature = b"\x89PNG\r\n\x1a\n"
        existing_exif_data = None
        
        # Read the entire file and parse chunks
        with open(image_path, "rb") as f:
            signature = f.read(8)
            if signature != png_signature:
                raise ValueError("Not a valid PNG file")
                
            chunks = []
            while True:
                length_bytes = f.read(4)
                if not length_bytes:
                    break
                length = struct.unpack(">I", length_bytes)[0]
                chunk_type = f.read(4)
                chunk_data = f.read(length)
                crc_bytes = f.read(4)
                
                # Check for existing XMP chunks (either iTXt or tEXt with keyword XML:com.adobe.xmp)
                is_filtered = False
                if chunk_type in (b"iTXt", b"tEXt"):
                    if chunk_data.startswith(b"XML:com.adobe.xmp\x00"):
                        is_filtered = True
                elif chunk_type == b"eXIf":
                    existing_exif_data = chunk_data
                    is_filtered = True
                
                if not is_filtered:
                    chunks.append((chunk_type, chunk_data))
                    
                if chunk_type == b"IEND":
                    break
                    
        # Construct the new uncompressed iTXt chunk for XMP metadata
        xmp_keyword = b"XML:com.adobe.xmp\x00"
        flags_and_nulls = b"\x00\x00\x00\x00" # Compression=0, Method=0, Lang='', Trans=''
        xmp_chunk_data = xmp_keyword + flags_and_nulls + xmp_xml.encode("utf-8")
        
        # Generate new EXIF chunk if any parameter is specified, or preserve existing EXIF
        exif_bytes = None
        if exposure_program or checkpoint_model or sampler_scheduler or lens_model:
            try:
                from PIL import Image
                img = Image.new("RGB", (1, 1))
                if existing_exif_data:
                    img.info['exif'] = b"Exif\x00\x00" + existing_exif_data
                exif = img.getexif()
                
                # Write main IFD0 tags
                if checkpoint_model:
                    exif[271] = checkpoint_model # Make (Checkpoint Model first)
                if sampler_scheduler:
                    exif[272] = sampler_scheduler # Model (Sampler + Scheduler second)
                    
                # Write SubIFD tags
                sub_ifd = exif.get_ifd(0x8769)
                
                if lens_model:
                    sub_ifd[0xa434] = lens_model # LensModel
                    
                # Clean up any legacy ExposureProgram tags to keep it empty
                if 0x8822 in sub_ifd:
                    del sub_ifd[0x8822]
                if 34850 in exif:
                    del exif[34850]
                    
                # Link SubIFD back to IFD0 if it has contents
                if sub_ifd:
                    exif[0x8769] = sub_ifd
                
                eb = exif.tobytes()
                if eb.startswith(b"Exif\x00\x00"):
                    eb = eb[6:]
                exif_bytes = eb
            except Exception as e:
                print(f"Error generating EXIF bytes with existing data: {e}")
                try:
                    # Fallback: Create a clean EXIF chunk without merging existing un-serializable EXIF
                    img = Image.new("RGB", (1, 1))
                    exif = img.getexif()
                    if checkpoint_model:
                        exif[271] = checkpoint_model
                    if sampler_scheduler:
                        exif[272] = sampler_scheduler
                    
                    sub_ifd = {}
                    if lens_model:
                        sub_ifd[0xa434] = lens_model
                        exif[0x8769] = sub_ifd
                        
                    eb = exif.tobytes()
                    if eb.startswith(b"Exif\x00\x00"):
                        eb = eb[6:]
                    exif_bytes = eb
                except Exception as ex_err:
                    print(f"Error generating fallback EXIF bytes: {ex_err}")
        elif existing_exif_data:
            exif_bytes = existing_exif_data

        # Write chunks to a temporary file
        dir_name = os.path.dirname(os.path.abspath(image_path))
        with tempfile.NamedTemporaryFile(delete=False, dir=dir_name, suffix=".png") as temp_file:
            temp_path = temp_file.name
            
            temp_file.write(png_signature)
            
            ihdr_written = False
            for chunk_type, chunk_data in chunks:
                length = len(chunk_data)
                temp_file.write(struct.pack(">I", length))
                temp_file.write(chunk_type)
                temp_file.write(chunk_data)
                
                crc = zlib.crc32(chunk_type + chunk_data) & 0xffffffff
                temp_file.write(struct.pack(">I", crc))
                
                # Insert the new XMP chunk and eXIf chunk right after IHDR
                if chunk_type == b"IHDR" and not ihdr_written:
                    xmp_length = len(xmp_chunk_data)
                    temp_file.write(struct.pack(">I", xmp_length))
                    temp_file.write(b"iTXt")
                    temp_file.write(xmp_chunk_data)
                    
                    xmp_crc = zlib.crc32(b"iTXt" + xmp_chunk_data) & 0xffffffff
                    temp_file.write(struct.pack(">I", xmp_crc))
                    
                    if exif_bytes:
                        exif_len = len(exif_bytes)
                        temp_file.write(struct.pack(">I", exif_len))
                        temp_file.write(b"eXIf")
                        temp_file.write(exif_bytes)
                        
                        exif_crc = zlib.crc32(b"eXIf" + exif_bytes) & 0xffffffff
                        temp_file.write(struct.pack(">I", exif_crc))

                    ihdr_written = True

        if backup:
            backup_path = image_path + ".bak"
            if not os.path.exists(backup_path):
                shutil.copy2(image_path, backup_path)

        os.replace(temp_path, image_path)
        return True

    except Exception as e:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass
        print(f"Error embedding XMP in {image_path}: {e}")
        return False

def write_xmp_sidecar(image_path: str, xmp_xml: str) -> bool:
    """
    Writes a standalone .xmp sidecar file next to the image.
    """
    sidecar_path = image_path + ".xmp"
    try:
        with open(sidecar_path, "w", encoding="utf-8") as f:
            f.write(xmp_xml)
        return True
    except Exception as e:
        print(f"Error writing XMP sidecar {sidecar_path}: {e}")
        return False

def remove_xmp_tags_from_file(image_path: str, mode: str = "embed") -> bool:
    """
    Removes XMP tags from a PNG image or .xmp sidecar file while preserving non-tag metadata (ratings, dates).
    If mode == "embed", updates or strips the XMP chunk in the PNG using binary byte manipulation.
    If mode == "sidecar", updates or deletes the .xmp sidecar file.
    """
    if not os.path.exists(image_path):
        return False

    if mode == "embed":
        temp_path = None
        try:
            png_signature = b"\x89PNG\r\n\x1a\n"
            
            raw_xmp = None
            chunks = []
            
            with open(image_path, "rb") as f:
                signature = f.read(8)
                if signature != png_signature:
                    raise ValueError("Not a valid PNG file")
                    
                while True:
                    length_bytes = f.read(4)
                    if not length_bytes:
                        break
                    length = struct.unpack(">I", length_bytes)[0]
                    chunk_type = f.read(4)
                    chunk_data = f.read(length)
                    crc_bytes = f.read(4)
                    
                    is_xmp = False
                    if chunk_type in (b"iTXt", b"tEXt"):
                        if chunk_data.startswith(b"XML:com.adobe.xmp\x00"):
                            is_xmp = True
                            if chunk_type == b"iTXt":
                                if len(chunk_data) > 22:
                                    raw_xmp = chunk_data[22:].decode("utf-8", errors="ignore")
                            else:
                                # tEXt format does not have flags, text starts right after null-terminated keyword
                                if len(chunk_data) > 18:
                                    raw_xmp = chunk_data[18:].decode("utf-8", errors="ignore")
                                
                    if not is_xmp:
                        chunks.append((chunk_type, chunk_data))
                        
                    if chunk_type == b"IEND":
                        break
            
            cleaned_xmp = None
            if raw_xmp:
                cleaned_xmp = strip_tags_from_xmp_xml(raw_xmp)
                
            dir_name = os.path.dirname(os.path.abspath(image_path))
            with tempfile.NamedTemporaryFile(delete=False, dir=dir_name, suffix=".png") as temp_file:
                temp_path = temp_file.name
                
                temp_file.write(png_signature)
                
                ihdr_written = False
                for chunk_type, chunk_data in chunks:
                    length = len(chunk_data)
                    temp_file.write(struct.pack(">I", length))
                    temp_file.write(chunk_type)
                    temp_file.write(chunk_data)
                    
                    crc = zlib.crc32(chunk_type + chunk_data) & 0xffffffff
                    temp_file.write(struct.pack(">I", crc))
                    
                    if chunk_type == b"IHDR" and cleaned_xmp and not ihdr_written:
                        xmp_keyword = b"XML:com.adobe.xmp\x00"
                        flags_and_nulls = b"\x00\x00\x00\x00"
                        xmp_chunk_data = xmp_keyword + flags_and_nulls + cleaned_xmp.encode("utf-8")
                        
                        xmp_length = len(xmp_chunk_data)
                        temp_file.write(struct.pack(">I", xmp_length))
                        temp_file.write(b"iTXt")
                        temp_file.write(xmp_chunk_data)
                        
                        xmp_crc = zlib.crc32(b"iTXt" + xmp_chunk_data) & 0xffffffff
                        temp_file.write(struct.pack(">I", xmp_crc))
                        ihdr_written = True
                        
            os.replace(temp_path, image_path)
            return True
            
        except Exception as e:
            if temp_path and os.path.exists(temp_path):
                try: os.remove(temp_path)
                except Exception: pass
            print(f"Error removing XMP tags from {image_path}: {e}")
            return False

    elif mode == "sidecar":
        sidecar_path = image_path + ".xmp"
        if not os.path.exists(sidecar_path):
            return True
        try:
            with open(sidecar_path, "r", encoding="utf-8", errors="ignore") as f:
                raw_xmp = f.read()

            cleaned_xmp = strip_tags_from_xmp_xml(raw_xmp)
            if cleaned_xmp:
                with open(sidecar_path, "w", encoding="utf-8") as f:
                    f.write(cleaned_xmp)
            else:
                os.remove(sidecar_path)
            return True
        except Exception as e:
            print(f"Error removing XMP sidecar tags from {sidecar_path}: {e}")
            return False

    return False
