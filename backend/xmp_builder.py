import xml.etree.ElementTree as ET
from xml.dom import minidom
from typing import List, Dict, Tuple, Optional
from backend.comfy_parser import ComfyMetadata

class XMPConfig:
    def __init__(
        self,
        include_models: bool = True,
        include_loras: bool = True,
        include_samplers: bool = True,
        include_prompts: bool = True,
        include_resolution: bool = True,
        prefix_model: str = "Model",
        prefix_lora: str = "Lora",
        prefix_prompt: str = "Prompt",
        prefix_sampler: str = "Sampler",
        prefix_resolution: str = "Resolution",
        res_tier1_mp: float = 1.0,
        res_tier1_name: str = "Preview",
        res_tier2_mp: float = 2.5,
        res_tier2_name: str = "Standard",
        res_tier3_name: str = "Upscale",
        write_flat_dc: bool = True,
        overwrite_existing_tags: bool = False,
        write_created_date: bool = False,
        write_camera_model: bool = False,
        write_description: bool = False,
        custom_creator: str = "",
        custom_copyright: str = "",
        custom_camera_make: str = "",
        custom_software: str = "",
        custom_comment: str = "",
        lowercase_prompt_tags: bool = False
    ):
        self.include_models = include_models
        self.include_loras = include_loras
        self.include_samplers = include_samplers
        self.include_prompts = include_prompts
        self.include_resolution = include_resolution
        self.prefix_model = prefix_model
        self.prefix_lora = prefix_lora
        self.prefix_prompt = prefix_prompt
        self.prefix_sampler = prefix_sampler
        self.prefix_resolution = prefix_resolution
        self.res_tier1_mp = res_tier1_mp
        self.res_tier1_name = res_tier1_name
        self.res_tier2_mp = res_tier2_mp
        self.res_tier2_name = res_tier2_name
        self.res_tier3_name = res_tier3_name
        self.write_flat_dc = write_flat_dc
        self.overwrite_existing_tags = overwrite_existing_tags
        self.write_created_date = write_created_date
        self.write_camera_model = write_camera_model
        self.write_description = write_description
        self.custom_creator = custom_creator
        self.custom_copyright = custom_copyright
        self.custom_camera_make = custom_camera_make
        self.custom_software = custom_software
        self.custom_comment = custom_comment
        self.lowercase_prompt_tags = lowercase_prompt_tags

def generate_xmp_tags(meta: ComfyMetadata, config: XMPConfig) -> Tuple[List[str], List[str]]:
    """
    Generates (flat_tags, hierarchical_tags) tuples from ComfyMetadata
    and preserves/merges all existing XMP tags already present in the image.
    """
    flat_tags: List[str] = []
    hierarchical_tags: List[str] = []

    # 1. Models / Checkpoints
    if config.include_models:
        for ckpt in meta.checkpoints:
            flat_tags.append(ckpt)
            hierarchical_tags.append(f"{config.prefix_model}/{ckpt}")

    # 2. LoRAs
    if config.include_loras:
        for lora in meta.loras:
            flat_tags.append(lora)
            hierarchical_tags.append(f"{config.prefix_lora}/{lora}")

    # 3. Samplers & Schedulers
    if config.include_samplers:
        for idx, s in enumerate(meta.samplers):
            if idx < len(meta.schedulers):
                sch = meta.schedulers[idx]
                tag_val = f"{s} / {sch}"
            else:
                tag_val = s
            flat_tags.append(tag_val)
            hierarchical_tags.append(f"{config.prefix_sampler}/{tag_val}")

    # 4. Resolution Tiers (Megapixel tags)
    if config.include_resolution and meta.width and meta.height:
        mp = (meta.width * meta.height) / 1000000.0
        if mp < config.res_tier1_mp:
            res_tag = config.res_tier1_name
        elif mp < config.res_tier2_mp:
            res_tag = config.res_tier2_name
        else:
            res_tag = config.res_tier3_name

        if res_tag and res_tag.strip():
            flat_tags.append(res_tag.strip())
            hierarchical_tags.append(f"{config.prefix_resolution}/{res_tag.strip()}")

    # 5. Prompts
    if config.include_prompts:
        for tag in meta.prompt_tags:
            flat_tags.append(tag)
            hierarchical_tags.append(f"{config.prefix_prompt}/{tag}")

    # 6. Merge Existing XMP Tags (Preserve all pre-existing tags if not overwriting!)
    if not config.overwrite_existing_tags and meta.has_existing_xmp and meta.existing_xmp_tags:
        for ex_tag in meta.existing_xmp_tags:
            ex_tag = ex_tag.strip()
            if not ex_tag:
                continue
            if "/" in ex_tag:
                hierarchical_tags.append(ex_tag)
                leaf = ex_tag.rsplit("/", 1)[-1]
                if leaf:
                    flat_tags.append(leaf)
            else:
                flat_tags.append(ex_tag)
                hierarchical_tags.append(ex_tag)

    # Deduplicate while preserving order
    flat_tags = list(dict.fromkeys(flat_tags))
    hierarchical_tags = list(dict.fromkeys(hierarchical_tags))

    return flat_tags, hierarchical_tags

