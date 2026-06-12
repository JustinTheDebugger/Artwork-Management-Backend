# Artwork Management System

## Overview

Artwork Management System is an internal tool developed to manage product artwork files, track artwork coverage, and monitor artwork requirements across all products.

The system automatically scans artwork folders, extracts metadata from file names and folder structures, stores records in PostgreSQL, and provides a Streamlit dashboard for visibility and reporting.

---

## Features

### Artwork Sync

* Scans artwork repository folders
* Detects new and updated PDF artwork files
* Extracts:

  * Product Code
  * Product Name
  * Artwork Type
  * Revision
  * File Path
* Updates artwork records in the database

### Product Management

* Stores product master data
* Tracks product codes and product names
* Supports combined products and shared artwork

### Artwork Coverage Tracking

* Displays required vs available artwork
* Highlights missing artwork
* Tracks coverage by artwork group

Artwork Groups:

* Branding
* Instruction
* Swing Tag
* Swing Tag Barcode Sticker
* Production Tag
* Outer Carton
* Inner Carton
* Colour Box
* Outer Shipping Sticker
* Inner Shipping Sticker
* Woven Label

### Dashboard

* Product coverage matrix
* Missing artwork reporting
* Artwork inventory overview

---

## Technology Stack

* Python 3.13
* Streamlit
* PostgreSQL - NEONDB
* Pandas
* Psycopg

---

## Project Structure

```text
Artwork Management Backend/
│
├── app.py
├── db.py
├── run-sync.py
├── dashboard.py
│
├── pages/
│   ├── Artwork Tracker.py
│   ├── Products.py
│
├── scripts/
├── sql/
├── uploads/
│
├── requirements.txt
├── README.md
└── .gitignore
```

---

## Database Tables

### products

Stores product master information.

### artworks

Stores artwork file records.

### product_artwork_requirements

Defines required artwork groups for each product.

### product_change_log

Stores product changes and revisions.

---

## Setup

Install dependencies:

```bash
pip install -r requirements.txt
```

Run Streamlit:

```bash
streamlit run app.py
```

Run artwork synchronization:

```bash
python run-sync.py
```

---

## Future Improvements

* Outlook email integration
* Automated product change logs
* Artwork approval workflow
* Revision history tracking
* Factory delivery status tracking
* SharePoint integration

---

## Author

Justin Tay
