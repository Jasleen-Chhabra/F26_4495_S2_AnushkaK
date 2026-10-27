import streamlit as st
import pandas as pd
import plotly.express as px
import math


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Inventory & Procurement Decision-Support System",
    page_icon="📦",
    layout="wide"
)


# ============================================================
# LOAD DATA
# ============================================================

products = pd.read_csv("Data/products.csv")
inventory = pd.read_csv("Data/inventory.csv")
purchase_orders = pd.read_csv("Data/purchase_orders.csv")
sales = pd.read_csv("Data/sales_monthly.csv")


# ============================================================
# DATE CONVERSIONS
# ============================================================

sales["month"] = pd.to_datetime(
    sales["month"],
    errors="coerce"
)

inventory["as_of_date"] = pd.to_datetime(
    inventory["as_of_date"],
    errors="coerce"
)

purchase_orders["order_date"] = pd.to_datetime(
    purchase_orders["order_date"],
    errors="coerce"
)

purchase_orders["expected_arrival_date"] = pd.to_datetime(
    purchase_orders["expected_arrival_date"],
    errors="coerce"
)

purchase_orders["actual_arrival_date"] = pd.to_datetime(
    purchase_orders["actual_arrival_date"],
    errors="coerce"
)


# ============================================================
# SIDEBAR NAVIGATION
# ============================================================

st.sidebar.title("Navigation")

page = st.sidebar.radio(
    "Go to",
    [
        "Overview",
        "Sales & Financials",
        "Inventory & Procurement",
        "Supplier Performance",
        "SKU Analysis",
        "Scenario Planner"
    ]
)

st.sidebar.markdown("---")

st.sidebar.write(
    "CSIS 4495 Applied Research Project"
)

st.sidebar.caption(
    "Inventory & Procurement Decision-Support System"
)

with st.sidebar.expander("Tech Stack"):

    st.write("Python")
    st.write("Streamlit")
    st.write("pandas")
    st.write("Plotly")
    st.write("CSV Dataset")
    st.write("SQLite Dataset Available")
    st.write("GitHub Version Control")


# ============================================================
# GENERAL REPORTING PERIOD
# ============================================================

latest_sales_month = sales["month"].max()

current_year = latest_sales_month.year
current_month_number = latest_sales_month.month
previous_year = current_year - 1

data_through = latest_sales_month.strftime("%b %Y")


# ============================================================
# CURRENT / PREVIOUS YEAR SALES
# ============================================================

current_ytd_sales = sales[
    (
        sales["month"].dt.year
        == current_year
    )
    &
    (
        sales["month"].dt.month
        <= current_month_number
    )
].copy()


previous_ytd_sales = sales[
    (
        sales["month"].dt.year
        == previous_year
    )
    &
    (
        sales["month"].dt.month
        <= current_month_number
    )
].copy()


previous_full_year_sales = sales[
    sales["month"].dt.year
    == previous_year
].copy()


# ============================================================
# HELPER FUNCTION
# INVENTORY PROJECTION
# ============================================================

def calculate_sku_projection(
    selected_sku,
    demand_increase_pct=0,
    shipment_delay_days=0
):

    selected_sales = sales[
        sales["sku"] == selected_sku
    ].copy()

    selected_inventory = inventory[
        inventory["sku"] == selected_sku
    ].copy()

    selected_pos = purchase_orders[
        (
            purchase_orders["sku"] == selected_sku
        )
        &
        (
            purchase_orders["status"].isin(
                [
                    "ordered",
                    "in_transit",
                    "delayed"
                ]
            )
        )
    ].copy()


    if selected_sales.empty or selected_inventory.empty:
        return None


    monthly_sales = (
        selected_sales
        .groupby(
            "month",
            as_index=False
        )["units_sold"]
        .sum()
        .sort_values("month")
    )


    if monthly_sales.empty:
        return None


    base_forecast = (
        monthly_sales
        .tail(3)["units_sold"]
        .mean()
    )


    adjusted_forecast = (
        base_forecast
        *
        (
            1
            +
            demand_increase_pct / 100
        )
    )


    forecast_demand = int(
        round(adjusted_forecast)
    )


    total_inventory = int(
        selected_inventory[
            "on_hand_qty"
        ].sum()
    )


    inventory_date = (
        selected_inventory[
            "as_of_date"
        ].max()
    )


    if not selected_pos.empty:

        selected_pos[
            "scenario_arrival_date"
        ] = (
            selected_pos[
                "expected_arrival_date"
            ]
            +
            pd.to_timedelta(
                shipment_delay_days,
                unit="D"
            )
        )

    else:

        selected_pos[
            "scenario_arrival_date"
        ] = pd.NaT


    total_incoming = int(
        selected_pos[
            "quantity"
        ].sum()
    )


    projection_start = (
        inventory_date
        .to_period("M")
        .to_timestamp()
    )


    future_months = pd.date_range(
        start=projection_start,
        periods=12,
        freq="MS"
    )


    opening_inventory = total_inventory

    projection_rows = []


    for month in future_months:

        month_start = month

        month_end = (
            month
            + pd.offsets.MonthEnd(1)
        )


        incoming_this_month = (
            selected_pos[
                (
                    selected_pos[
                        "scenario_arrival_date"
                    ] >= month_start
                )
                &
                (
                    selected_pos[
                        "scenario_arrival_date"
                    ] <= month_end
                )
            ]["quantity"].sum()
        )


        closing_inventory = (
            opening_inventory
            +
            int(incoming_this_month)
            -
            forecast_demand
        )


        projection_rows.append(
            {
                "Month Date": month,
                "Month": month.strftime("%b %Y"),
                "Opening Inventory": opening_inventory,
                "Incoming": int(incoming_this_month),
                "Forecast Demand": forecast_demand,
                "Closing Inventory": closing_inventory
            }
        )


        opening_inventory = closing_inventory


    projection_df = pd.DataFrame(
        projection_rows
    )


    shortage_rows = projection_df[
        projection_df[
            "Closing Inventory"
        ] < 0
    ]


    if shortage_rows.empty:

        shortage_month = None

    else:

        shortage_month = (
            shortage_rows
            .iloc[0]["Month Date"]
        )


    return {

        "base_forecast":
            base_forecast,

        "adjusted_forecast":
            adjusted_forecast,

        "projection":
            projection_df,

        "shortage_month":
            shortage_month,

        "current_inventory":
            total_inventory,

        "incoming_quantity":
            total_incoming
    }


