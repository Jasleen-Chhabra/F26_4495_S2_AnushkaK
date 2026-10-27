# F26_4495_S2_AnushkaK

## Project: Inventory and Procurement Decision-Support System
CSIS 4495-002 Applied Research Project, Fall 2026, Douglas College

## Team
| Name | Student ID | Email |
| --- | --- | --- |
| Anushka Kshirsagar (Team Lead) | 300395615 | kshirsagara@student.douglascollege.ca |
| Jasleen Chhabra | 300413040 | chhabraj@student.douglascollege.ca |

**Instructor:** Padmapriya Arasanipalai Kandhadai

## Overview
A browser-based decision-support app that combines sales history, current
stock, incoming shipments and lead times to forecast demand, project future
stock and suggest when and how much to reorder.

## Features (mid-course)
- Overview dashboard: revenue, estimated gross profit, inventory value, open PO value and products at risk
- Sales & Financials, and Inventory & Procurement pages
- Supplier Performance: on-time delivery, average lead time and delayed orders
- SKU Analysis: sales history, stock, incoming purchase orders, demand forecast (3-month moving average), 12-month inventory projection and reorder recommendation
- Scenario Planner: higher demand and shipment delay what-if analysis

## Data
The current dataset is a **generated sample dataset** created for development
and testing (about 300 SKUs, monthly sales from Jan 2022 to Sep 2026, selling
prices, inventory and purchase orders). It was generated with a Python script
using AI assistance, and all names are **fictional**. Anonymized workplace data
may replace it later if permission and time allow.

Files in `Implementation/Data/`:
- `products.csv`, `inventory.csv`, `purchase_orders.csv`, `sales_monthly.csv`

## Installation and how to run the demo
Requirements: Python 3.10 or newer, and Git.

1. Clone the repository:
   `git clone https://github.com/Jasleen-Chhabra/F26_4495_S2_AnushkaK.git`
2. Go to the application folder (the folder that contains `app.py` and `Data/`):
   `cd F26_4495_S2_AnushkaK/Implementation`
3. (Optional) Create and activate a virtual environment:
   `python -m venv venv`, then `venv\Scripts\activate` (Windows) or `source venv/bin/activate` (Mac/Linux)
4. Install the packages:
   `pip install -r requirements.txt`
5. Run the app from this folder:
   `streamlit run app.py`
6. Open the link shown in the terminal (usually http://localhost:8501).

## Folders
- `ReportsAndDocuments/` - proposal, progress reports, mid-course and final reports
- `Implementation/` - application code (Python, Streamlit) and data
- `Misc/` - other files

## Status
Mid-course stage (Oct 2026). Next: forecast evaluation, scenario and supplier
analysis improvements, reorder logic and testing.
