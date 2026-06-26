import os
import time
import traceback
import shutil
import re
import random
import string
from datetime import datetime
from db import (
    insert_artwork,
    link_artwork_to_product,
    get_artwork_id_by_filename,
    get_artwork_details,
    get_product,
    insert_product,
    seed_artwork_requirements
)

# ---------------- CONFIG ---------------- #

LOG_FILE = "rename_log.txt"

# ---------------- LOGGING ---------------- #

def log(msg):
    print(msg)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

# ---------------- HELPERS ---------------- #

def remove_batch_from_filename(filename):

    parts = filename.split("_", 1)

    if len(parts) != 2:
        return filename

    prefix = parts[0]

    # Keep valid dates
    if re.match(r'^\d{6}$', prefix):
        return filename

    if re.match(r'^\d{8}$', prefix):
        return filename

    # Remove only actual batch codes
    if prefix.isalnum() and any(char.isdigit() for char in prefix):
        return parts[1]

    return filename


def update_date_prefix(filename):
    """
    Add today's date only if no date prefix already exists.

    New standard:
        YYMMDD_

    Legacy formats recognised:
        YYMMDD-
        YYYYMMDD-
        YYMMDD_
        YYYYMMDD_

    """

    # Already has date prefix → leave unchanged
    if re.match(r'^(?:\d{6}|\d{8})[-_]', filename):
        return filename

    today = datetime.now().strftime("%y%m%d")

    return f"{today}_{filename}"


# ---------------- RENAME ---------------- #

def rename_folder_pdfs(folder, actions):

    rename_jobs = []

    for root, _, files in os.walk(folder):

        for filename in files:

            if not filename.lower().endswith(".pdf"):
                continue

            # Step 1: Remove batch prefix
            new_name = remove_batch_from_filename(filename)

            # Step 2: Replace/add date prefix
            new_name = update_date_prefix(new_name)

            if new_name != filename:
                rename_jobs.append((root, filename, new_name))

    time.sleep(1)

    for root, old_name, new_name in rename_jobs:

        old_path = os.path.join(root, old_name)

        if not os.path.exists(old_path):
            actions.append(f"[SKIPPED] Missing: {old_name}")
            continue

        new_path = os.path.join(root, new_name)

        counter = 1
        final_path = new_path

        while os.path.exists(final_path):
            name, ext = os.path.splitext(new_name)
            final_path = os.path.join(root, f"{name}_{counter}{ext}")
            counter += 1

        try:
            os.rename(old_path, final_path)

            actions.append(
                f"[RENAMED] {old_name} → {os.path.basename(final_path)}"
            )

        except Exception as e:
            actions.append(f"[ERROR] {old_name}: {e}")

# ---------------- COPY SPECIAL FILES ---------------- #

def copy_special_files(folder, actions):

    parent_dir = os.path.dirname(folder)

    production_tag_dir = os.path.join(parent_dir, "0 - PRODUCTIONTAGS")
    instructions_dir = os.path.join(parent_dir, "1 - INSTRUCTIONS")
    header_card_dir = os.path.join(parent_dir, "2 - HEADERCARDS")
    woven_label_dir = os.path.join(parent_dir, "3 - WOVENLABELS")

    os.makedirs(production_tag_dir, exist_ok=True)
    os.makedirs(instructions_dir, exist_ok=True)
    os.makedirs(header_card_dir, exist_ok=True)
    os.makedirs(woven_label_dir, exist_ok=True)

    for root, _, files in os.walk(folder):

        for filename in files:

            if not filename.lower().endswith(".pdf"):
                continue

            name_without_ext = os.path.splitext(filename)[0]
            segments = name_without_ext.split("_")
            segments_upper = [s.upper() for s in segments]

            dest_dir = None

            # ---- PRODUCTION TAG ---- #
            if any("PRODUCTION-TAG" in s for s in segments_upper):
                dest_dir = production_tag_dir

            # ---- HEADER CARD ---- #
            elif any("HEADER" in s and "CARD" in s for s in segments_upper):
                dest_dir = header_card_dir

            # ---- WOVEN LABEL ---- #
            elif any("WOVEN" in s and "LABEL" in s for s in segments_upper):
                dest_dir = woven_label_dir

            # ---- INSTRUCTION ---- #
            elif any("INSTRUCTION" in s for s in segments_upper):
                dest_dir = instructions_dir

            else:
                actions.append(f"[IGNORED] {filename}")
                continue

            src_path = os.path.join(root, filename)
            dest_path = os.path.join(dest_dir, filename)

            if os.path.exists(dest_path):
                actions.append(f"[SKIPPED] Exists: {filename}")
                continue

            try:
                shutil.copy2(src_path, dest_path)

                actions.append(
                    f"[COPIED] {filename} → {os.path.basename(dest_dir)}"
                )

            except Exception as e:
                actions.append(f"[ERROR] {filename}: {e}")