# ============================================================
# HELPER FUNCTION
# REORDER RECOMMENDATION
# ============================================================

def calculate_reorder(
    product,
    forecast_value,
    shortage_month
):

    if shortage_month is None:
        return None


    lead_time_days = int(
        product[
            "lead_time_days"
        ]
    )


    suggested_order_date = (
        shortage_month
        -
        pd.Timedelta(
            days=lead_time_days
        )
    )


    raw_order_quantity = (
        forecast_value
        * 3
    )


    pack_size = int(
        product[
            "pack_size"
        ]
    )


    suggested_order_quantity = (
        math.ceil(
            raw_order_quantity
            /
            pack_size
        )
        *
        pack_size
    )


    return {

        "order_date":
            suggested_order_date,

        "order_quantity":
            suggested_order_quantity
    }


# ============================================================
# EXECUTIVE KPI CALCULATIONS
# ============================================================

current_ytd_units = int(
    current_ytd_sales[
        "units_sold"
    ].sum()
)


previous_ytd_units = int(
    previous_ytd_sales[
        "units_sold"
    ].sum()
)


if previous_ytd_units > 0:

    yoy_units_change = (
        (
            current_ytd_units
            -
            previous_ytd_units
        )
        /
        previous_ytd_units
    ) * 100

else:

    yoy_units_change = 0


current_ytd_revenue = (
    current_ytd_sales[
        "revenue"
    ].sum()
)


previous_ytd_revenue = (
    previous_ytd_sales[
        "revenue"
    ].sum()
)


previous_full_year_revenue = (
    previous_full_year_sales[
        "revenue"
    ].sum()
)


if previous_ytd_revenue > 0:

    yoy_revenue_change = (
        (
            current_ytd_revenue
            -
            previous_ytd_revenue
        )
        /
        previous_ytd_revenue
    ) * 100

else:

    yoy_revenue_change = 0


revenue_gap_to_last_year = max(
    previous_full_year_revenue
    -
    current_ytd_revenue,
    0
)


# ============================================================
# ESTIMATED GROSS PROFIT
# ============================================================

financial_sales = (
    current_ytd_sales.merge(
        products[
            [
                "sku",
                "unit_cost"
            ]
        ],
        on="sku",
        how="left"
    )
)


financial_sales[
    "estimated_cogs"
] = (
    financial_sales[
        "units_sold"
    ]
    *
    financial_sales[
        "unit_cost"
    ]
)


estimated_cogs = (
    financial_sales[
        "estimated_cogs"
    ].sum()
)


estimated_gross_profit = (
    current_ytd_revenue
    -
    estimated_cogs
)


if current_ytd_revenue > 0:

    gross_margin = (
        estimated_gross_profit
        /
        current_ytd_revenue
    ) * 100

else:

    gross_margin = 0


# ============================================================
# INVENTORY VALUE
# ============================================================

inventory_with_cost = (
    inventory.merge(
        products[
            [
                "sku",
                "unit_cost"
            ]
        ],
        on="sku",
        how="left"
    )
)


inventory_with_cost[
    "inventory_value"
] = (
    inventory_with_cost[
        "on_hand_qty"
    ]
    *
    inventory_with_cost[
        "unit_cost"
    ]
)


total_inventory_value = (
    inventory_with_cost[
        "inventory_value"
    ].sum()
)


total_inventory_units = int(
    inventory[
        "on_hand_qty"
    ].sum()
)


# ============================================================
# OPEN PURCHASE ORDERS
# ============================================================

open_purchase_orders = (
    purchase_orders[
        purchase_orders[
            "status"
        ].isin(
            [
                "ordered",
                "in_transit",
                "delayed"
            ]
        )
    ].copy()
)


total_open_po_value = (
    open_purchase_orders[
        "total_cost"
    ].sum()
)


total_open_po_units = int(
    open_purchase_orders[
        "quantity"
    ].sum()
)


delayed_po_count = len(
    open_purchase_orders[
        open_purchase_orders[
            "status"
        ] == "delayed"
    ]
)


# ============================================================
# TOP PRODUCTS
# ============================================================

sku_sales_ytd = (
    current_ytd_sales
    .groupby(
        "sku",
        as_index=False
    )
    .agg(
        units_sold=(
            "units_sold",
            "sum"
        ),
        revenue=(
            "revenue",
            "sum"
        )
    )
)


top_by_units = (
    sku_sales_ytd
    .sort_values(
        "units_sold",
        ascending=False
    )
)


top_by_revenue = (
    sku_sales_ytd
    .sort_values(
        "revenue",
        ascending=False
    )
)


