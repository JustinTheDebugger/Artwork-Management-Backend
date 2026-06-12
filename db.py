from datetime import datetime
import psycopg

CONNECTION_STRING = "postgresql://neondb_owner:npg_VsvbSpul5Ch0@ep-late-rain-a7epxzsy-pooler.ap-southeast-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require"


def get_connection():
    return psycopg.connect(CONNECTION_STRING)

def insert_artwork(record):

    sql = """
    INSERT INTO artwork_files (
        range_name,
        product_name,
        base_product_code,
        product_variant,
        full_product_code,
        artwork_type,
        artwork_group,
        revision_code,
        release_date,
        resolution,
        upload_id,
        filename,
        file_path,
        is_combined
    )
    VALUES (
        %(range_name)s,
        %(product_name)s,
        %(base_product_code)s,
        %(product_variant)s,
        %(full_product_code)s,
        %(artwork_type)s,
        %(artwork_group)s,
        %(revision_code)s,
        %(release_date)s,
        %(resolution)s,
        %(upload_id)s,
        %(filename)s,
        %(file_path)s,
        %(is_combined)s
    )
    RETURNING id
    """

    with get_connection() as conn:

        with conn.cursor() as cur:

            # Already exists?
            existing_id = get_artwork_id_by_filename(
                cur,
                record["filename"]
            )

            if existing_id:
                return existing_id, True

            record.setdefault("base_product_code", None)
            record.setdefault("product_variant", None)
            record.setdefault("full_product_code", None)
            record.setdefault("product_name", None)
            record.setdefault("is_combined", False)
            record.setdefault("artwork_group", None)

            cur.execute(sql, record)

            artwork_id = cur.fetchone()[0]

            conn.commit()

            return artwork_id, False

def link_artwork_to_product(artwork_id, product_code):

    sql = """
    INSERT INTO product_artwork_links (
        product_code,
        artwork_id
    )
    VALUES (%s, %s)
    ON CONFLICT (product_code, artwork_id)
    DO NOTHING
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (product_code, artwork_id))

        conn.commit()

def link_artwork_safe(artwork_id, record):

    # CASE 1: single product
    if record.get("full_product_code"):
        link_artwork_to_product(
            artwork_id,
            record["full_product_code"]
        )
        return

    # CASE 2: combined products in filename field
    if record.get("combined_product_codes"):
        for code in record["combined_product_codes"]:
            link_artwork_to_product(
                artwork_id,
                code
            )

def get_artwork_id(cur, filename):

    cur.execute(
        """
        SELECT id
        FROM artwork_files
        WHERE filename = %s
        """,
        (filename,)
    )

    row = cur.fetchone()

    return row[0] if row else None

def get_artwork_id_by_filename(cur, filename):

    cur.execute(
        """
        SELECT id
        FROM artwork_files
        WHERE filename = %s
        """,
        (filename,)
    )

    row = cur.fetchone()

    return row[0] if row else None

def get_artwork_details(artwork_id):

    sql = """
    SELECT
        filename,
        full_product_code,
        artwork_type
    FROM artwork_files
    WHERE id = %s
    """

    with get_connection() as conn:
        with conn.cursor() as cur:

            cur.execute(sql, (artwork_id,))

            return cur.fetchone()

def get_product(product_code):

    sql = """
    SELECT product_name
    FROM products
    WHERE product_code = %s
    """

    with get_connection() as conn:
        with conn.cursor() as cur:

            cur.execute(
                sql,
                (product_code,)
            )

            return cur.fetchone()

def insert_product(
    product_code,
    product_name,
    range_name
):

    sql = """
    INSERT INTO products (
        product_code,
        product_name,
        range_name
    )
    VALUES (
        %s,
        %s,
        %s
    )
    ON CONFLICT (product_code)
    DO NOTHING
    """

    with get_connection() as conn:
        with conn.cursor() as cur:

            cur.execute(
                sql,
                (
                    product_code,
                    product_name,
                    range_name
                )
            )

            conn.commit()

def sync_artwork_requirements():

    sql = """
    INSERT INTO product_artwork_requirements (
        product_code,
        artwork_group,
        required
    )
    SELECT DISTINCT
        product_code,
        artwork_group,
        TRUE
    FROM vw_product_artwork_coverage
    ON CONFLICT DO NOTHING
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            conn.commit()