# ---------------- GENERATE RANDOM STRING ---------------- #
def generate_upload_id():

    date_part = datetime.now().strftime("%y%m")

    random_part = ''.join(
        random.choices(
            string.ascii_uppercase + string.digits,
            k=4
        )
    )

    return f"{date_part}{random_part}"

# ---------------- RETRIEVE PRODUCT NAME AND CODE FROM FOLDER PATH ---------------- #

def get_product_from_path(folder_path):

    folder_name = os.path.basename(folder_path)

    match = re.search(
        r'(.+?)\s*-\s*(\d[\d-]*)$',
        folder_name
    )

    if not match:
        return None, None

    product_name = match.group(1).strip()
    product_code = match.group(2).strip()

    return product_code, product_name

# ---------------- EXTRACT ARTWORK TYPE ---------------- #

def extract_artwork_type(parts, product_index):

    after_code = parts[product_index + 1:]

    # Remove resolution
    if after_code and after_code[-1] in ["HR", "LR"]:
        after_code = after_code[:-1]

    # Remove Combined
    if after_code and after_code[-1].upper() == "COMBINED":
        after_code = after_code[:-1]

    # Remove revision
    if after_code:
        after_code = after_code[:-1]

    # Remove variant
    if after_code:
        after_code = after_code[:-1]

    return "_".join(after_code)

    # remaining = parts[product_index + 1:]

    # # remove resolution
    # if remaining and remaining[-1] in ["HR", "LR"]:
    #     remaining.pop()

    # # remove revision
    # if remaining and re.match(r'^[A-Z]$', remaining[-1]):
    #     remaining.pop()

    # # remove variant
    # if remaining and re.match(r'^\d+$', remaining[-1]):
    #     remaining.pop()

    # if not remaining:
    #     return None

    # return "_".join(remaining)

# ---------------- EXTRACT ARTWORK GROUP ---------------- #

def extract_artwork_group(parts, product_index):

    print("\nDEBUG PARTS")
    print(parts)

    variant_index = None

    for i in range(product_index + 1, len(parts)):

        # Find variant code (000, 001, 002, etc.)
        if re.match(r'^\d{3}$', parts[i]):
            variant_index = i
            break

    if variant_index is None:
        return None

    return "_".join(
        parts[product_index + 1:variant_index]
    )

# ---------------- PARSE FILENAME ---------------- #