if not top_by_units.empty:

    top_units_sku = (
        top_by_units
        .iloc[0]["sku"]
    )

    top_units_value = int(
        top_by_units
        .iloc[0]["units_sold"]
    )

else:

    top_units_sku = "N/A"
    top_units_value = 0


if not top_by_revenue.empty:

    top_revenue_sku = (
        top_by_revenue
        .iloc[0]["sku"]
    )

    top_revenue_value = (
        top_by_revenue
        .iloc[0]["revenue"]
    )

else:

    top_revenue_sku = "N/A"
    top_revenue_value = 0


# ============================================================
# INVENTORY RISK CALCULATION
# ============================================================

risk_rows = []


for sku in products["sku"]:

    result = (
        calculate_sku_projection(
            sku
        )
    )


    if result is None:
        continue


    shortage_month = (
        result[
            "shortage_month"
        ]
    )


    product_row = products[
        products[
            "sku"
        ] == sku
    ].iloc[0]


    forecast = result[
        "base_forecast"
    ]


    current_stock = result[
        "current_inventory"
    ]


    if forecast > 0:

        months_cover = (
            current_stock
            /
            forecast
        )

    else:

        months_cover = 0


    if months_cover < 2:

        inventory_health = "At Risk"

    elif months_cover > 6:

        inventory_health = "Excess"

    else:

        inventory_health = "Healthy"


    if shortage_month is not None:

        risk_rows.append(
            {
                "SKU": sku,
                "Current Stock": current_stock,
                "Forecast / Month": round(
                    forecast
                ),
                "Incoming": result[
                    "incoming_quantity"
                ],
                "Projected Shortage":
                    shortage_month.strftime(
                        "%b %Y"
                    ),
                "Lead Time (Days)":
                    int(
                        product_row[
                            "lead_time_days"
                        ]
                    ),
                "Shortage Date":
                    shortage_month
            }
        )


risk_df = pd.DataFrame(
    risk_rows
)


if not risk_df.empty:

    risk_df = (
        risk_df.sort_values(
            "Shortage Date"
        )
    )


risk_count = len(
    risk_df
)


# ============================================================
# INVENTORY HEALTH
# ============================================================

inventory_health_rows = []


for sku in products["sku"]:

    result = (
        calculate_sku_projection(
            sku
        )
    )

    if result is None:
        continue


    forecast = (
        result[
            "base_forecast"
        ]
    )

    current_stock = (
        result[
            "current_inventory"
        ]
    )


    if forecast > 0:

        months_cover = (
            current_stock
            /
            forecast
        )

    else:

        months_cover = 0


    if months_cover < 2:

        health = "At Risk"

    elif months_cover > 6:

        health = "Excess"

    else:

        health = "Healthy"


    inventory_health_rows.append(
        {
            "SKU": sku,
            "Health": health,
            "Months Cover": months_cover
        }
    )


inventory_health_df = pd.DataFrame(
    inventory_health_rows
)


inventory_health_summary = (
    inventory_health_df[
        "Health"
    ]
    .value_counts()
    .reset_index()
)


inventory_health_summary.columns = [
    "Health",
    "Products"
]


# ============================================================
# SUPPLIER PERFORMANCE CALCULATIONS
# ============================================================

supplier_rows = []


for supplier in sorted(
    purchase_orders[
        "supplier_id"
    ].dropna().unique()
):

    supplier_orders = (
        purchase_orders[
            purchase_orders[
                "supplier_id"
            ] == supplier
        ].copy()
    )


    received_orders = (
        supplier_orders[
            supplier_orders[
                "status"
            ] == "received"
        ].copy()
    )


    open_orders = (
        supplier_orders[
            supplier_orders[
                "status"
            ].isin(
                [
                    "ordered",
                    "in_transit",
                    "delayed"
                ]
            )
        ].copy()
    )


    delayed_orders = (
        open_orders[
            open_orders[
                "status"
            ] == "delayed"
        ]
    )


    if not received_orders.empty:

        received_orders[
            "actual_lead_days"
        ] = (
            received_orders[
                "actual_arrival_date"
            ]
            -
            received_orders[
                "order_date"
            ]
        ).dt.days


        valid_on_time = (
            received_orders[
                "actual_arrival_date"
            ].notna()
            &
            received_orders[
                "expected_arrival_date"
            ].notna()
        )


        valid_received = (
            received_orders[
                valid_on_time
            ]
        )


        if not valid_received.empty:

            on_time_count = (
                valid_received[
                    "actual_arrival_date"
                ]
                <=
                valid_received[
                    "expected_arrival_date"
                ]
            ).sum()


            on_time_rate = (
                on_time_count
                /
                len(valid_received)
            ) * 100

        else:

            on_time_rate = 0


        avg_actual_lead = (
            received_orders[
                "actual_lead_days"
            ].mean()
        )

    else:

        on_time_rate = 0
        avg_actual_lead = 0


    open_po_value = (
        open_orders[
            "total_cost"
        ].sum()
    )


    supplier_rows.append(
        {
            "Supplier": supplier,
            "Total Orders": len(
                supplier_orders
            ),
            "Received Orders": len(
                received_orders
            ),
            "Open Orders": len(
                open_orders
            ),
            "Delayed Open Orders": len(
                delayed_orders
            ),
            "On-Time %": round(
                on_time_rate,
                1
            ),
            "Avg Actual Lead Time": round(
                avg_actual_lead,
                1
            ),
            "Open PO Value": round(
                open_po_value,
                2
            )
        }
    )


