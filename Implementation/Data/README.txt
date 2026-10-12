SYNTHETIC DATASET - CSIS 4495 Inventory & Procurement Decision-Support System
All data is artificially generated (seed 4495). Not real company data. Snapshot date: 2026-10-07.

products.csv         45 SKUs: category, supplier_id, pack_size, lead_time_days, unit_cost, warehouses
sales_monthly.csv    Monthly units sold per SKU & warehouse, 2024-01 to 2026-09 (seasonal + trend + noise,
                     includes a few promo spikes and low-sales/stock-out months)
inventory.csv        Current on-hand quantity per SKU & warehouse (as_of_date 2026-10-07)
purchase_orders.csv  Open POs (ordered / in_transit / delayed) with separate ETAs per container, plus
                     received POs (history) with actual_arrival_date for lead-time analysis
inventory.db         Same 4 tables in SQLite
generate_dataset.py  Regenerates everything (change seed / SKU count as needed)

Notes: Seasonal categories (Holiday peak Nov-Dec, Summer peak May-Aug), Everyday, Premium.
Stock is set so ~30% SKUs are at shortage risk, ~50% OK, ~20% excess - good for testing flags.
Use for demo / backup; document in the report that this part is synthetic.
