"""Sample inventory & procurement dataset v3 (300 SKUs, 57 months, with selling prices).
Run: python generate_dataset.py   (fixed seed -> reproducible). All data is artificially generated."""
import numpy as np, pandas as pd, sqlite3, os
rng = np.random.default_rng(4495)
OUT = os.path.dirname(os.path.abspath(__file__))
TODAY = pd.Timestamp("2026-10-07")
N_SKU = 300

cats = {  # profile, base monthly demand, unit cost, markup range (sell price = cost * markup), pack sizes
 "Seasonal-Holiday": ("holiday", (150, 600), (4, 18),  (1.6, 2.2), [6, 12, 24]),
 "Seasonal-Summer":  ("summer",  (120, 500), (6, 25),  (1.5, 2.0), [6, 12]),
 "Everyday":         ("flat",    (200, 900), (2, 12),  (1.3, 1.7), [12, 24, 48]),
 "Premium":          ("mild",    (60, 250),  (20, 90), (1.7, 2.4), [1, 4, 6]),
}
suppliers = {"Supplier A": 95, "Supplier B": 110, "Supplier C": 75, "Supplier D": 125, "Supplier E": 60, "Supplier F": 90,
             "Supplier G": 85, "Supplier H": 105, "Supplier I": 70, "Supplier J": 115}
prof = {
 "holiday": [.85,.80,.85,.90,.95,.90,.90,.95,1.1,1.45,1.9,2.1],
 "summer":  [.60,.65,.85,1.1,1.45,1.75,1.8,1.6,1.1,.8,.65,.6],
 "flat":    [1,.97,1,1,1.02,1.03,1.02,1.0,1.0,1.03,1.08,1.1],
 "mild":    [.9,.9,.95,1,1,1,.95,.95,1,1.05,1.2,1.3],
}
WH_SETS = [(["WH1"], [1.0]), (["WH1", "WH2"], [.65, .35]), (["WH1", "WH2", "WH3"], [.5, .3, .2])]

rows = []
for i in range(1, N_SKU + 1):
    cat = rng.choice(list(cats), p=[.3, .2, .35, .15])
    p, (dlo, dhi), (clo, chi), (mlo, mhi), packs = cats[cat]
    sup = rng.choice(list(suppliers))
    lt = int(np.clip(rng.normal(suppliers[sup], 10), 45, 140))
    cost = round(rng.uniform(clo, chi), 2)
    price = round(cost * rng.uniform(mlo, mhi) - 0.01, 2)  # ends in .99-style price
    wi = rng.choice(3, p=[.3, .45, .25])
    rows.append(dict(sku=f"SKU{i:03d}", category=cat, supplier_id=sup, pack_size=int(rng.choice(packs)),
        lead_time_days=lt, unit_cost=cost, selling_price=price, base_monthly_demand=int(rng.integers(dlo, dhi)),
        trend_pct_per_year=round(rng.normal(.04, .08), 3), profile=p, warehouses=",".join(WH_SETS[wi][0]), _wi=int(wi)))
prod = pd.DataFrame(rows)

# ---------- sales (monthly, per sku & warehouse) with prices ----------
months = pd.period_range("2022-01", "2026-09", freq="M")
sales = []
for _, r in prod.iterrows():
    whs, shares = WH_SETS[r._wi]
    promo_months = set(rng.choice(len(months), size=int(len(months) * .08), replace=False))  # ~8% promo months
    for k, m in enumerate(months):
        infl = 1.03 ** (k / 12)                                  # yearly price increase ~3%
        promo = k in promo_months
        disc = rng.uniform(.10, .30) if promo else 0.0
        price = round(r.selling_price * infl * (1 - disc), 2)
        uplift = (1 + disc * rng.uniform(3, 5)) if promo else 1.0  # promos lift demand
        seas = prof[r.profile][m.month - 1]
        trend = (1 + r.trend_pct_per_year) ** (k / 12)
        for wh, sh in zip(whs, shares):
            lam = r.base_monthly_demand * sh * seas * trend * uplift
            u = int(rng.negative_binomial(20, 20 / (20 + lam)))
            sales.append((r.sku, wh, str(m), u, price, int(promo)))
