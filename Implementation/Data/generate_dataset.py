"""Synthetic inventory & procurement dataset for CSIS 4495 project.
Run: python generate_dataset.py   (seed fixed -> reproducible)
All data is synthetic; no real company/supplier information."""
import numpy as np, pandas as pd, sqlite3, os
rng = np.random.default_rng(4495)
OUT = os.path.dirname(os.path.abspath(__file__))
TODAY = pd.Timestamp("2026-10-07")

# ---------- products ----------
cats = {  # category: (seasonal profile, base demand range, unit cost range, pack sizes)
 "Seasonal-Holiday": ("holiday", (150, 600), (4, 18),  [6, 12, 24]),
 "Seasonal-Summer":  ("summer",  (120, 500), (6, 25),  [6, 12]),
 "Everyday":         ("flat",    (200, 900), (2, 12),  [12, 24, 48]),
 "Premium":          ("mild",    (60, 250),  (20, 90), [1, 4, 6]),
}
suppliers = {"Supplier A": 95, "Supplier B": 110, "Supplier C": 75, "Supplier D": 125, "Supplier E": 60}
prof = {
 "holiday": [.85,.80,.85,.90,.95,.90,.90,.95,1.1,1.45,1.9,2.1],
 "summer":  [.60,.65,.85,1.1,1.45,1.75,1.8,1.6,1.1,.8,.65,.6],
 "flat":    [1,.97,1,1,1.02,1.03,1.02,1.0,1.0,1.03,1.08,1.1],
 "mild":    [.9,.9,.95,1,1,1,.95,.95,1,1.05,1.2,1.3],
}
rows = []
for i in range(1, 46):
    cat = rng.choice(list(cats), p=[.3,.2,.35,.15])
    p, (dlo, dhi), (clo, chi), packs = cats[cat]
    sup = rng.choice(list(suppliers))
    lt = int(np.clip(rng.normal(suppliers[sup], 10), 45, 140))
    whs = ["WH1"] if rng.random() < .4 else ["WH1", "WH2"]
    rows.append(dict(sku=f"SKU{i:03d}", category=cat, supplier_id=sup, pack_size=int(rng.choice(packs)),
        lead_time_days=lt, unit_cost=round(rng.uniform(clo, chi), 2), base_monthly_demand=int(rng.integers(dlo, dhi)),
        trend_pct_per_year=round(rng.normal(.04, .08), 3), profile=p, warehouses=",".join(whs)))
prod = pd.DataFrame(rows)

# ---------- sales (monthly, per sku & warehouse) ----------
months = pd.period_range("2024-01", "2026-09", freq="M")
sales = []
for _, r in prod.iterrows():
    whs = r.warehouses.split(",")
    shares = [1.0] if len(whs) == 1 else [.65, .35]
    for wh, sh in zip(whs, shares):
        for k, m in enumerate(months):
            seas = prof[r.profile][m.month-1]
            trend = (1 + r.trend_pct_per_year) ** (k/12)
            lam = r.base_monthly_demand * sh * seas * trend
            u = rng.negative_binomial(20, 20/(20+lam)) if lam > 0 else 0
            sales.append((r.sku, wh, str(m), int(u)))
sales = pd.DataFrame(sales, columns=["sku", "warehouse", "month", "units_sold"])
# a few promo spikes and stock-out months (data realism)
idx = rng.choice(sales.index, 40, replace=False); sales.loc[idx, "units_sold"] = (sales.loc[idx, "units_sold"] * rng.uniform(1.5, 2.2, 40)).astype(int)
idx = rng.choice(sales.index, 25, replace=False); sales.loc[idx, "units_sold"] = (sales.loc[idx, "units_sold"] * .25).astype(int)

# ---------- forward monthly demand estimate (used only to size stock/POs) ----------
def fwd_monthly(r, k0):
    return np.mean([r.base_monthly_demand * prof[r.profile][(10+j-1) % 12] * (1+r.trend_pct_per_year)**((len(months)+j)/12) for j in range(4)])

# ---------- current inventory & purchase orders ----------
inv, po = [], []
n = 0
for _, r in prod.iterrows():
    d = fwd_monthly(r, 0)
    whs = r.warehouses.split(",")
    scenario = rng.choice(["risk", "ok", "excess"], p=[.3, .5, .2])
    cover_m = {"risk": rng.uniform(.8, 2.0), "ok": rng.uniform(2.5, 4.5), "excess": rng.uniform(6, 9)}[scenario]
    total_stock = int(d * cover_m)
    for wh, sh in zip(whs, [1.0] if len(whs) == 1 else [.65, .35]):
        inv.append((r.sku, wh, int(total_stock * sh // r.pack_size * r.pack_size), str(TODAY.date())))
    # open POs: 1-4 shipments with different ETAs
    n_open = int(rng.choice([0, 1, 2, 3, 4], p=[.1, .25, .35, .22, .08]))
    if scenario == "excess": n_open = max(n_open, 2)
    for j in range(n_open):
        elapsed = int(rng.integers(1, max(2, r.lead_time_days - 8)))
        odate = TODAY - pd.Timedelta(days=elapsed)
        eta = odate + pd.Timedelta(days=int(r.lead_time_days + rng.integers(-7, 10)))
        qty = int(max(1, d * rng.uniform(.8, 2.2)) // r.pack_size * r.pack_size) or r.pack_size
        n += 1
        status = "delayed" if rng.random() < .12 else ("in_transit" if elapsed > 30 else "ordered")
        po.append((f"PO{n:04d}", r.sku, r.supplier_id, "WH1" if len(whs)==1 or rng.random()<.7 else "WH2",
                   f"CNT{rng.integers(1000, 9999)}", qty, str(odate.date()), str(eta.date()), status, None))
    # historical received POs (for lead-time analysis)
    for j in range(int(rng.integers(3, 7))):
        recv = pd.Timestamp("2024-03-01") + pd.Timedelta(days=int(rng.integers(0, 570)))
        act_lt = int(max(30, rng.normal(r.lead_time_days, 12)))
        odate = recv - pd.Timedelta(days=act_lt)
        qty = int(d * rng.uniform(.8, 2.0) // r.pack_size * r.pack_size) or r.pack_size
        n += 1
        po.append((f"PO{n:04d}", r.sku, r.supplier_id, "WH1", f"CNT{rng.integers(1000, 9999)}", qty,
                   str(odate.date()), str((odate + pd.Timedelta(days=int(r.lead_time_days))).date()), "received", str(recv.date())))

inventory = pd.DataFrame(inv, columns=["sku", "warehouse", "on_hand_qty", "as_of_date"])
pos = pd.DataFrame(po, columns=["po_id", "sku", "supplier_id", "warehouse", "container_id", "quantity",
                                "order_date", "expected_arrival_date", "status", "actual_arrival_date"])
products = prod.drop(columns=["base_monthly_demand", "trend_pct_per_year", "profile"])  # hide generator internals

# ---------- save ----------
tables = dict(products=products, sales_monthly=sales, inventory=inventory, purchase_orders=pos)
for k, v in tables.items(): v.to_csv(f"{OUT}/{k}.csv", index=False)
with sqlite3.connect(f"{OUT}/inventory.db") as c:
    for k, v in tables.items(): v.to_sql(k, c, if_exists="replace", index=False)
    c.execute("CREATE INDEX ix_sales ON sales_monthly(sku, month)"); c.execute("CREATE INDEX ix_po ON purchase_orders(sku, status)")
for k, v in tables.items(): print(k, v.shape)
print(pos.status.value_counts().to_dict())