supplier_performance = pd.DataFrame(
    supplier_rows
)


# ============================================================
# PAGE 1 - OVERVIEW
# ============================================================

if page == "Overview":

    st.title(
        "Executive Business Overview"
    )

    st.write(
        "A quick management view of company performance, "
        "inventory risk and procurement activity."
    )

    st.caption(
        f"Data through {data_through}"
    )

    st.markdown("---")


    # --------------------------------------------------------
    # EXECUTIVE SUMMARY
    # --------------------------------------------------------

    st.subheader(
        "Executive Summary"
    )


    if yoy_revenue_change >= 0:

        revenue_message = (
            f"Revenue is {abs(yoy_revenue_change):.1f}% "
            f"above the same period last year."
        )

    else:

        revenue_message = (
            f"Revenue is {abs(yoy_revenue_change):.1f}% "
            f"below the same period last year."
        )


    summary_text = (
        f"{revenue_message} "
        f"{risk_count} products are projected to experience "
        f"a shortage within the next 12 months. "
        f"{delayed_po_count} purchase orders are currently delayed. "
        f"The highest-revenue product YTD is {top_revenue_sku}."
    )


    st.info(
        summary_text
    )


    # --------------------------------------------------------
    # BUSINESS HEALTH
    # --------------------------------------------------------

    st.subheader(
        "Business Health"
    )


    h1, h2, h3, h4 = st.columns(4)


    with h1:

        if yoy_revenue_change >= 0:

            st.success(
                f"Revenue\n\n"
                f"{yoy_revenue_change:+.1f}% YoY"
            )

        else:

            st.error(
                f"Revenue\n\n"
                f"{yoy_revenue_change:+.1f}% YoY"
            )


    with h2:

        if yoy_units_change >= 0:

            st.success(
                f"Unit Sales\n\n"
                f"{yoy_units_change:+.1f}% YoY"
            )

        else:

            st.error(
                f"Unit Sales\n\n"
                f"{yoy_units_change:+.1f}% YoY"
            )


    with h3:

        risk_percentage = (
            risk_count
            /
            len(products)
        ) * 100


        if risk_percentage >= 50:

            st.error(
                f"Inventory Risk\n\n"
                f"{risk_count} products"
            )

        elif risk_percentage >= 20:

            st.warning(
                f"Inventory Risk\n\n"
                f"{risk_count} products"
            )

        else:

            st.success(
                f"Inventory Risk\n\n"
                f"{risk_count} products"
            )


    with h4:

        if delayed_po_count == 0:

            st.success(
                "PO Health\n\n"
                "No delays"
            )

        elif delayed_po_count <= 10:

            st.warning(
                f"PO Health\n\n"
                f"{delayed_po_count} delayed"
            )

        else:

            st.error(
                f"PO Health\n\n"
                f"{delayed_po_count} delayed"
            )


    st.markdown("---")


    # --------------------------------------------------------
    # KEY KPIS
    # --------------------------------------------------------

    st.subheader(
        "Key Business Indicators"
    )


    k1, k2, k3, k4 = st.columns(4)


    with k1:

        st.metric(
            "Revenue YTD",
            f"${current_ytd_revenue:,.0f}",
            f"{yoy_revenue_change:+.1f}%"
        )


    with k2:

        st.metric(
            "Estimated Gross Profit",
            f"${estimated_gross_profit:,.0f}"
        )

        st.caption(
            f"Gross margin: {gross_margin:.1f}%"
        )


    with k3:

        st.metric(
            "Inventory Value",
            f"${total_inventory_value:,.0f}"
        )


    with k4:

        st.metric(
            "Open PO Value",
            f"${total_open_po_value:,.0f}"
        )


    k5, k6, k7, k8 = st.columns(4)


    with k5:

        st.metric(
            "Units Sold YTD",
            f"{current_ytd_units:,}",
            f"{yoy_units_change:+.1f}%"
        )


    with k6:

        st.metric(
            "Top SKU by Revenue",
            top_revenue_sku
        )

        st.caption(
            f"${top_revenue_value:,.0f}"
        )


    with k7:

        st.metric(
            "Products at Risk",
            risk_count
        )


    with k8:

        st.metric(
            "Delayed POs",
            delayed_po_count
        )


    st.markdown("---")


    # --------------------------------------------------------
    # REVENUE TREND
    # --------------------------------------------------------

    st.subheader(
        "Revenue Performance"
    )


    revenue_monthly = (
        sales[
            sales[
                "month"
            ].dt.year.isin(
                [
                    previous_year,
                    current_year
                ]
            )
        ]
        .groupby(
            [
                sales[
                    "month"
                ].dt.year.rename("Year"),
                sales[
                    "month"
                ].dt.month.rename("Month Number")
            ]
        )["revenue"]
        .sum()
        .reset_index()
    )


    month_names = {
        1: "Jan",
        2: "Feb",
        3: "Mar",
        4: "Apr",
        5: "May",
        6: "Jun",
        7: "Jul",
        8: "Aug",
        9: "Sep",
        10: "Oct",
        11: "Nov",
        12: "Dec"
    }


    revenue_monthly[
        "Month"
    ] = (
        revenue_monthly[
            "Month Number"
        ].map(
            month_names
        )
    )


    revenue_monthly[
        "Year"
    ] = (
        revenue_monthly[
            "Year"
        ].astype(str)
    )


    revenue_chart = px.line(
        revenue_monthly,
        x="Month",
        y="revenue",
        color="Year",
        markers=True,
        title=(
            f"Monthly Revenue: "
            f"{previous_year} vs {current_year}"
        )
    )


    revenue_chart.update_layout(
        xaxis_title="Month",
        yaxis_title="Revenue ($)"
    )


    st.plotly_chart(
        revenue_chart,
        width="stretch"
    )


    # --------------------------------------------------------
    # INVENTORY HEALTH + TOP PRODUCTS
    # --------------------------------------------------------

    c1, c2 = st.columns(2)


    with c1:

        st.subheader(
            "Inventory Health"
        )


        health_chart = px.pie(
            inventory_health_summary,
            names="Health",
            values="Products",
            title="Inventory Health by Product"
        )


        st.plotly_chart(
            health_chart,
            width="stretch"
        )


    with c2:

        st.subheader(
            "Top Products"
        )


        top_5 = (
            top_by_revenue
            .head(5)
        )


        top_chart = px.bar(
            top_5,
            x="sku",
            y="revenue",
            title="Top 5 SKUs by Revenue"
        )


        st.plotly_chart(
            top_chart,
            width="stretch"
        )


    # --------------------------------------------------------
    # PRIORITY ACTION LIST
    # --------------------------------------------------------

    st.subheader(
        "Priority Action List"
    )


    if not risk_df.empty:

        top_risk = (
            risk_df
            .head(5)
        )


        for _, row in top_risk.iterrows():

            st.warning(
                f"{row['SKU']} — projected shortage "
                f"{row['Projected Shortage']} | "
                f"Lead time {row['Lead Time (Days)']} days"
            )


    if delayed_po_count > 0:

        st.warning(
            f"{delayed_po_count} purchase orders "
            "are currently marked as delayed."
        )


    if yoy_revenue_change >= 0:

        st.success(
            f"Revenue YTD is {yoy_revenue_change:.1f}% "
            "ahead of the same period last year."
        )