sales = pd.DataFrame(sales, columns=["sku", "warehouse", "month", "units_sold", "avg_selling_price", "promo_flag"])
idx = rng.choice(sales.index, int(len(sales) * .008), replace=False)  # a few low-sales / stock-out months
sales.loc[idx, "units_sold"] = (sales.loc[idx, "units_sold"] * .25).astype(int)
sales["revenue"] = (sales.units_sold * sales.avg_selling_price).round(2)

# ---------- current inventory & purchase orders ----------
def fwd_monthly(r):
    return np.mean([r.base_monthly_demand * prof[r.profile][(10 + j - 1) % 12] * (1 + r.trend_pct_per_year) ** ((len(months) + j) / 12) for j in range(4)])

inv, po, n = [], [], 0
for _, r in prod.iterrows():
    d = fwd_monthly(r)
    whs, shares = WH_SETS[r._wi]
    scenario = rng.choice(["risk", "ok", "excess"], p=[.3, .5, .2])
    cover_m = {"risk": rng.uniform(.8, 2.0), "ok": rng.uniform(2.5, 4.5), "excess": rng.uniform(6, 9)}[scenario]
    total_stock = int(d * cover_m)
    for wh, sh in zip(whs, shares):
        inv.append((r.sku, wh, int(total_stock * sh // r.pack_size * r.pack_size), str(TODAY.date())))
    n_open = int(rng.choice([0, 1, 2, 3, 4], p=[.1, .25, .35, .22, .08]))
    if scenario == "excess": n_open = max(n_open, 2)
    for j in range(n_open):
        elapsed = int(rng.integers(1, max(2, r.lead_time_days - 8)))
        odate = TODAY - pd.Timedelta(days=elapsed)
        eta = odate + pd.Timedelta(days=int(r.lead_time_days + rng.integers(-7, 10)))
        qty = int(max(1, d * rng.uniform(.8, 2.2)) // r.pack_size * r.pack_size) or r.pack_size
        n += 1
        status = "delayed" if rng.random() < .12 else ("in_transit" if elapsed > 30 else "ordered")
        po.append((f"PO{n:04d}", r.sku, r.supplier_id, whs[0] if len(whs) == 1 or rng.random() < .7 else whs[1],
                   f"CNT{rng.integers(1000, 9999)}", qty, r.unit_cost, round(qty * r.unit_cost, 2),
                   str(odate.date()), str(eta.date()), status, None))
    for j in range(int(rng.integers(8, 15))):  # received POs (history)
        recv = pd.Timestamp("2022-04-01") + pd.Timedelta(days=int(rng.integers(0, 1480)))
        act_lt = int(max(30, rng.normal(r.lead_time_days, 12)))
        odate = recv - pd.Timedelta(days=act_lt)
        qty = int(d * rng.uniform(.8, 2.0) // r.pack_size * r.pack_size) or r.pack_size
        n += 1
        po.append((f"PO{n:04d}", r.sku, r.supplier_id, whs[0], f"CNT{rng.integers(1000, 9999)}", qty, r.unit_cost,
                   round(qty * r.unit_cost, 2), str(odate.date()), str((odate + pd.Timedelta(days=int(r.lead_time_days))).date()),
                   "received", str(recv.date())))

inventory = pd.DataFrame(inv, columns=["sku", "warehouse", "on_hand_qty", "as_of_date"])
pos = pd.DataFrame(po, columns=["po_id", "sku", "supplier_id", "warehouse", "container_id", "quantity", "unit_cost", "total_cost",
                                "order_date", "expected_arrival_date", "status", "actual_arrival_date"])
products = prod.drop(columns=["base_monthly_demand", "trend_pct_per_year", "profile", "_wi"])
sales = sales[["sku", "warehouse", "month", "units_sold", "avg_selling_price", "revenue", "promo_flag"]]

tables = dict(products=products, sales_monthly=sales, inventory=inventory, purchase_orders=pos)
for k, v in tables.items(): v.to_csv(f"{OUT}/{k}.csv", index=False)
with sqlite3.connect(f"{OUT}/inventory.db") as c:
    for k, v in tables.items(): v.to_sql(k, c, if_exists="replace", index=False)
    c.execute("CREATE INDEX ix_sales ON sales_monthly(sku, month)"); c.execute("CREATE INDEX ix_po ON purchase_orders(sku, status)")
for k, v in tables.items(): print(k, v.shape)