# new parser function
def parse_filename(filename):

    name = os.path.splitext(filename)[0]

    parts = name.split("_")

    # release date
    try:
        release_date = datetime.strptime(
            parts[0],
            "%y%m%d"
        ).date()
    except:
        return None

    product_index = None
    product_code = None

    for i, part in enumerate(parts):

        # 0199920
        # 0199920-000
        # 0266631-33
        # 0266612-13-22-23
        # 0256504-002-0266505-001

        if re.match(
            r'^\d{7}(?:-\d+)*$',
            part
        ):
            product_index = i
            product_code = part
            break

    if not product_code:

        # Find variant (001 / 000 / 00100 etc.)
        variant_index = None

        for i, part in enumerate(parts):

            if re.fullmatch(r"\d{3,5}", part):
                variant_index = i
                break

        if variant_index:
            artwork_type = "_".join(parts[2:variant_index])
        else:
            artwork_type = "_".join(parts[2:])

        print(f"DEBUG artwork_type = {artwork_type}")

        artwork_group = get_artwork_group(artwork_type)

        return {
            "release_date": release_date,
            "base_product_code": None,
            "product_variant": None,
            "full_product_code": None,
            "artwork_group": artwork_group,
            "is_combined": True
        }

    # if not product_code:

    #     artwork_type = (
    #         parts[-3]
    #         if len(parts) >= 3
    #         else None
    #     )

    #     artwork_group = get_artwork_group(
    #         artwork_type
    #     )

    #     return {
    #         "release_date": release_date,
    #         "base_product_code": None,
    #         "product_variant": None,
    #         "full_product_code": None,
    #         "artwork_group": artwork_group,
    #         "is_combined": True
    #     }

    artwork_type = extract_artwork_type(
        parts,
        product_index
    )

    # print("\nDEBUG")
    # print(filename)
    # print("artwork_type =", artwork_type)

    artwork_group = get_artwork_group(
        artwork_type
    )

    # Variant

    variant_match = re.search(
        r'-(\d{3})$',
        product_code
    )

    product_variant = (
        variant_match.group(1)
        if variant_match
        else "000"
    )

    base_product_code = product_code.split("-")[0]

    return {
        "release_date": release_date,
        "base_product_code": base_product_code,
        "product_variant": product_variant,
        "full_product_code": f"{base_product_code}-{product_variant}",
        "artwork_group": artwork_group,
        "is_combined": product_code.count("-") > 1
    }

# def parse_filename(filename):

#     name = os.path.splitext(filename)[0]

#     parts = name.split("_")

#     # Handle files without resolution suffix

#     if parts[-1].upper() not in ["HR", "LR"]:

#         print(
#             f"[NO RESOLUTION] {filename} -> Defaulting to HR"
#         )

#         parts.append("HR")

#     # Generic artwork
#     # Example:
#     # 260610_PE-Footprints_Generic-Instructions_B_HR

#     if len(parts) == 5:

#         return {
#             "release_date": datetime.strptime(
#                 parts[0],
#                 "%y%m%d"
#             ).date(),

#             "range_name": None,

#             "product_name": parts[1],

#             "base_product_code": None,

#             "product_variant": None,

#             "full_product_code": None,

#             "artwork_type": parts[2],

#             "revision_code": parts[3],

#             "resolution": parts[4],

#             "is_combined": True,

#             "combined_product_codes": []
#         }

#     # Minimum:
#     # 260603_Shapeshifter-6_Production-Tag_001_B_HR

#     if len(parts) < 5:
#         return None

#     # -------------------------
#     # DATE
#     # -------------------------

#     date_part = parts[0]

#     try:
#         release_date = datetime.strptime(
#             date_part,
#             "%y%m%d"
#         ).date()
#     except ValueError:
#         return None

#     # -------------------------
#     # RESOLUTION (optional)
#     # -------------------------

#     resolution = "HR"  # default

#     if parts[-1].upper() in ["HR", "LR"]:
#         resolution = parts.pop()

#     # -------------------------
#     # COMBINED or SHARED FLAGS
#     # -------------------------

#     is_combined = False
#     combined_product_codes = []

#     name_upper = name.upper()

#     is_combined = any(
#         k in name_upper
#         for k in ["COMBINED", "GENERIC"]
#     )

#     # Pattern:
#     # Product_0256504-002-0266505-001_Instruction-Booklet_B_HR

#     if (
#         len(parts) == 6
#         and re.match(
#             r'^\d{7}-\d{3}-\d{7}-\d{3}$',
#             parts[2]
#         )
#     ):

#         is_combined = True

#         revision_code = parts[-1]

#         variant_code = None

#         middle_parts = parts[1:-1]

#     # Pattern:
#     # Product_Generic-Instruction_B_Combined_HR

