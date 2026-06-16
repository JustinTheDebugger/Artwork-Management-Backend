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
            if "PRODUCTION-TAG" in segments_upper:
                dest_dir = production_tag_dir

            # ---- HEADER CARD ---- #
            elif "HEADER-CARD" in segments_upper:
                dest_dir = header_card_dir

            # ---- WOVEN LABEL ---- #
            elif any("WOVEN-LABEL" in s for s in segments_upper):
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

    # match = re.search(
    #     r'(.+?)\s*-\s*(\d{7}-\d{3})$',
    #     folder_name
    # )

    match = re.search(
        r'(.+?)\s*-\s*(\d{7}(?:-\d{3})?)$',
        folder_name
    )

    if not match:
        return None, None

    product_name = match.group(1).strip()
    product_code = match.group(2).strip()

    return product_code, product_name


# ---------------- PARSE FILENAME ---------------- #

def parse_filename(filename):

    name = os.path.splitext(filename)[0]

    parts = name.split("_")

    # Generic artwork
    # Example:
    # 260610_PE-Footprints_Generic-Instructions_B_HR

    if len(parts) == 5:

        return {
            "release_date": datetime.strptime(
                parts[0],
                "%y%m%d"
            ).date(),

            "range_name": None,

            "product_name": parts[1],

            "base_product_code": None,

            "product_variant": None,

            "full_product_code": None,

            "artwork_type": parts[2],

            "revision_code": parts[3],

            "resolution": parts[4],

            "is_combined": True,

            "combined_product_codes": []
        }

    # Minimum:
    # 260603_Shapeshifter-6_Production-Tag_001_B_HR

    if len(parts) < 5:
        return None

    # -------------------------
    # DATE
    # -------------------------

    date_part = parts[0]

    try:
        release_date = datetime.strptime(
            date_part,
            "%y%m%d"
        ).date()
    except ValueError:
        return None

    # -------------------------
    # RESOLUTION
    # -------------------------

    resolution = parts[-1]

    # -------------------------
    # COMBINED or SHARED FLAGS
    # -------------------------

    # -------------------------
    # COMBINED or SHARED FLAGS
    # -------------------------

    is_combined = False
    combined_product_codes = []

    name_upper = name.upper()

    is_combined = any(
        k in name_upper
        for k in ["COMBINED", "GENERIC"]
    )

    # Pattern:
    # Product_0256504-002-0266505-001_Instruction-Booklet_B_HR

    if (
        len(parts) == 6
        and re.match(
            r'^\d{7}-\d{3}-\d{7}-\d{3}$',
            parts[2]
        )
    ):

        is_combined = True

        revision_code = parts[-2]

        variant_code = None

        middle_parts = parts[1:-2]

    # Pattern:
    # Product_Generic-Instruction_B_Combined_HR

    elif is_combined and len(parts) == 6:

        revision_code = f"{parts[-3]} - Combined"

        variant_code = None

        middle_parts = parts[1:-3]

    # Pattern:
    # Product_Swing-Tag_001_B_Combined_HR

    elif is_combined:

        revision_code = f"{parts[-3]} - Combined"

        variant_code = parts[-4]

        middle_parts = parts[1:-4]

    # Standard artwork

    else:

        revision_code = parts[-2]

        variant_code = parts[-3]

        middle_parts = parts[1:-3]

    # is_combined = False
    # combined_product_codes = []
    # name_upper = name.upper()

    # is_combined = any(k in name_upper for k in ["COMBINED", "GENERIC"])

    # # Generic shared artwork
    # # Pattern:
    # # Product_Generic-Instruction_B_Combined_HR
    # if is_combined and len(parts) == 6:

    #     revision_code = f"{parts[-3]} - Combined"

    #     variant_code = None

    #     middle_parts = parts[1:-3]
    
    # # Pattern:
    # # Product_Swing-Tag_001_B_Combined_HR
    # elif is_combined:

    #     revision_code = f"{parts[-3]} - Combined"
        
    #     variant_code = parts[-4]

    #     middle_parts = parts[1:-4]

    # else:

    #     revision_code = parts[-2]
        
    #     variant_code = parts[-3]

    #     middle_parts = parts[1:-3]

    # -------------------------
    # FIND PRODUCT CODE
    # -------------------------

    product_code = None

    # print("\nDEBUG MIDDLE PARTS")
    # print(filename)
    # print(middle_parts)

    for i, part in enumerate(middle_parts):

        if re.match(r'^\d+(?:-\d+)*$', part):
            product_code = part
            product_code_index = i
            break

    # -------------------------
    # FILE HAS PRODUCT CODE
    # -------------------------

    if product_code:

        matches = re.findall(
            r'\d{7}-\d{3}',
            product_code
        )


        # Pattern:
        # 0256504-002-0266505-001
        if len(matches) > 1:

            is_combined = True

            combined_product_codes = matches

            product_code = None
            variant_code = None

        # Pattern:
        # 0266661-0266662
        elif re.match(
            r'^\d{7}-\d{7}$',
            product_code
        ):

            is_combined = True

            codes = product_code.split("-")

            combined_product_codes = [
                f"{code}-{variant_code}"
                for code in codes
            ]

            product_code = None
            variant_code = None

        # Pattern:
        # 0266661-62
        # 0266612-13-22-23

        elif re.match(
            r'^\d{7}(?:-\d{2})+$',
            product_code
        ):

            is_combined = True

            first_code = product_code.split("-")[0]

            prefix = first_code[:5]

            suffixes = [
                first_code[5:]
            ] + product_code.split("-")[1:]

            combined_product_codes = [
                f"{prefix}{suffix}-{variant_code}"
                for suffix in suffixes
            ]

            product_code = None
            variant_code = None

    if product_code:

        range_name = middle_parts[0]

        product_name = "_".join(
            middle_parts[:product_code_index]
        )

        artwork_type = "_".join(
            middle_parts[product_code_index + 1:]
        )

    elif is_combined:

        range_name = middle_parts[0]

        product_name = "_".join(
            middle_parts[:product_code_index]
        ) if 'product_code_index' in locals() else None

        artwork_type = "_".join(
            middle_parts[product_code_index + 1:]
        ) if 'product_code_index' in locals() else "_".join(middle_parts[1:])

    else:

        range_name = middle_parts[0]

        # No product code found
        # Treat first segment as product name
        # and remainder as artwork type

        if len(middle_parts) > 1:

            product_name = middle_parts[0]

            artwork_type = "_".join(
                middle_parts[1:]
            )

        else:

            product_name = middle_parts[0]

            artwork_type = None

    # -------------------------
    # PRODUCT CODE LOGIC
    # -------------------------

    base_product_code = product_code
    product_variant = variant_code

    if product_code and variant_code and not is_combined:
        full_product_code = f"{product_code}-{variant_code}"
    else:
        full_product_code = None
   
    artwork_group = get_artwork_group(artwork_type)

    # print("\nDEBUG")
    # print(filename)
    # print("product_name =", product_name)
    # print("artwork_type =", artwork_type)

    return {

        "release_date": release_date,

        "range_name": range_name,

        "product_name": product_name,

        "base_product_code": product_code,

        "product_variant": product_variant,

        "full_product_code": full_product_code,

        "artwork_type": artwork_type,

        "artwork_group": artwork_group,

        "revision_code": revision_code,

        "resolution": resolution,

        "is_combined": is_combined,

        "combined_product_codes": combined_product_codes
    }