# ============================================================
# PAGE 2 - SALES & FINANCIALS
# ============================================================

elif page == "Sales & Financials":

    st.title(
        "Sales & Financial Performance"
    )

    st.caption(
        f"Data through {data_through}"
    )


    f1, f2, f3, f4 = st.columns(4)


    with f1:

        st.metric(
            "Revenue YTD",
            f"${current_ytd_revenue:,.0f}",
            f"{yoy_revenue_change:+.1f}%"
        )


    with f2:

        st.metric(
            "Estimated Gross Profit",
            f"${estimated_gross_profit:,.0f}"
        )


    with f3:

        st.metric(
            "Gross Margin",
            f"{gross_margin:.1f}%"
        )


    with f4:

        st.metric(
            f"Revenue Needed to Match {previous_year}",
            f"${revenue_gap_to_last_year:,.0f}"
        )


    st.caption(
        "Gross profit is an estimate based on revenue minus "
        "product unit cost. Operating expenses are not included."
    )


    st.markdown("---")


    # --------------------------------------------------------
    # CATEGORY PERFORMANCE
    # --------------------------------------------------------

    category_sales = (
        current_ytd_sales.merge(
            products[
                [
                    "sku",
                    "category"
                ]
            ],
            on="sku",
            how="left"
        )
    )


    category_summary = (
        category_sales
        .groupby(
            "category",
            as_index=False
        )
        .agg(
            Revenue=(
                "revenue",
                "sum"
            ),
            Units=(
                "units_sold",
                "sum"
            )
        )
        .sort_values(
            "Revenue",
            ascending=False
        )
    )


    st.subheader(
        "Category Performance"
    )


    category_chart = px.bar(
        category_summary,
        x="category",
        y="Revenue",
        title="Revenue by Product Category"
    )


    st.plotly_chart(
        category_chart,
        width="stretch"
    )


    st.dataframe(
        category_summary,
        width="stretch",
        hide_index=True
    )


    # --------------------------------------------------------
    # TOP PRODUCTS
    # --------------------------------------------------------

    st.subheader(
        "Top Products"
    )


    c1, c2 = st.columns(2)


    with c1:

        top_rev = (
            top_by_revenue
            .head(10)
        )


        chart = px.bar(
            top_rev,
            x="sku",
            y="revenue",
            title="Top 10 SKUs by Revenue"
        )


        st.plotly_chart(
            chart,
            width="stretch"
        )


    with c2:

        top_units = (
            top_by_units
            .head(10)
        )


        chart = px.bar(
            top_units,
            x="sku",
            y="units_sold",
            title="Top 10 SKUs by Units Sold"
        )


        st.plotly_chart(
            chart,
            width="stretch"
        )


# ============================================================
# PAGE 3 - INVENTORY & PROCUREMENT
# ============================================================