import re

def generate_xmp_payload(meta: ComfyMetadata, config: XMPConfig) -> Tuple[str, List[str], List[str]]:
    """
    Generates a full RDF/XML packet string for XMP embedding (DigiKam compatible),
    along with the list of flat and hierarchical tags. Preserves all non-tag metadata
    such as xmp:Rating (DigiKam star ratings), digiKam:ColorLabel, and creation dates.
    """
    flat_tags, hierarchical_tags = generate_xmp_tags(meta, config)

    # Register XML Namespaces
    X_NS = "adobe:ns:meta/"
    RDF_NS = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
    DC_NS = "http://purl.org/dc/elements/1.1/"
    LR_NS = "http://ns.adobe.com/lightroom/1.0/"
    DIGIKAM_NS = "http://www.digikam.org/ns/1.0/"
    XMP_NS = "http://ns.adobe.com/xap/1.0/"
    TIFF_NS = "http://ns.adobe.com/tiff/1.0/"
    EXIF_NS = "http://ns.adobe.com/exif/1.0/"
    XMPRIGHTS_NS = "http://ns.adobe.com/xap/1.0/rights/"

    ET.register_namespace("x", X_NS)
    ET.register_namespace("rdf", RDF_NS)
    ET.register_namespace("dc", DC_NS)
    ET.register_namespace("lr", LR_NS)
    ET.register_namespace("digiKam", DIGIKAM_NS)
    ET.register_namespace("xmp", XMP_NS)
    ET.register_namespace("tiff", TIFF_NS)
    ET.register_namespace("exif", EXIF_NS)
    ET.register_namespace("xmpRights", XMPRIGHTS_NS)

    root = None
    desc = None

    # If the image already contains raw XMP metadata, parse and preserve all existing nodes (e.g. ratings, labels)
    if meta.has_existing_xmp and meta.raw_xmp_str:
        try:
            cleaned_xml = re.sub(r'<\?xpacket.*?\?>', '', meta.raw_xmp_str, flags=re.DOTALL).strip()
            if cleaned_xml:
                parsed_root = ET.fromstring(cleaned_xml)
                parsed_desc = parsed_root.find(f".//{{{RDF_NS}}}Description")
                if parsed_desc is not None:
                    root = parsed_root
                    desc = parsed_desc
                    # Remove only existing tag containers to replace them with merged lists
                    to_remove = []
                    for child in list(desc):
                        tag_name = child.tag
                        if any(bad in tag_name for bad in ["hierarchicalSubject", "TagsList", "subject"]):
                            to_remove.append(child)
                        if config.write_created_date and "CreateDate" in tag_name:
                            to_remove.append(child)
                        if config.write_camera_model and "Model" in tag_name:
                            to_remove.append(child)
                        if config.write_description and "description" in tag_name:
                            to_remove.append(child)
                        if config.custom_creator and "creator" in tag_name:
                            to_remove.append(child)
                        if config.custom_copyright and "rights" in tag_name:
                            to_remove.append(child)
                        if config.custom_camera_make and "Make" in tag_name:
                            to_remove.append(child)
                        if config.custom_software and "CreatorTool" in tag_name:
                            to_remove.append(child)
                        if config.custom_comment and "UserComment" in tag_name:
                            to_remove.append(child)
                    for child in to_remove:
                        try:
                            desc.remove(child)
                        except ValueError:
                            pass
                    
                    if config.write_created_date:
                        desc.attrib.pop(f"{{{XMP_NS}}}CreateDate", None)
                    if config.write_camera_model:
                        desc.attrib.pop(f"{{{TIFF_NS}}}Model", None)
                    if config.write_description:
                        desc.attrib.pop(f"{{{DC_NS}}}description", None)
                    if config.custom_creator:
                        desc.attrib.pop(f"{{{DC_NS}}}creator", None)
                    if config.custom_copyright:
                        desc.attrib.pop(f"{{{DC_NS}}}rights", None)
                    if config.custom_camera_make:
                        desc.attrib.pop(f"{{{TIFF_NS}}}Make", None)
                    if config.custom_software:
                        desc.attrib.pop(f"{{{XMP_NS}}}CreatorTool", None)
                    if config.custom_comment:
                        desc.attrib.pop(f"{{{EXIF_NS}}}UserComment", None)
        except Exception:
            root = None
            desc = None

    # Fallback: Create new XMP structure if no existing XML could be parsed
    if root is None or desc is None:
        xmpmeta = ET.Element(f"{{{X_NS}}}xmpmeta", {f"{{{X_NS}}}xmptk": "ComfyUI XMP Tagger v1.0"})
        rdf = ET.SubElement(xmpmeta, f"{{{RDF_NS}}}RDF")
        desc = ET.SubElement(rdf, f"{{{RDF_NS}}}Description", {
            f"{{{RDF_NS}}}about": "",
        })
        root = xmpmeta

    # 1. lr:hierarchicalSubject (DigiKam / Lightroom Tree Tags)
    if hierarchical_tags:
        lr_hsub = ET.SubElement(desc, f"{{{LR_NS}}}hierarchicalSubject")
        lr_bag = ET.SubElement(lr_hsub, f"{{{RDF_NS}}}Bag")
        for tag in hierarchical_tags:
            li = ET.SubElement(lr_bag, f"{{{RDF_NS}}}li")
            li.text = tag

        # Also populate digiKam:TagsList for native DigiKam compatibility
        dk_tags = ET.SubElement(desc, f"{{{DIGIKAM_NS}}}TagsList")
        dk_seq = ET.SubElement(dk_tags, f"{{{RDF_NS}}}Seq")
        for tag in hierarchical_tags:
            li = ET.SubElement(dk_seq, f"{{{RDF_NS}}}li")
            li.text = tag

    # 2. dc:subject (Flat Keywords)
    if config.write_flat_dc and flat_tags:
        dc_subj = ET.SubElement(desc, f"{{{DC_NS}}}subject")
        dc_bag = ET.SubElement(dc_subj, f"{{{RDF_NS}}}Bag")
        for tag in flat_tags:
            li = ET.SubElement(dc_bag, f"{{{RDF_NS}}}li")
            li.text = tag

    # 3. xmp:CreateDate
    if config.write_created_date and meta.creation_date:
        elem = ET.SubElement(desc, f"{{{XMP_NS}}}CreateDate")
        elem.text = meta.creation_date

    # 4. tiff:Model
    if config.write_camera_model and meta.checkpoints:
        elem = ET.SubElement(desc, f"{{{TIFF_NS}}}Model")
        elem.text = meta.checkpoints[0]

    # 5. dc:description
    if config.write_description and meta.positive_prompts:
        merged_prompts = "\n\n".join(meta.positive_prompts)
        dc_desc = ET.SubElement(desc, f"{{{DC_NS}}}description")
        rdf_alt = ET.SubElement(dc_desc, f"{{{RDF_NS}}}Alt")
        li = ET.SubElement(rdf_alt, f"{{{RDF_NS}}}li", {f"{{http://www.w3.org/XML/1998/namespace}}lang": "x-default"})
        li.text = merged_prompts

    # 6. dc:creator
    if config.custom_creator:
        creator_elem = ET.SubElement(desc, f"{{{DC_NS}}}creator")
        seq_elem = ET.SubElement(creator_elem, f"{{{RDF_NS}}}Seq")
        li_elem = ET.SubElement(seq_elem, f"{{{RDF_NS}}}li")
        li_elem.text = config.custom_creator

    # 7. dc:rights (Copyright)
    if config.custom_copyright:
        rights_elem = ET.SubElement(desc, f"{{{DC_NS}}}rights")
        alt_elem = ET.SubElement(rights_elem, f"{{{RDF_NS}}}Alt")
        li_elem = ET.SubElement(alt_elem, f"{{{RDF_NS}}}li", {f"{{http://www.w3.org/XML/1998/namespace}}lang": "x-default"})
        li_elem.text = config.custom_copyright

    # 8. tiff:Make
    if config.custom_camera_make:
        elem = ET.SubElement(desc, f"{{{TIFF_NS}}}Make")
        elem.text = config.custom_camera_make

    # 9. xmp:CreatorTool
    if config.custom_software:
        elem = ET.SubElement(desc, f"{{{XMP_NS}}}CreatorTool")
        elem.text = config.custom_software

    # 10. exif:UserComment
    if config.custom_comment:
        comment_elem = ET.SubElement(desc, f"{{{EXIF_NS}}}UserComment")
        alt_elem = ET.SubElement(comment_elem, f"{{{RDF_NS}}}Alt")
        li_elem = ET.SubElement(alt_elem, f"{{{RDF_NS}}}li", {f"{{http://www.w3.org/XML/1998/namespace}}lang": "x-default"})
        li_elem.text = config.custom_comment



    rough_string = ET.tostring(root, "utf-8")
    reparsed = minidom.parseString(rough_string)
    pretty_xml = reparsed.toprettyxml(indent="  ")

    header = '<?xpacket begin="\ufeff" id="W5M0MpCehiHzreSzNTczkc9d"?>\n'
    footer = '<?xpacket end="w"?>'
    full_xmp = header + pretty_xml + footer

    return full_xmp, flat_tags, hierarchical_tags