#     elif is_combined and len(parts) == 6:

#         revision_code = f"{parts[-2]} - Combined"

#         variant_code = None

#         middle_parts = parts[1:-2]

#     # Pattern:
#     # Product_Swing-Tag_001_B_Combined_HR

#     elif is_combined:

#         revision_code = f"{parts[-3]} - Combined"

#         variant_code = parts[-3]

#         middle_parts = parts[1:-3]

#     # Standard artwork

#     else:

#         revision_code = parts[-2]

#         variant_code = parts[-3]

#         middle_parts = parts[1:-3]

#     # -------------------------
#     # FIND PRODUCT CODE
#     # -------------------------

#     product_code = None

#     # print("\nDEBUG MIDDLE PARTS")
#     # print(filename)
#     # print(middle_parts)

#     for i, part in enumerate(middle_parts):

#         if re.match(r'^\d+(?:-\d+)*$', part):
#             product_code = part
#             product_code_index = i
#             break

#     # -------------------------
#     # FILE HAS PRODUCT CODE
#     # -------------------------

#     if product_code:

#         matches = re.findall(
#             r'\d{7}-\d{3}',
#             product_code
#         )


#         # Pattern:
#         # 0256504-002-0266505-001
#         if len(matches) > 1:

#             is_combined = True

#             combined_product_codes = matches

#             product_code = None
#             variant_code = None

#         # Pattern:
#         # 0266661-0266662
#         elif re.match(
#             r'^\d{7}-\d{7}$',
#             product_code
#         ):

#             is_combined = True

#             codes = product_code.split("-")

#             combined_product_codes = [
#                 f"{code}-{variant_code}"
#                 for code in codes
#             ]

#             product_code = None
#             variant_code = None

#         # Pattern:
#         # 0266661-62
#         # 0266612-13-22-23

#         elif re.match(
#             r'^\d{7}(?:-\d{2})+$',
#             product_code
#         ):

#             is_combined = True

#             first_code = product_code.split("-")[0]

#             prefix = first_code[:5]

#             suffixes = [
#                 first_code[5:]
#             ] + product_code.split("-")[1:]

#             combined_product_codes = [
#                 f"{prefix}{suffix}-{variant_code}"
#                 for suffix in suffixes
#             ]

#             product_code = None
#             variant_code = None

#     if product_code:

#         range_name = middle_parts[0]

#         product_name = "_".join(
#             middle_parts[:product_code_index]
#         )

#         artwork_type = "_".join(
#             middle_parts[product_code_index + 1:]
#         )

#     elif is_combined:

#         range_name = middle_parts[0]

#         product_name = "_".join(
#             middle_parts[:product_code_index]
#         ) if 'product_code_index' in locals() else None

#         artwork_type = "_".join(
#             middle_parts[product_code_index + 1:]
#         ) if 'product_code_index' in locals() else "_".join(middle_parts[1:])

#     else:

#         range_name = middle_parts[0]

#         # No product code found
#         # Treat first segment as product name
#         # and remainder as artwork type

#         if len(middle_parts) > 1:

#             product_name = middle_parts[0]

#             artwork_type = "_".join(
#                 middle_parts[1:]
#             )

#         else:

#             product_name = middle_parts[0]

#             artwork_type = None

#     # -------------------------
#     # PRODUCT CODE LOGIC
#     # -------------------------

#     base_product_code = product_code
#     product_variant = variant_code

#     if product_code and variant_code and not is_combined:
#         full_product_code = f"{product_code}-{variant_code}"
#     else:
#         full_product_code = None
   
#     artwork_group = get_artwork_group(artwork_type)

#     print("\nDEBUG")
#     print(filename)
#     print("product_name =", product_name)
#     print("artwork_type =", artwork_type)

#     return {

#         "release_date": release_date,

#         "range_name": range_name,

#         "product_name": product_name,

#         "base_product_code": product_code,

#         "product_variant": product_variant,

#         "full_product_code": full_product_code,

#         "artwork_type": artwork_type,