elif page == "Inventory & Procurement":

    st.title(
        "Inventory & Procurement"
    )


    i1, i2, i3, i4 = st.columns(4)


    with i1:

        st.metric(
            "Inventory Value",
            f"${total_inventory_value:,.0f}"
        )


    with i2:

        st.metric(
            "Inventory Units",
            f"{total_inventory_units:,}"
        )


    with i3:

        st.metric(
            "Open PO Value",
            f"${total_open_po_value:,.0f}"
        )


    with i4:

        st.metric(
            "Delayed POs",
            delayed_po_count
        )


    st.markdown("---")


    st.subheader(
        "Inventory Health"
    )


    health_chart = px.bar(
        inventory_health_summary,
        x="Health",
        y="Products",
        title="Product Inventory Health"
    )


    st.plotly_chart(
        health_chart,
        width="stretch"
    )


    st.subheader(
        "Products Requiring Attention"
    )


    if risk_df.empty:

        st.success(
            "No shortages projected."
        )

    else:

        risk_display = (
            risk_df[
                [
                    "SKU",
                    "Current Stock",
                    "Forecast / Month",
                    "Incoming",
                    "Projected Shortage",
                    "Lead Time (Days)"
                ]
            ]
        )


        st.dataframe(
            risk_display,
            width="stretch",
            hide_index=True
        )


    st.subheader(
        "Upcoming Purchase Orders"
    )


    upcoming_pos = (
        open_purchase_orders[
            [
                "po_id",
                "supplier_id",
                "sku",
                "warehouse",
                "quantity",
                "expected_arrival_date",
                "status",
                "total_cost"
            ]
        ]
        .sort_values(
            "expected_arrival_date"
        )
    )


    st.dataframe(
        upcoming_pos,
        width="stretch",
        hide_index=True
    )


    st.subheader(
        "Delayed Purchase Orders"
    )


    delayed_pos = (
        open_purchase_orders[
            open_purchase_orders[
                "status"
            ] == "delayed"
        ]
    )


    if delayed_pos.empty:

        st.success(
            "No delayed purchase orders."
        )

    else:

        st.dataframe(
            delayed_pos[
                [
                    "po_id",
                    "supplier_id",
                    "sku",
                    "quantity",
                    "expected_arrival_date",
                    "total_cost"
                ]
            ],
            width="stretch",
            hide_index=True
        )


# ============================================================
# PAGE 4 - SUPPLIER PERFORMANCE
# ============================================================

elif page == "Supplier Performance":

    st.title(
        "Supplier Performance"
    )

    st.write(
        "Supplier reliability, lead-time performance "
        "and open purchase-order exposure."
    )


    if supplier_performance.empty:

        st.info(
            "No supplier data available."
        )

    else:

        reliable_supplier = (
            supplier_performance
            .sort_values(
                "On-Time %",
                ascending=False
            )
            .iloc[0]
        )


        delay_supplier = (
            supplier_performance
            .sort_values(
                "Delayed Open Orders",
                ascending=False
            )
            .iloc[0]
        )


        shortest_lead_supplier = (
            supplier_performance
            .sort_values(
                "Avg Actual Lead Time",
                ascending=True
            )
            .iloc[0]
        )


        s1, s2, s3, s4 = st.columns(4)


        with s1:

            st.metric(
                "Suppliers",
                len(
                    supplier_performance
                )
            )


        with s2:

            st.metric(
                "Most Reliable",
                reliable_supplier[
                    "Supplier"
                ]
            )

            st.caption(
                f"{reliable_supplier['On-Time %']:.1f}% on time"
            )


        with s3:

            st.metric(
                "Most Delayed",
                delay_supplier[
                    "Supplier"
                ]
            )

            st.caption(
                f"{int(delay_supplier['Delayed Open Orders'])} delayed open POs"
            )


        with s4:

            st.metric(
                "Shortest Avg Lead Time",
                shortest_lead_supplier[
                    "Supplier"
                ]
            )

            st.caption(
                f"{shortest_lead_supplier['Avg Actual Lead Time']:.0f} days"
            )


        st.markdown("---")


        # --------------------------------------------------------
        # SUPPLIER RELIABILITY
        # --------------------------------------------------------

        st.subheader(
            "Supplier Reliability"
        )


        reliability_chart = px.bar(
            supplier_performance
            .sort_values(
                "On-Time %",
                ascending=False
            ),
            x="Supplier",
            y="On-Time %",
            title="On-Time Delivery Rate by Supplier"
        )


        reliability_chart.update_layout(
            yaxis_title="On-Time Delivery (%)"
        )


        st.plotly_chart(
            reliability_chart,
            width="stretch"
        )


        # --------------------------------------------------------
        # LEAD TIME
        # --------------------------------------------------------

        st.subheader(
            "Average Actual Lead Time"
        )


        lead_chart = px.bar(
            supplier_performance
            .sort_values(
                "Avg Actual Lead Time"
            ),
            x="Supplier",
            y="Avg Actual Lead Time",
            title="Average Actual Lead Time by Supplier"
        )


        lead_chart.update_layout(
            yaxis_title="Days"
        )


        st.plotly_chart(
            lead_chart,
            width="stretch"
        )


        # --------------------------------------------------------
        # SUPPLIER TABLE
        # --------------------------------------------------------

        st.subheader(
            "Supplier Scorecard"
        )


        supplier_display = (
            supplier_performance
            .sort_values(
                "On-Time %",
                ascending=False
            )
        )


        st.dataframe(
            supplier_display,
            width="stretch",
            hide_index=True
        )


        # --------------------------------------------------------
        # SUPPLIER DETAIL
        # --------------------------------------------------------

        st.subheader(
            "Supplier Drill-Down"
        )


        selected_supplier = st.selectbox(
            "Select Supplier",
            sorted(
                supplier_performance[
                    "Supplier"
                ]
            )
        )


        selected_supplier_orders = (
            purchase_orders[
                purchase_orders[
                    "supplier_id"
                ] == selected_supplier
            ]
            .copy()
        )


        open_supplier_orders = (
            selected_supplier_orders[
                selected_supplier_orders[
                    "status"
                ].isin(
                    [
                        "ordered",
                        "in_transit",
                        "delayed"
                    ]
                )
            ]
        )


        st.write(
            f"Open purchase orders for {selected_supplier}"
        )


        if open_supplier_orders.empty:

            st.success(
                "No open purchase orders."
            )

        else:

            st.dataframe(
                open_supplier_orders[
                    [
                        "po_id",
                        "sku",
                        "quantity",
                        "order_date",
                        "expected_arrival_date",
                        "status",
                        "total_cost"
                    ]
                ],
                width="stretch",
                hide_index=True
            )


