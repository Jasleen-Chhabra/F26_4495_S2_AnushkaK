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
# REPORTING PERIOD
# ============================================================

latest_sales_month = sales["month"].max()

current_year = latest_sales_month.year
current_month_number = latest_sales_month.month
previous_year = current_year - 1

data_through = latest_sales_month.strftime("%b %Y")

latest_inventory_date = (
    inventory["as_of_date"].max()
)


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.title("Navigation")

page = st.sidebar.radio(
    "Go to",
    [
        "Overview",
        "Sales & Financials",
        "Inventory & Procurement",
        "Supplier Performance",
        "Forecast Evaluation",
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

st.sidebar.caption(
    f"Sales data through {data_through}"
)

if pd.notna(latest_inventory_date):

    st.sidebar.caption(
        "Inventory snapshot: "
        f"{latest_inventory_date.strftime('%d %b %Y')}"
    )


with st.sidebar.expander("Tech Stack"):

    st.write("Python")
    st.write("Streamlit")
    st.write("pandas")
    st.write("Plotly")
    st.write("CSV")
    st.write("SQLite dataset available")
    st.write("GitHub")


# ============================================================
# HELPER FUNCTION
# FILTER DATA
# ============================================================

def filter_data_by_management_filters(
    selected_category,
    selected_supplier,
    selected_warehouse
):

    filtered_products = products.copy()
    filtered_inventory = inventory.copy()
    filtered_sales = sales.copy()
    filtered_pos = purchase_orders.copy()


    if selected_category != "All":

        allowed_skus = (
            products[
                products["category"]
                == selected_category
            ]["sku"]
        )

        filtered_products = (
            filtered_products[
                filtered_products["sku"]
                .isin(allowed_skus)
            ]
        )

        filtered_inventory = (
            filtered_inventory[
                filtered_inventory["sku"]
                .isin(allowed_skus)
            ]
        )

        filtered_sales = (
            filtered_sales[
                filtered_sales["sku"]
                .isin(allowed_skus)
            ]
        )

        filtered_pos = (
            filtered_pos[
                filtered_pos["sku"]
                .isin(allowed_skus)
            ]
        )


    if selected_supplier != "All":

        allowed_skus = (
            products[
                products["supplier_id"]
                == selected_supplier
            ]["sku"]
        )

        filtered_products = (
            filtered_products[
                filtered_products["sku"]
                .isin(allowed_skus)
            ]
        )

        filtered_inventory = (
            filtered_inventory[
                filtered_inventory["sku"]
                .isin(allowed_skus)
            ]
        )

        filtered_sales = (
            filtered_sales[
                filtered_sales["sku"]
                .isin(allowed_skus)
            ]
        )

        filtered_pos = (
            filtered_pos[
                filtered_pos["supplier_id"]
                == selected_supplier
            ]
        )


    if selected_warehouse != "All":

        filtered_inventory = (
            filtered_inventory[
                filtered_inventory["warehouse"]
                == selected_warehouse
            ]
        )

        filtered_sales = (
            filtered_sales[
                filtered_sales["warehouse"]
                == selected_warehouse
            ]
        )

        filtered_pos = (
            filtered_pos[
                filtered_pos["warehouse"]
                == selected_warehouse
            ]
        )


    return (
        filtered_products,
        filtered_inventory,
        filtered_sales,
        filtered_pos
    )


# ============================================================
# HELPER FUNCTION
# SKU PROJECTION
# ============================================================

def calculate_sku_projection(
    selected_sku,
    demand_increase_pct=0,
    shipment_delay_days=0
):

    selected_sales = sales[
        sales["sku"]
        == selected_sku
    ].copy()

    selected_inventory = inventory[
        inventory["sku"]
        == selected_sku
    ].copy()

    selected_pos = purchase_orders[
        (
            purchase_orders["sku"]
            == selected_sku
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


    if (
        selected_sales.empty
        or
        selected_inventory.empty
    ):

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
        round(
            adjusted_forecast
        )
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


    opening_inventory = (
        total_inventory
    )


    projection_rows = []


    for month in future_months:

        month_start = month

        month_end = (
            month
            +
            pd.offsets.MonthEnd(1)
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
            ]["quantity"]
            .sum()
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
                "Month Date":
                    month,

                "Month":
                    month.strftime(
                        "%b %Y"
                    ),

                "Opening Inventory":
                    opening_inventory,

                "Incoming":
                    int(
                        incoming_this_month
                    ),

                "Forecast Demand":
                    forecast_demand,

                "Closing Inventory":
                    closing_inventory
            }
        )


        opening_inventory = (
            closing_inventory
        )


    projection_df = pd.DataFrame(
        projection_rows
    )


    shortage_rows = (
        projection_df[
            projection_df[
                "Closing Inventory"
            ] < 0
        ]
    )


    if shortage_rows.empty:

        shortage_month = None

    else:

        shortage_month = (
            shortage_rows
            .iloc[0][
                "Month Date"
            ]
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
# REORDER
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
        *
        3
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
# CURRENT / PREVIOUS SALES
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
    ==
    previous_year
].copy()


# ============================================================
# GENERAL KPI CALCULATIONS
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
# GROSS PROFIT
# ============================================================

financial_sales = (
    current_ytd_sales
    .merge(
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
    inventory
    .merge(
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
        .iloc[0][
            "units_sold"
        ]
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
# RISK / DAYS TO SHORTAGE
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


    if shortage_month is None:
        continue


    product_row = (
        products[
            products["sku"]
            == sku
        ]
        .iloc[0]
    )


    reorder = calculate_reorder(
        product_row,
        result[
            "base_forecast"
        ],
        shortage_month
    )


    days_to_shortage = (
        shortage_month
        -
        pd.Timestamp(
            latest_inventory_date
        )
    ).days


    risk_rows.append(
        {
            "SKU":
                sku,

            "Current Stock":
                result[
                    "current_inventory"
                ],

            "Forecast / Month":
                round(
                    result[
                        "base_forecast"
                    ]
                ),

            "Incoming":
                result[
                    "incoming_quantity"
                ],

            "Projected Shortage":
                shortage_month.strftime(
                    "%b %Y"
                ),

            "Days to Shortage":
                days_to_shortage,

            "Lead Time (Days)":
                int(
                    product_row[
                        "lead_time_days"
                    ]
                ),

            "Suggested Order Date":
                (
                    reorder[
                        "order_date"
                    ].strftime(
                        "%d %b %Y"
                    )
                    if reorder
                    else "N/A"
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
        risk_df
        .sort_values(
            [
                "Days to Shortage",
                "Lead Time (Days)"
            ]
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
            "SKU":
                sku,

            "Health":
                health,

            "Months Cover":
                round(
                    months_cover,
                    1
                )
        }
    )


inventory_health_df = (
    pd.DataFrame(
        inventory_health_rows
    )
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
# SUPPLIER PERFORMANCE
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
            ]
            == supplier
        ]
        .copy()
    )


    received_orders = (
        supplier_orders[
            supplier_orders[
                "status"
            ]
            ==
            "received"
        ]
        .copy()
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
        ]
        .copy()
    )


    delayed_open_orders = (
        open_orders[
            open_orders[
                "status"
            ]
            ==
            "delayed"
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


        valid_received = (
            received_orders[
                received_orders[
                    "actual_arrival_date"
                ].notna()
                &
                received_orders[
                    "expected_arrival_date"
                ].notna()
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


    delayed_count = len(
        delayed_open_orders
    )


    if (
        on_time_rate < 70
        or
        delayed_count >= 5
    ):

        risk_rating = "High Risk"

    elif (
        on_time_rate < 85
        or
        delayed_count >= 2
    ):

        risk_rating = "Medium Risk"

    else:

        risk_rating = "Low Risk"


    supplier_rows.append(
        {
            "Supplier":
                supplier,

            "Total Orders":
                len(
                    supplier_orders
                ),

            "Received Orders":
                len(
                    received_orders
                ),

            "Open Orders":
                len(
                    open_orders
                ),

            "Delayed Open Orders":
                delayed_count,

            "On-Time %":
                round(
                    on_time_rate,
                    1
                ),

            "Avg Actual Lead Time":
                round(
                    avg_actual_lead,
                    1
                ),

            "Open PO Value":
                round(
                    open_orders[
                        "total_cost"
                    ].sum(),
                    2
                ),

            "Supplier Risk":
                risk_rating
        }
    )


supplier_performance = (
    pd.DataFrame(
        supplier_rows
    )
)


# ============================================================
# FORECAST EVALUATION
# ============================================================

forecast_test_rows = []


for sku in products["sku"]:

    sku_sales = (
        sales[
            sales["sku"]
            == sku
        ]
        .groupby(
            "month",
            as_index=False
        )["units_sold"]
        .sum()
        .sort_values(
            "month"
        )
    )


    if len(sku_sales) < 4:
        continue


    sku_sales[
        "Forecast"
    ] = (
        sku_sales[
            "units_sold"
        ]
        .shift(1)
        .rolling(
            3
        )
        .mean()
    )


    evaluation_rows = (
        sku_sales[
            sku_sales[
                "Forecast"
            ].notna()
        ]
        .copy()
    )


    evaluation_rows[
        "Absolute Error"
    ] = (
        evaluation_rows[
            "units_sold"
        ]
        -
        evaluation_rows[
            "Forecast"
        ]
    ).abs()


    evaluation_rows[
        "APE"
    ] = (
        evaluation_rows[
            "Absolute Error"
        ]
        /
        evaluation_rows[
            "units_sold"
        ].replace(
            0,
            pd.NA
        )
    ) * 100


    for _, row in (
        evaluation_rows
        .tail(6)
        .iterrows()
    ):

        forecast_test_rows.append(
            {
                "SKU":
                    sku,

                "Month":
                    row[
                        "month"
                    ],

                "Actual":
                    row[
                        "units_sold"
                    ],

                "Forecast":
                    row[
                        "Forecast"
                    ],

                "Absolute Error":
                    row[
                        "Absolute Error"
                    ],

                "APE":
                    row[
                        "APE"
                    ]
            }
        )


forecast_evaluation_df = (
    pd.DataFrame(
        forecast_test_rows
    )
)


if not forecast_evaluation_df.empty:

    overall_mae = (
        forecast_evaluation_df[
            "Absolute Error"
        ].mean()
    )


    overall_mape = (
        forecast_evaluation_df[
            "APE"
        ]
        .dropna()
        .mean()
    )

else:

    overall_mae = 0
    overall_mape = 0


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
        f"Sales data through {data_through}"
    )


    # --------------------------------------------------------
    # FILTERS
    # --------------------------------------------------------

    st.subheader(
        "Management Filters"
    )


    filter1, filter2, filter3 = (
        st.columns(3)
    )


    with filter1:

        selected_category = (
            st.selectbox(
                "Category",
                [
                    "All"
                ]
                +
                sorted(
                    products[
                        "category"
                    ]
                    .dropna()
                    .unique()
                    .tolist()
                )
            )
        )


    with filter2:

        selected_supplier = (
            st.selectbox(
                "Supplier",
                [
                    "All"
                ]
                +
                sorted(
                    products[
                        "supplier_id"
                    ]
                    .dropna()
                    .unique()
                    .tolist()
                )
            )
        )


    with filter3:

        selected_warehouse = (
            st.selectbox(
                "Warehouse",
                [
                    "All"
                ]
                +
                sorted(
                    inventory[
                        "warehouse"
                    ]
                    .dropna()
                    .unique()
                    .tolist()
                )
            )
        )


    (
        filtered_products,
        filtered_inventory,
        filtered_sales,
        filtered_pos
    ) = filter_data_by_management_filters(
        selected_category,
        selected_supplier,
        selected_warehouse
    )


    filtered_current_sales = (
        filtered_sales[
            (
                filtered_sales[
                    "month"
                ].dt.year
                ==
                current_year
            )
            &
            (
                filtered_sales[
                    "month"
                ].dt.month
                <=
                current_month_number
            )
        ]
    )


    filtered_previous_sales = (
        filtered_sales[
            (
                filtered_sales[
                    "month"
                ].dt.year
                ==
                previous_year
            )
            &
            (
                filtered_sales[
                    "month"
                ].dt.month
                <=
                current_month_number
            )
        ]
    )


    filtered_revenue = (
        filtered_current_sales[
            "revenue"
        ].sum()
    )


    filtered_previous_revenue = (
        filtered_previous_sales[
            "revenue"
        ].sum()
    )


    if filtered_previous_revenue > 0:

        filtered_yoy_revenue = (
            (
                filtered_revenue
                -
                filtered_previous_revenue
            )
            /
            filtered_previous_revenue
        ) * 100

    else:

        filtered_yoy_revenue = 0


    filtered_inventory_cost = (
        filtered_inventory.merge(
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


    filtered_inventory_cost[
        "value"
    ] = (
        filtered_inventory_cost[
            "on_hand_qty"
        ]
        *
        filtered_inventory_cost[
            "unit_cost"
        ]
    )


    filtered_inventory_value = (
        filtered_inventory_cost[
            "value"
        ].sum()
    )


    filtered_open_pos = (
        filtered_pos[
            filtered_pos[
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


    filtered_open_po_value = (
        filtered_open_pos[
            "total_cost"
        ].sum()
    )


    filtered_delayed_po_count = len(
        filtered_open_pos[
            filtered_open_pos[
                "status"
            ]
            ==
            "delayed"
        ]
    )


    st.markdown("---")


    # --------------------------------------------------------
    # EXECUTIVE SUMMARY
    # --------------------------------------------------------

    st.subheader(
        "Executive Summary"
    )


    if filtered_yoy_revenue >= 0:

        revenue_message = (
            f"Revenue is {filtered_yoy_revenue:.1f}% "
            f"above the same period last year."
        )

    else:

        revenue_message = (
            f"Revenue is {abs(filtered_yoy_revenue):.1f}% "
            f"below the same period last year."
        )


    st.info(
        f"{revenue_message} "
        f"{risk_count} products are projected to experience "
        f"a shortage within the next 12 months. "
        f"{filtered_delayed_po_count} purchase orders are currently delayed."
    )


    # --------------------------------------------------------
    # KPI GROUPS
    # --------------------------------------------------------

    st.subheader(
        "Business Performance"
    )


    b1, b2, b3, b4 = (
        st.columns(4)
    )


    with b1:

        st.metric(
            "Revenue YTD",
            f"${filtered_revenue:,.0f}",
            f"{filtered_yoy_revenue:+.1f}%"
        )


    with b2:

        st.metric(
            "Estimated Gross Profit",
            f"${estimated_gross_profit:,.0f}"
        )


    with b3:

        st.metric(
            "Gross Margin",
            f"{gross_margin:.1f}%"
        )


    with b4:

        st.metric(
            "Top SKU by Revenue",
            top_revenue_sku
        )


    st.subheader(
        "Inventory Health"
    )


    i1, i2, i3, i4 = (
        st.columns(4)
    )


    with i1:

        st.metric(
            "Inventory Value",
            f"${filtered_inventory_value:,.0f}"
        )


    with i2:

        st.metric(
            "Products at Risk",
            risk_count
        )


    with i3:

        healthy_count = (
            inventory_health_df[
                inventory_health_df[
                    "Health"
                ]
                ==
                "Healthy"
            ]
            .shape[0]
        )


        st.metric(
            "Healthy Products",
            healthy_count
        )


    with i4:

        excess_count = (
            inventory_health_df[
                inventory_health_df[
                    "Health"
                ]
                ==
                "Excess"
            ]
            .shape[0]
        )


        st.metric(
            "Excess Inventory SKUs",
            excess_count
        )


    st.subheader(
        "Procurement Health"
    )


    p1, p2, p3, p4 = (
        st.columns(4)
    )


    with p1:

        st.metric(
            "Open PO Value",
            f"${filtered_open_po_value:,.0f}"
        )


    with p2:

        st.metric(
            "Delayed POs",
            filtered_delayed_po_count
        )


    with p3:

        st.metric(
            "Open PO Units",
            f"{total_open_po_units:,}"
        )


    with p4:

        high_risk_suppliers = (
            supplier_performance[
                supplier_performance[
                    "Supplier Risk"
                ]
                ==
                "High Risk"
            ]
            .shape[0]
        )


        st.metric(
            "High-Risk Suppliers",
            high_risk_suppliers
        )


    st.markdown("---")


    # --------------------------------------------------------
    # REVENUE TREND
    # --------------------------------------------------------

    st.subheader(
        "Revenue Performance"
    )


    revenue_monthly = (
        filtered_sales[
            filtered_sales[
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
                filtered_sales[
                    "month"
                ].dt.year.rename(
                    "Year"
                ),

                filtered_sales[
                    "month"
                ].dt.month.rename(
                    "Month Number"
                )
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

    c1, c2 = (
        st.columns(2)
    )


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


        top_chart = px.bar(
            top_by_revenue.head(5),
            x="sku",
            y="revenue",
            title="Top 5 SKUs by Revenue"
        )


        st.plotly_chart(
            top_chart,
            width="stretch"
        )


    # --------------------------------------------------------
    # CRITICAL SKU ACTION LIST
    # --------------------------------------------------------

    st.subheader(
        "Critical SKU Action List"
    )


    if risk_df.empty:

        st.success(
            "No projected shortages."
        )

    else:

        critical_display = (
            risk_df[
                [
                    "SKU",
                    "Current Stock",
                    "Forecast / Month",
                    "Incoming",
                    "Days to Shortage",
                    "Projected Shortage",
                    "Lead Time (Days)",
                    "Suggested Order Date"
                ]
            ]
            .head(10)
        )


        st.dataframe(
            critical_display,
            width="stretch",
            hide_index=True
        )


        st.download_button(
            "Download Critical SKU Report",
            data=critical_display.to_csv(
                index=False
            ),
            file_name=(
                "critical_sku_report.csv"
            ),
            mime="text/csv"
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


    f1, f2, f3, f4 = (
        st.columns(4)
    )


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
        "Estimated gross profit is based on revenue minus product unit cost. "
        "Operating expenses are not included."
    )


    st.markdown("---")


    category_sales = (
        current_ytd_sales
        .merge(
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


    st.subheader(
        "Top Products"
    )


    c1, c2 = (
        st.columns(2)
    )


    with c1:

        chart = px.bar(
            top_by_revenue.head(10),
            x="sku",
            y="revenue",
            title="Top 10 SKUs by Revenue"
        )


        st.plotly_chart(
            chart,
            width="stretch"
        )


    with c2:

        chart = px.bar(
            top_by_units.head(10),
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


    i1, i2, i3, i4 = (
        st.columns(4)
    )


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
        "Purchase Order Status"
    )


    po_status_summary = (
        purchase_orders[
            "status"
        ]
        .value_counts()
        .reset_index()
    )


    po_status_summary.columns = [
        "Status",
        "Orders"
    ]


    po_status_chart = px.bar(
        po_status_summary,
        x="Status",
        y="Orders",
        title="Purchase Order Status Summary"
    )


    st.plotly_chart(
        po_status_chart,
        width="stretch"
    )


    st.subheader(
        "Products Requiring Attention"
    )


    if risk_df.empty:

        st.success(
            "No projected shortages."
        )

    else:

        risk_display = (
            risk_df[
                [
                    "SKU",
                    "Current Stock",
                    "Forecast / Month",
                    "Incoming",
                    "Days to Shortage",
                    "Projected Shortage",
                    "Lead Time (Days)",
                    "Suggested Order Date"
                ]
            ]
        )


        st.dataframe(
            risk_display,
            width="stretch",
            hide_index=True
        )


        st.download_button(
            "Download Risk Report",
            data=risk_display.to_csv(
                index=False
            ),
            file_name=(
                "inventory_risk_report.csv"
            ),
            mime="text/csv"
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


    st.download_button(
        "Download Open PO Report",
        data=upcoming_pos.to_csv(
            index=False
        ),
        file_name=(
            "open_purchase_orders.csv"
        ),
        mime="text/csv"
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


        most_delayed_supplier = (
            supplier_performance
            .sort_values(
                "Delayed Open Orders",
                ascending=False
            )
            .iloc[0]
        )


        shortest_lead_supplier = (
            supplier_performance[
                supplier_performance[
                    "Avg Actual Lead Time"
                ] > 0
            ]
            .sort_values(
                "Avg Actual Lead Time"
            )
        )


        s1, s2, s3, s4 = (
            st.columns(4)
        )


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
                most_delayed_supplier[
                    "Supplier"
                ]
            )

            st.caption(
                f"{int(most_delayed_supplier['Delayed Open Orders'])} delayed open POs"
            )


        with s4:

            if not shortest_lead_supplier.empty:

                fastest = (
                    shortest_lead_supplier
                    .iloc[0]
                )

                st.metric(
                    "Shortest Avg Lead Time",
                    fastest[
                        "Supplier"
                    ]
                )

                st.caption(
                    f"{fastest['Avg Actual Lead Time']:.0f} days"
                )


        st.markdown("---")


        st.subheader(
            "Supplier Risk"
        )


        supplier_risk_summary = (
            supplier_performance[
                "Supplier Risk"
            ]
            .value_counts()
            .reset_index()
        )


        supplier_risk_summary.columns = [
            "Risk",
            "Suppliers"
        ]


        risk_chart = px.bar(
            supplier_risk_summary,
            x="Risk",
            y="Suppliers",
            title="Supplier Risk Classification"
        )


        st.plotly_chart(
            risk_chart,
            width="stretch"
        )


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


        st.plotly_chart(
            reliability_chart,
            width="stretch"
        )


        st.subheader(
            "Average Actual Lead Time"
        )


        lead_chart = px.bar(
            supplier_performance[
                supplier_performance[
                    "Avg Actual Lead Time"
                ] > 0
            ]
            .sort_values(
                "Avg Actual Lead Time"
            ),
            x="Supplier",
            y="Avg Actual Lead Time",
            title="Average Actual Lead Time by Supplier"
        )


        st.plotly_chart(
            lead_chart,
            width="stretch"
        )


        st.subheader(
            "Supplier Scorecard"
        )


        st.dataframe(
            supplier_performance
            .sort_values(
                [
                    "Supplier Risk",
                    "On-Time %"
                ],
                ascending=[
                    True,
                    False
                ]
            ),
            width="stretch",
            hide_index=True
        )


        st.download_button(
            "Download Supplier Scorecard",
            data=(
                supplier_performance
                .to_csv(
                    index=False
                )
            ),
            file_name=(
                "supplier_scorecard.csv"
            ),
            mime="text/csv"
        )


        st.subheader(
            "Supplier Drill-Down"
        )


        selected_supplier = (
            st.selectbox(
                "Select Supplier",
                sorted(
                    supplier_performance[
                        "Supplier"
                    ]
                )
            )
        )


        selected_supplier_orders = (
            purchase_orders[
                purchase_orders[
                    "supplier_id"
                ]
                ==
                selected_supplier
            ]
        )


        st.dataframe(
            selected_supplier_orders[
                [
                    "po_id",
                    "sku",
                    "quantity",
                    "order_date",
                    "expected_arrival_date",
                    "actual_arrival_date",
                    "status",
                    "total_cost"
                ]
            ],
            width="stretch",
            hide_index=True
        )


# ============================================================
# PAGE 5 - FORECAST EVALUATION
# ============================================================

elif page == "Forecast Evaluation":

    st.title(
        "Forecast Evaluation"
    )

    st.write(
        "This page checks how the three-month moving-average "
        "baseline performs against historical actual sales."
    )


    if forecast_evaluation_df.empty:

        st.info(
            "Not enough data available for forecast evaluation."
        )

    else:

        e1, e2 = (
            st.columns(2)
        )


        with e1:

            st.metric(
                "Overall MAE",
                f"{overall_mae:.1f} units"
            )


        with e2:

            st.metric(
                "Overall MAPE",
                f"{overall_mape:.1f}%"
            )


        st.caption(
            "MAE shows the average absolute difference between "
            "forecast and actual sales. MAPE shows the average "
            "percentage error."
        )


        st.markdown("---")


        selected_eval_sku = (
            st.selectbox(
                "Choose SKU",
                sorted(
                    forecast_evaluation_df[
                        "SKU"
                    ].unique()
                )
            )
        )


        sku_eval = (
            forecast_evaluation_df[
                forecast_evaluation_df[
                    "SKU"
                ]
                ==
                selected_eval_sku
            ]
            .copy()
        )


        sku_eval[
            "Month Label"
        ] = (
            sku_eval[
                "Month"
            ].dt.strftime(
                "%b %Y"
            )
        )


        sku_mae = (
            sku_eval[
                "Absolute Error"
            ].mean()
        )


        sku_mape = (
            sku_eval[
                "APE"
            ].dropna().mean()
        )


        c1, c2 = (
            st.columns(2)
        )


        with c1:

            st.metric(
                "SKU MAE",
                f"{sku_mae:.1f} units"
            )


        with c2:

            st.metric(
                "SKU MAPE",
                f"{sku_mape:.1f}%"
            )


        comparison_df = (
            sku_eval[
                [
                    "Month Label",
                    "Actual",
                    "Forecast"
                ]
            ]
            .melt(
                id_vars="Month Label",
                var_name="Type",
                value_name="Units"
            )
        )


        forecast_chart = px.line(
            comparison_df,
            x="Month Label",
            y="Units",
            color="Type",
            markers=True,
            title=(
                f"Actual vs Forecast – "
                f"{selected_eval_sku}"
            )
        )


        st.plotly_chart(
            forecast_chart,
            width="stretch"
        )


        display_eval = (
            sku_eval[
                [
                    "Month Label",
                    "Actual",
                    "Forecast",
                    "Absolute Error",
                    "APE"
                ]
            ]
            .copy()
        )


        display_eval[
            "Forecast"
        ] = (
            display_eval[
                "Forecast"
            ].round(1)
        )


        display_eval[
            "Absolute Error"
        ] = (
            display_eval[
                "Absolute Error"
            ].round(1)
        )


        display_eval[
            "APE"
        ] = (
            display_eval[
                "APE"
            ].round(1)
        )


        st.dataframe(
            display_eval,
            width="stretch",
            hide_index=True
        )


# ============================================================
# PAGE 6 - SKU ANALYSIS
# ============================================================

elif page == "SKU Analysis":

    st.title(
        "SKU Analysis"
    )

    st.write(
        "Detailed product-level inventory planning, "
        "forecasting and reorder analysis."
    )


    selected_sku = (
        st.selectbox(
            "Choose SKU",
            sorted(
                products[
                    "sku"
                ].unique()
            )
        )
    )


    product = (
        products[
            products["sku"]
            ==
            selected_sku
        ]
        .iloc[0]
    )


    st.subheader(
        "Product Details"
    )


    p1, p2, p3, p4 = (
        st.columns(4)
    )


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


    p5, p6, p7 = (
        st.columns(3)
    )


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


    selected_inventory = (
        inventory[
            inventory["sku"]
            ==
            selected_sku
        ]
    )


    st.subheader(
        "Current Inventory"
    )


    st.metric(
        "Total On-Hand Inventory",
        f'{int(selected_inventory["on_hand_qty"].sum()):,} units'
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


    selected_pos = (
        purchase_orders[
            (
                purchase_orders["sku"]
                ==
                selected_sku
            )
            &
            (
                purchase_orders["status"]
                .isin(
                    [
                        "ordered",
                        "in_transit",
                        "delayed"
                    ]
                )
            )
        ]
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


    selected_sales = (
        sales[
            sales["sku"]
            ==
            selected_sku
        ]
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


    s1, s2 = (
        st.columns(2)
    )


    with s1:

        st.metric(
            "Average Monthly Sales",
            f'{monthly_sales["units_sold"].mean():.0f} units'
        )


    with s2:

        st.metric(
            "Historical Revenue",
            f'${monthly_sales["revenue"].sum():,.0f}'
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

        r1, r2 = (
            st.columns(2)
        )


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
# PAGE 7 - SCENARIO PLANNER
# ============================================================

elif page == "Scenario Planner":

    st.title(
        "What-If Scenario Planner"
    )

    st.write(
        "Test how demand increases or shipment delays "
        "could change inventory risk and purchasing decisions."
    )


    selected_sku = (
        st.selectbox(
            "Choose SKU",
            sorted(
                products[
                    "sku"
                ].unique()
            ),
            key="scenario_sku"
        )
    )


    product = (
        products[
            products["sku"]
            ==
            selected_sku
        ]
        .iloc[0]
    )


    c1, c2 = (
        st.columns(2)
    )


    with c1:

        demand_increase = (
            st.selectbox(
                "Demand Increase",
                [
                    0,
                    10,
                    20,
                    30
                ],
                format_func=
                    lambda x:
                    f"{x}%"
            )
        )


    with c2:

        shipment_delay = (
            st.selectbox(
                "Shipment Delay",
                [
                    0,
                    15,
                    30,
                    45
                ],
                format_func=
                    lambda x:
                    f"{x} days"
            )
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


    b1, b2, b3, b4 = (
        st.columns(4)
    )


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


    comparison = pd.DataFrame(
        {
            "Month":
                base_result[
                    "projection"
                ][
                    "Month"
                ],

            "Base":
                base_result[
                    "projection"
                ][
                    "Closing Inventory"
                ],

            "Scenario":
                scenario_result[
                    "projection"
                ][
                    "Closing Inventory"
                ]
        }
    )


    comparison_long = (
        comparison
        .melt(
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
            "No reorder is required within "
            "the 12-month scenario window."
        )

    else:

        s1, s2 = (
            st.columns(2)
        )


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
        and
        shipment_delay == 0
    ):

        st.info(
            "This is the baseline scenario. "
            "Change demand or shipment delay "
            "to test a different condition."
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
            "The selected scenario does not move "
            "the shortage earlier."
        )