#         "artwork_group": artwork_group,

#         "revision_code": revision_code,

#         "resolution": resolution,

#         "is_combined": is_combined,

#         "combined_product_codes": combined_product_codes
#     }

# ---------------- ARTWORK GROUP MAPPING ---------------- #

def get_artwork_group(artwork_type):

    print("MAPPING LOOKUP:", repr(artwork_type))

    if not artwork_type:
        return "Unknown"

    # Normalize
    # artwork_type = artwork_type.replace("_", "-")

    mapping = {

        # Instructions
        "Instruction-Booklet": "Instruction",
        "Instructions": "Instruction",
        "Generic-Instruction": "Instruction",
        "Generic-Instructions": "Instruction",

        # Swing Tags
        "Packaging-Swing-Tag": "Swing Tag",
        "Packaging_Swing-Tag": "Swing Tag",
        "Swing-Tag": "Swing Tag",

        # Swing Tag Barcode
        "Packaging-Swing-Tag-Barcode-Sticker": "Swing Tag Barcode Sticker",
        "Packaging_Swing-Tag_Barcode-Sticker": "Swing Tag Barcode Sticker",
        "Swing-Tag-Barcode-Sticker": "Swing Tag Barcode Sticker",
        "Swing-Tag_Barcode-Sticker": "Swing Tag Barcode Sticker",
        "Barcode-Sticker-Swing-Tag": "Swing Tag Barcode Sticker",
        "Barcode-Sticker": "Swing Tag Barcode Sticker",

        # Production Tags
        "Production-Tag": "Production Tag",
        "Label_Production-Tag": "Production Tag",

        # Branding
        "Branding": "Branding",
        "Branding-Carrybag": "Branding Carrybag",

        # Woven Labels
        "Branding-Woven-Label": "Woven Label",
        "Branding_Woven-Label": "Woven Label",

        # Cartons
        "Packaging-Outer-Carton": "Outer Carton",
        "Packaging_Outer-Carton": "Outer Carton",
        "Packaging-Inner-Carton": "Inner Carton",
        "Packaging_Inner-Carton": "Inner Carton",
        "Outer-Carton": "Outer Carton",
        "Inner-Carton": "Inner Carton",

        # Shipping Stickers
        "Outer-Shipping-Sticker": "Outer Shipping Sticker",
        "Inner-Shipping-Sticker": "Inner Shipping Sticker",
        "Outer-Shipping-Sticker-AU": "Outer Shipping Sticker",
        "Inner-Shipping-Sticker-NZ": "Inner Shipping Sticker",

        # Colour Boxes
        "Packaging-Colour-Box": "Colour Box",
        "Packaging_Colour-Box": "Colour Box",
        "Packaging-Colour-Carton": "Colour Box",
        "Packaging_Colour-Carton": "Colour Box",

        # Unit Boxes (Brown)
        "Packaging-Unit-Carton": "Unit Carton",
        "Packaging_Unit-Carton": "Unit Carton",

        # Header Cards
        "Header-Cards": "Header Cards",
        "Header-Card": "Header Cards",
        "Packaging-Header-Card": "Header Cards",
        "Packaging-Header-Cards": "Header Cards",
        "Packaging_Header-Cards": "Header Cards",        
        "Packaging_Header-Card": "Header Cards",

        # Header Card Sticker
        "Header-Card-Sticker": "Header Card Sticker",
    }

    return mapping.get(
        artwork_type,
        "Unknown"
    )


# ---------------- SYNC FOLDER TO NEON ---------------- #