# ============================================================
# PAGE 5 - SKU ANALYSIS
# ============================================================

elif page == "SKU Analysis":

    st.title(
        "SKU Analysis"
    )

    st.write(
        "Detailed product-level inventory planning, "
        "forecasting and reorder analysis."
    )


    selected_sku = st.selectbox(
        "Choose SKU",
        products[
            "sku"
        ]
    )


    product = (
        products[
            products[
                "sku"
            ] == selected_sku
        ]
        .iloc[0]
    )


    # --------------------------------------------------------
    # PRODUCT DETAILS
    # --------------------------------------------------------

    st.subheader(
        "Product Details"
    )


    p1, p2, p3, p4 = st.columns(4)


    with p1:

        st.metric(
            "Category",
            product[
                "category"
            ]
        )


    with p2:

        st.metric(
            "Supplier",
            product[
                "supplier_id"
            ]
        )


    with p3:

        st.metric(
            "Lead Time",
            f'{product["lead_time_days"]} days'
        )


    with p4:

        st.metric(
            "Pack Size",
            product[
                "pack_size"
            ]
        )


    p5, p6, p7 = st.columns(3)


    with p5:

        st.metric(
            "Unit Cost",
            f'${product["unit_cost"]:.2f}'
        )


    with p6:

        st.metric(
            "Selling Price",
            f'${product["selling_price"]:.2f}'
        )


    with p7:

        st.metric(
            "Warehouse(s)",
            product[
                "warehouses"
            ]
        )


    # --------------------------------------------------------
    # CURRENT INVENTORY
    # --------------------------------------------------------

    selected_inventory = (
        inventory[
            inventory[
                "sku"
            ] == selected_sku
        ]
        .copy()
    )


    total_inventory = (
        selected_inventory[
            "on_hand_qty"
        ].sum()
    )


    st.subheader(
        "Current Inventory"
    )


    st.metric(
        "Total On-Hand Inventory",
        f"{int(total_inventory):,} units"
    )


    st.dataframe(
        selected_inventory[
            [
                "warehouse",
                "on_hand_qty",
                "as_of_date"
            ]
        ],
        width="stretch",
        hide_index=True
    )


    # --------------------------------------------------------
    # PURCHASE ORDERS
    # --------------------------------------------------------

    selected_pos = (
        purchase_orders[
            (
                purchase_orders[
                    "sku"
                ] == selected_sku
            )
            &
            (
                purchase_orders[
                    "status"
                ].isin(
                    [
                        "ordered",
                        "in_transit",
                        "delayed"
                    ]
                )
            )
        ]
        .copy()
    )


    st.subheader(
        "Incoming Purchase Orders"
    )


    if selected_pos.empty:

        st.info(
            "No open purchase orders."
        )

    else:

        st.metric(
            "Incoming Quantity",
            f'{int(selected_pos["quantity"].sum()):,} units'
        )


        st.dataframe(
            selected_pos[
                [
                    "po_id",
                    "supplier_id",
                    "container_id",
                    "warehouse",
                    "quantity",
                    "expected_arrival_date",
                    "status",
                    "total_cost"
                ]
            ],
            width="stretch",
            hide_index=True
        )


    # --------------------------------------------------------
    # SALES HISTORY
    # --------------------------------------------------------

    selected_sales = (
        sales[
            sales[
                "sku"
            ] == selected_sku
        ]
        .copy()
    )


    monthly_sales = (
        selected_sales
        .groupby(
            "month",
            as_index=False
        )
        .agg(
            units_sold=(
                "units_sold",
                "sum"
            ),
            revenue=(
                "revenue",
                "sum"
            )
        )
        .sort_values(
            "month"
        )
    )


    st.subheader(
        "Historical Sales"
    )


    st.metric(
        "Average Monthly Sales",
        f'{monthly_sales["units_sold"].mean():.0f} units'
    )


    sales_chart = px.line(
        monthly_sales,
        x="month",
        y="units_sold",
        markers=True,
        title="Monthly Sales History"
    )


    st.plotly_chart(
        sales_chart,
        width="stretch"
    )


    # --------------------------------------------------------
    # FORECAST
    # --------------------------------------------------------

    result = (
        calculate_sku_projection(
            selected_sku
        )
    )


    st.subheader(
        "Demand Forecast"
    )


    st.metric(
        "3-Month Moving Average",
        f'{result["base_forecast"]:.0f} units/month'
    )


    st.write(
        "The baseline forecast uses the average "
        "sales of the most recent three months."
    )


    # --------------------------------------------------------
    # INVENTORY PROJECTION
    # --------------------------------------------------------

    projection = (
        result[
            "projection"
        ]
    )


    shortage = (
        result[
            "shortage_month"
        ]
    )


    st.subheader(
        "Projected Inventory"
    )


    st.dataframe(
        projection[
            [
                "Month",
                "Opening Inventory",
                "Incoming",
                "Forecast Demand",
                "Closing Inventory"
            ]
        ],
        width="stretch",
        hide_index=True
    )


    projection_chart = px.line(
        projection,
        x="Month",
        y="Closing Inventory",
        markers=True,
        title="Projected Inventory"
    )


    st.plotly_chart(
        projection_chart,
        width="stretch"
    )


    # --------------------------------------------------------
    # REORDER
    # --------------------------------------------------------

    st.subheader(
        "Reorder Recommendation"
    )


    reorder = (
        calculate_reorder(
            product,
            result[
                "base_forecast"
            ],
            shortage
        )
    )


    if reorder is None:

        st.success(
            "No immediate reorder required."
        )

    else:

        r1, r2 = st.columns(2)


        with r1:

            st.metric(
                "Suggested Order Date",
                reorder[
                    "order_date"
                ].strftime(
                    "%d %b %Y"
                )
            )


        with r2:

            st.metric(
                "Suggested Quantity",
                f'{reorder["order_quantity"]:,} units'
            )