# ---------------- ARTWORK GROUP MAPPING ---------------- #

def get_artwork_group(artwork_type):

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

        # Shipping Stickers
        "Outer-Shipping-Sticker": "Outer Shipping Sticker",
        "Inner-Shipping-Sticker": "Inner Shipping Sticker",

        # Colour Boxes
        "Packaging-Colour-Box": "Colour Box",
        "Packaging_Colour-Box": "Colour Box",
        "Packaging-Colour-Carton": "Colour Box",
        "Packaging_Colour-Carton": "Colour Box",
    }

    return mapping.get(
        artwork_type,
        artwork_type.replace("-", " ").replace("_", " ")
    )


# ---------------- SYNC FOLDER TO NEON ---------------- #

def sync_folder_to_neon(folder, upload_id, actions):

    for root, _, files in os.walk(folder):

        for filename in files:

            if not filename.lower().endswith(".pdf"):
                continue

            try:

                record = parse_filename(filename)

                full_product_code, product_name = get_product_from_path(folder)

                if record and full_product_code:

                    record["full_product_code"] = full_product_code

                    record["base_product_code"] = full_product_code.split("-")[0]

                    record["product_variant"] = full_product_code.split("-")[1]

                product_code, product_name = (
                    get_product_from_path(folder)
                )

                if product_code:

                    existing = get_product(
                        product_code
                    )

                    if not existing:

                        print("\n" + "=" * 50)
                        print("NEW PRODUCT")
                        print(product_code)
                        print("=" * 50)

                        suggested_name = (
                            record.get("product_name")
                            or ""
                        )

                        print(
                            f"Suggested name: {suggested_name}"
                        )

                        product_name = input(
                            "Product name (Enter = accept): "
                        ).strip()

                        if not product_name:
                            product_name = suggested_name

                        insert_product(
                            product_code,
                            product_name,
                            record.get("range_name")
                        )

                        # Insert product artwork requirements into database
                        seed_artwork_requirements(product_code)

                        actions.append(
                            f"[PRODUCT CREATED] {product_code}"
                        )

                if not record:
                    actions.append(
                        f"[DB SKIPPED] Unable to parse: {filename}"
                    )
                    continue

                record["filename"] = filename
                record["file_path"] = os.path.join(root, filename)
                record["upload_id"] = upload_id

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

                    actions.append(
                        f"[DB EXISTS] {filename}"
                    )

                    is_shared_artwork = (
                        record.get("is_combined")
                        or not record.get("full_product_code")
                        or "PRODUCTION-TAG" in record.get("artwork_type", "").upper()
                    )

                    # Shared artwork
                    # Ask user which products use it
                    # Create links
                    if is_shared_artwork:

                        print("\n" + "=" * 50)
                        print("SIMILAR ARTWORK DETECTED")
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
                else:
                    # New artwork
                    # Just insert record

                    actions.append(
                        f"[DB INSERTED] {filename}"
                    )

                
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