def sync_folder_to_neon(folder, upload_id, actions):
    # ---------------------------------
    # Create product once per folder
    # ---------------------------------

    full_product_code, folder_product_name = (
        get_product_from_path(folder)
    )

    if full_product_code:

        existing = get_product(full_product_code)

        if not existing:

            print("\n" + "=" * 50)
            print("NEW PRODUCT")
            print(full_product_code)
            print("=" * 50)

            product_name = input(
                f"Product name (Enter = accept '{folder_product_name}'): "
            ).strip()

            if not product_name:
                product_name = folder_product_name

            insert_product(
                full_product_code,
                product_name,
                None
            )

            seed_artwork_requirements(
                full_product_code
            )

            actions.append(
                f"[PRODUCT CREATED] {full_product_code}"
            )

    # ---------------------------------
    # Process artwork files
    # ---------------------------------

    for root, _, files in os.walk(folder):

        for filename in files:

            if not filename.lower().endswith(".pdf"):
                continue

            try:

                record = parse_filename(filename)

                if record and full_product_code:

                    parts = base_product_code, product_variant = (
                        full_product_code.split("-")
                    )

                    record["full_product_code"] = (
                        full_product_code
                    )

                    record["base_product_code"] = parts[0]

                    record["product_variant"] = (
                        parts[1] if len(parts) > 1 else None
                    )

                if not record:
                    actions.append(
                        f"[DB SKIPPED] Unable to parse: {filename}"
                    )
                    continue

                record["filename"] = filename
                record["file_path"] = os.path.join(root, filename)
                record["upload_id"] = upload_id
                record["product_name"] = folder_product_name

                artwork_id, already_exists = insert_artwork(record)

                # if artwork_id and record.get("combined_product_codes"):

                #     actions.append(
                #         f"[COMBINED DETECTED] {record.get('combined_product_codes', [])}"
                #     )

                #     for code in record["combined_product_codes"]:

                #         link_artwork_to_product(
                #             artwork_id,
                #             code
                #         )

                #         actions.append(
                #             f"[AUTO LINKED] {filename} -> {code}"
                #         )

                if artwork_id and record.get("is_combined"):

                    # Case 1
                    # Combined artwork with detected product codes
                    if record.get("combined_product_codes"):

                        actions.append(
                            f"[COMBINED DETECTED] {record['combined_product_codes']}"
                        )

                        for code in record["combined_product_codes"]:

                            link_artwork_to_product(
                                artwork_id,
                                code
                            )

                            actions.append(
                                f"[AUTO LINKED] {filename} -> {code}"
                            )

                    # Case 2
                    # Generic / Combined artwork without codes
                    else:

                        print("\n" + "=" * 50)
                        print("COMBINED ARTWORK DETECTED")
                        print(filename)
                        print("=" * 50)

                        suggested_codes = get_product_codes_from_path(folder)

                        print("\nSuggested product codes:")

                        print(
                            ", ".join(suggested_codes)
                        )

                        codes = input(
                            "\nPress Enter to use suggestions, or enter different codes: "
                        ).strip()

                        if not codes:
                            codes_to_link = suggested_codes
                        else:
                            codes_to_link = [
                                c.strip()
                                for c in codes.split(",")
                                if c.strip()
                            ]

                        for code in codes_to_link:

                            link_artwork_to_product(
                                artwork_id,
                                code
                            )

                            actions.append(
                                f"[LINKED] {filename} -> {code}"
                            )

                if already_exists:

                    actions.append(f"[DB EXISTS] {filename}")

                    SHARED_ARTWORK_GROUPS = [
                        "Production Tag",
                        "Instruction"
                    ]

                    is_shared_artwork = (
                        record.get("is_combined")
                        or not record.get("full_product_code")
                        or record.get("artwork_group") in SHARED_ARTWORK_GROUPS
                    )

                    # Product-specific artwork
                    if full_product_code and not is_shared_artwork:

                        link_artwork_to_product(
                            artwork_id,
                            full_product_code
                        )

                        actions.append(
                            f"[AUTO LINKED] {filename} -> {full_product_code}"
                        )

                    # Shared artwork
                    elif artwork_id:

                        print("\n" + "=" * 50)
                        print("SIMILAR SHARED ARTWORK DETECTED")
                        print(filename)
                        print("=" * 50)

                        suggested_codes = get_product_codes_from_path(folder)

                        print("\nSuggested product codes:")
                        print(", ".join(suggested_codes))

                        codes = input(
                            "\nPress Enter to use suggestions, or enter different codes: "
                        ).strip()

                        if not codes:
                            codes_to_link = suggested_codes
                        else:
                            codes_to_link = [
                                c.strip()
                                for c in codes.split(",")
                                if c.strip()
                            ]

                        for code in codes_to_link:

                            link_artwork_to_product(
                                artwork_id,
                                code
                            )

                            actions.append(
                                f"[LINKED] {filename} -> {code}"
                            )

                else:

                    actions.append(
                        f"[DB INSERTED] {filename}"
                    )

                    if (
                        artwork_id
                        and full_product_code
                        and not record.get("is_combined")
                    ):

                        link_artwork_to_product(
                            artwork_id,
                            full_product_code
                        )

                        actions.append(
                            f"[AUTO LINKED] {filename} -> {full_product_code}"
                        )

                # if already_exists:

                #     actions.append(
                #         f"[DB EXISTS] {filename}"
                #     )

                #     SHARED_ARTWORK_GROUPS = [
                #         "Production Tag",
                #         "Instruction"
                #     ]

                #     is_shared_artwork = (
                #         record.get("is_combined")
                #         or not record.get("full_product_code")
                #         or record.get("artwork_group") in SHARED_ARTWORK_GROUPS
                #     )

                #     # Shared artwork
                #     # Ask user which products use it
                #     # Create links
                #     if artwork_id and is_shared_artwork:

                #         print("\n" + "=" * 50)
                #         print("SIMILAR ARTWORK DETECTED")
                #         print(filename)
                #         print("=" * 50)

                #         suggested_codes = get_product_codes_from_path(folder)

                #         print("\nSuggested product codes:")

                #         print(
                #             ", ".join(suggested_codes)
                #         )

                #         codes = input(
                #             "\nPress Enter to use suggestions, or enter different codes: "
                #         ).strip()

                #         if not codes:
                #             codes_to_link = suggested_codes
                #         else:
                #             codes_to_link = [
                #                 c.strip()
                #                 for c in codes.split(",")
                #                 if c.strip()
                #             ]

                #         for code in codes_to_link:

                #             link_artwork_to_product(
                #                 artwork_id,
                #                 code
                #             )

                #             actions.append(
                #                 f"[LINKED] {filename} -> {code}"
                #             )
                # else:
                #     # New artwork
                #     # Always link to current product

                #     actions.append(
                #         f"[DB INSERTED] {filename}"
                #     )

                #     if full_product_code:

                #         link_artwork_to_product(
                #             artwork_id,
                #             full_product_code
                #         )

                #         actions.append(
                #             f"[AUTO LINKED] {filename} -> {full_product_code}"
                #         )

                
            except Exception as e:

                actions.append(
                    f"[DB ERROR] {filename}: {e}"
                )


# ---------------- RETRIEVE PRODUCT CODE FROM THE INPUT FOLDER PATH ---------------- #
def get_product_codes_from_path(folder):

    path_text = folder.replace("\\", " ")

    return sorted(
        set(
            re.findall(
                r'\d{7}-\d{3}',
                path_text
            )
        )
    )

# ---------------- MAIN ---------------- #

while True:

    actions = []

    upload_id = generate_upload_id()

    try:

        folder_path = input("\nEnter folder path: ").strip()

        if not os.path.isdir(folder_path):
            print("❌ Invalid folder path.")
            continue

        # Step 1: Rename PDFs
        rename_folder_pdfs(folder_path, actions)

        # Step 2: Copy classified PDFs
        copy_special_files(folder_path, actions)

        # Step 3: Insert artwork into database
        sync_folder_to_neon(folder_path, upload_id, actions)

    except Exception:

        print("\n🔥 SCRIPT ERROR — window kept open")

        err = traceback.format_exc()

        print(err)
        log(err)

    print("\n========== SUMMARY ==========")

    for a in actions:
        log(a)

    if input("\nProcess another folder? (y/n): ").lower() != "y":
        print("\n✅ Finished.")
        break