# ============================================================
# PAGE 6 - SCENARIO PLANNER
# ============================================================

elif page == "Scenario Planner":

    st.title(
        "What-If Scenario Planner"
    )

    st.write(
        "Test how demand increases or shipment delays "
        "could change inventory risk and purchasing decisions."
    )


    selected_sku = st.selectbox(
        "Choose SKU",
        products[
            "sku"
        ],
        key="scenario_sku"
    )


    product = (
        products[
            products[
                "sku"
            ] == selected_sku
        ]
        .iloc[0]
    )


    c1, c2 = st.columns(2)


    with c1:

        demand_increase = st.selectbox(
            "Demand Increase",
            [
                0,
                10,
                20,
                30
            ],
            format_func=lambda x: f"{x}%"
        )


    with c2:

        shipment_delay = st.selectbox(
            "Shipment Delay",
            [
                0,
                15,
                30,
                45
            ],
            format_func=lambda x: f"{x} days"
        )


    base_result = (
        calculate_sku_projection(
            selected_sku
        )
    )


    scenario_result = (
        calculate_sku_projection(
            selected_sku,
            demand_increase_pct=
                demand_increase,
            shipment_delay_days=
                shipment_delay
        )
    )


    base_shortage = (
        base_result[
            "shortage_month"
        ]
    )


    scenario_shortage = (
        scenario_result[
            "shortage_month"
        ]
    )


    base_reorder = (
        calculate_reorder(
            product,
            base_result[
                "base_forecast"
            ],
            base_shortage
        )
    )


    scenario_reorder = (
        calculate_reorder(
            product,
            scenario_result[
                "adjusted_forecast"
            ],
            scenario_shortage
        )
    )


    st.subheader(
        "Base vs Scenario"
    )


    b1, b2, b3, b4 = st.columns(4)


    with b1:

        st.metric(
            "Base Demand",
            f'{base_result["base_forecast"]:.0f}/month'
        )


    with b2:

        st.metric(
            "Scenario Demand",
            f'{scenario_result["adjusted_forecast"]:.0f}/month'
        )


    with b3:

        if base_shortage is None:

            st.metric(
                "Base Shortage",
                "None"
            )

        else:

            st.metric(
                "Base Shortage",
                base_shortage.strftime(
                    "%b %Y"
                )
            )


    with b4:

        if scenario_shortage is None:

            st.metric(
                "Scenario Shortage",
                "None"
            )

        else:

            st.metric(
                "Scenario Shortage",
                scenario_shortage.strftime(
                    "%b %Y"
                )
            )


    base_projection = (
        base_result[
            "projection"
        ]
    )


    scenario_projection = (
        scenario_result[
            "projection"
        ]
    )


    comparison = pd.DataFrame(
        {
            "Month":
                base_projection[
                    "Month"
                ],

            "Base":
                base_projection[
                    "Closing Inventory"
                ],

            "Scenario":
                scenario_projection[
                    "Closing Inventory"
                ]
        }
    )


    comparison_long = (
        comparison.melt(
            id_vars="Month",
            var_name="Projection",
            value_name="Closing Inventory"
        )
    )


    comparison_chart = px.line(
        comparison_long,
        x="Month",
        y="Closing Inventory",
        color="Projection",
        markers=True,
        title="Base vs Scenario Inventory Projection"
    )


    st.plotly_chart(
        comparison_chart,
        width="stretch"
    )


    st.subheader(
        "Scenario Reorder Recommendation"
    )


    if scenario_reorder is None:

        st.success(
            "No reorder is required "
            "within the 12-month scenario window."
        )

    else:

        s1, s2 = st.columns(2)


        with s1:

            st.metric(
                "Suggested Order Date",
                scenario_reorder[
                    "order_date"
                ].strftime(
                    "%d %b %Y"
                )
            )


        with s2:

            st.metric(
                "Suggested Quantity",
                f'{scenario_reorder["order_quantity"]:,} units'
            )


    if (
        demand_increase == 0
        and shipment_delay == 0
    ):

        st.info(
            "This is the baseline scenario. "
            "Change the controls to test a different condition."
        )

    elif scenario_shortage is None:

        st.success(
            "No shortage is projected under "
            "the selected scenario."
        )

    elif base_shortage is None:

        st.warning(
            "The baseline had no shortage, "
            "but the selected scenario creates one."
        )

    elif scenario_shortage < base_shortage:

        st.warning(
            "The selected scenario causes "
            "the shortage to occur earlier."
        )

    elif scenario_shortage == base_shortage:

        st.info(
            "The shortage month remains the same, "
            "but projected inventory levels have changed."
        )

    else:

        st.info(
            "The selected scenario does not "
            "move the shortage earlier."
        )