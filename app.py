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
latest_inventory_date = inventory["as_of_date"].max()

current_year = latest_sales_month.year
current_month_number = latest_sales_month.month
previous_year = current_year - 1


# ============================================================
# HELPER FUNCTION - SKU PROJECTION
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
            1 +
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

    rows = []

    for month in future_months:

        month_end = (
            month +
            pd.offsets.MonthEnd(1)
        )

        incoming = selected_pos.loc[
            (
                selected_pos[
                    "scenario_arrival_date"
                ] >= month
            )
            &
            (
                selected_pos[
                    "scenario_arrival_date"
                ] <= month_end
            ),
            "quantity"
        ].sum()

        closing = (
            opening_inventory
            +
            int(incoming)
            -
            forecast_demand
        )

        rows.append(
            {
                "Month Date": month,
                "Month": month.strftime(
                    "%b %Y"
                ),
                "Opening Inventory":
                    opening_inventory,
                "Incoming":
                    int(incoming),
                "Forecast Demand":
                    forecast_demand,
                "Closing Inventory":
                    closing
            }
        )

        opening_inventory = closing

    projection = pd.DataFrame(
        rows
    )

    shortage_rows = projection[
        projection[
            "Closing Inventory"
        ] < 0
    ]

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
            projection,

        "shortage_month":
            shortage_month,

        "current_inventory":
            total_inventory,

        "incoming_quantity":
            int(
                selected_pos[
                    "quantity"
                ].sum()
            )
    }


# ============================================================
# REORDER FUNCTION
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

    order_date = (
        shortage_month
        -
        pd.Timedelta(
            days=lead_time_days
        )
    )

    pack_size = max(
        int(
            product[
                "pack_size"
            ]
        ),
        1
    )

    order_quantity = (
        math.ceil(
            (
                forecast_value * 3
            )
            /
            pack_size
        )
        *
        pack_size
    )

    return {
        "order_date":
            order_date,

        "order_quantity":
            order_quantity
    }


# ============================================================
# SALES CALCULATIONS
# ============================================================

current_ytd_sales = sales[
    (
        sales[
            "month"
        ].dt.year
        ==
        current_year
    )
    &
    (
        sales[
            "month"
        ].dt.month
        <=
        current_month_number
    )
].copy()


previous_ytd_sales = sales[
    (
        sales[
            "month"
        ].dt.year
        ==
        previous_year
    )
    &
    (
        sales[
            "month"
        ].dt.month
        <=
        current_month_number
    )
].copy()


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


# ============================================================
# FINANCIAL CALCULATIONS
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


estimated_gross_profit = (
    current_ytd_revenue
    -
    financial_sales[
        "estimated_cogs"
    ].sum()
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


# ============================================================
# PURCHASE ORDERS
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
    ]
    .copy()
)


total_open_po_value = (
    open_purchase_orders[
        "total_cost"
    ].sum()
)


delayed_po_count = len(
    open_purchase_orders[
        open_purchase_orders[
            "status"
        ]
        ==
        "delayed"
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


top_by_revenue = (
    sku_sales_ytd
    .sort_values(
        "revenue",
        ascending=False
    )
)


# ============================================================
# INVENTORY RISK
# ============================================================

risk_rows = []


for sku in products["sku"]:

    result = (
        calculate_sku_projection(
            sku
        )
    )

    if (
        result is None
        or
        result[
            "shortage_month"
        ] is None
    ):

        continue

    product_row = products[
        products[
            "sku"
        ] == sku
    ].iloc[0]


    reorder = calculate_reorder(
        product_row,
        result[
            "base_forecast"
        ],
        result[
            "shortage_month"
        ]
    )


    days_to_shortage = (
        result[
            "shortage_month"
        ]
        -
        pd.Timestamp(
            latest_inventory_date
        )
    ).days


    lead_time = int(
        product_row[
            "lead_time_days"
        ]
    )


    if (
        days_to_shortage
        <=
        lead_time
    ):

        urgency = (
            "Immediate Action"
        )

    elif (
        days_to_shortage
        <=
        lead_time + 30
    ):

        urgency = (
            "Review Soon"
        )

    else:

        urgency = (
            "Monitor"
        )


    risk_rows.append(
        {
            "SKU":
                sku,

            "Urgency":
                urgency,

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

            "Days to Shortage":
                days_to_shortage,

            "Projected Shortage":
                result[
                    "shortage_month"
                ].strftime(
                    "%b %Y"
                ),

            "Lead Time (Days)":
                lead_time,

            "Suggested Order Date":
                reorder[
                    "order_date"
                ].strftime(
                    "%d %b %Y"
                )
                if reorder
                else "N/A"
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
            ==
            supplier
        ]
        .copy()
    )


    received = (
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


    delayed_count = len(
        open_orders[
            open_orders[
                "status"
            ]
            ==
            "delayed"
        ]
    )


    valid = received[
        received[
            "actual_arrival_date"
        ].notna()
        &
        received[
            "expected_arrival_date"
        ].notna()
    ].copy()


    if not valid.empty:

        on_time_rate = (
            (
                valid[
                    "actual_arrival_date"
                ]
                <=
                valid[
                    "expected_arrival_date"
                ]
            ).sum()
            /
            len(valid)
        ) * 100


        avg_lead = (
            valid[
                "actual_arrival_date"
            ]
            -
            valid[
                "order_date"
            ]
        ).dt.days.mean()

    else:

        on_time_rate = 0
        avg_lead = 0


    if (
        on_time_rate < 70
        or
        delayed_count >= 5
    ):

        risk = (
            "High Risk"
        )

    elif (
        on_time_rate < 85
        or
        delayed_count >= 2
    ):

        risk = (
            "Medium Risk"
        )

    else:

        risk = (
            "Low Risk"
        )


    supplier_rows.append(
        {
            "Supplier":
                supplier,

            "Total Orders":
                len(
                    supplier_orders
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
                    avg_lead,
                    1
                )
                if pd.notna(
                    avg_lead
                )
                else 0,

            "Open PO Value":
                round(
                    open_orders[
                        "total_cost"
                    ].sum(),
                    2
                ),

            "Supplier Risk":
                risk
        }
    )


supplier_performance = (
    pd.DataFrame(
        supplier_rows
    )
)


# ============================================================
# FORECAST EVALUATION DATA
# ============================================================

forecast_rows = []


for sku in products["sku"]:

    sku_sales = (
        sales[
            sales[
                "sku"
            ]
            ==
            sku
        ]
        .groupby(
            "month",
            as_index=False
        )[
            "units_sold"
        ]
        .sum()
        .sort_values(
            "month"
        )
    )


    if len(
        sku_sales
    ) < 4:

        continue


    sku_sales[
        "Forecast"
    ] = (
        sku_sales[
            "units_sold"
        ]
        .shift(1)
        .rolling(3)
        .mean()
    )


    eval_rows = (
        sku_sales[
            sku_sales[
                "Forecast"
            ].notna()
        ]
        .copy()
    )


    eval_rows[
        "Absolute Error"
    ] = (
        eval_rows[
            "units_sold"
        ]
        -
        eval_rows[
            "Forecast"
        ]
    ).abs()


    eval_rows[
        "APE"
    ] = (
        eval_rows[
            "Absolute Error"
        ]
        /
        eval_rows[
            "units_sold"
        ].replace(
            0,
            pd.NA
        )
    ) * 100


    for _, row in (
        eval_rows
        .tail(6)
        .iterrows()
    ):

        forecast_rows.append(
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
        forecast_rows
    )
)


if not forecast_evaluation_df.empty:

    overall_mae = (
        forecast_evaluation_df[
            "Absolute Error"
        ].mean()
    )


    overall_mape = (
        pd.to_numeric(
            forecast_evaluation_df[
                "APE"
            ],
            errors="coerce"
        )
        .dropna()
        .mean()
    )

else:

    overall_mae = 0
    overall_mape = 0


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.title(
    "Navigation"
)


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


st.sidebar.markdown(
    "---"
)


st.sidebar.write(
    "CSIS 4495 Applied Research Project"
)


st.sidebar.caption(
    "Inventory & Procurement Decision-Support System"
)


if pd.notna(
    latest_sales_month
):

    st.sidebar.caption(
        "Sales data through: "
        f"{latest_sales_month.strftime('%b %Y')}"
    )


if pd.notna(
    latest_inventory_date
):

    st.sidebar.caption(
        "Inventory snapshot: "
        f"{latest_inventory_date.strftime('%d %b %Y')}"
    )


# ============================================================
# PAGE 1 - OVERVIEW
# ============================================================

if page == "Overview":

    st.title(
        "Executive Business Overview"
    )


    st.info(
        "Academic project note: this application "
        "uses synthetic data for testing."
    )


    c1, c2, c3, c4 = (
        st.columns(4)
    )


    with c1:

        st.metric(
            "Revenue YTD",
            f"${current_ytd_revenue:,.0f}",
            f"{yoy_revenue_change:+.1f}% vs last year"
        )


    with c2:

        st.metric(
            "Estimated Gross Profit",
            f"${estimated_gross_profit:,.0f}"
        )


    with c3:

        st.metric(
            "Inventory Value",
            f"${total_inventory_value:,.0f}"
        )


    with c4:

        st.metric(
            "Products Needing Attention",
            len(
                risk_df
            )
        )


    st.subheader(
        "Revenue Trend"
    )


    trend = sales[
        sales[
            "month"
        ].dt.year.isin(
            [
                previous_year,
                current_year
            ]
        )
    ].copy()


    trend[
        "Year"
    ] = (
        trend[
            "month"
        ].dt.year.astype(
            str
        )
    )


    trend[
        "Month"
    ] = (
        trend[
            "month"
        ].dt.strftime(
            "%b"
        )
    )


    trend = (
        trend
        .groupby(
            [
                "Year",
                "Month"
            ],
            as_index=False
        )[
            "revenue"
        ]
        .sum()
    )


    chart = px.line(
        trend,
        x="Month",
        y="revenue",
        color="Year",
        markers=True,
        title="Monthly Revenue"
    )


    st.plotly_chart(
        chart,
        use_container_width=True
    )


    st.subheader(
        "Products Needing Attention"
    )


    if risk_df.empty:

        st.success(
            "No projected shortages "
            "in the next 12 months."
        )

    else:

        st.dataframe(
            risk_df.head(10),
            use_container_width=True,
            hide_index=True
        )


# ============================================================
# PAGE 2 - SALES
# ============================================================

elif page == "Sales & Financials":

    st.title(
        "Sales & Financial Performance"
    )


    c1, c2, c3 = (
        st.columns(3)
    )


    with c1:

        st.metric(
            "Revenue YTD",
            f"${current_ytd_revenue:,.0f}"
        )


    with c2:

        st.metric(
            "Estimated Gross Profit",
            f"${estimated_gross_profit:,.0f}"
        )


    with c3:

        st.metric(
            "Estimated Gross Margin",
            f"{gross_margin:.1f}%"
        )


    st.info(
        "Gross profit is an estimate based "
        "on revenue minus product unit cost. "
        "Operating expenses are not included."
    )


    st.subheader(
        "Top Products by Revenue"
    )


    chart = px.bar(
        top_by_revenue.head(10),
        x="sku",
        y="revenue",
        title="Top 10 Products by Revenue"
    )


    st.plotly_chart(
        chart,
        use_container_width=True
    )


# ============================================================
# PAGE 3 - INVENTORY
# ============================================================

elif page == "Inventory & Procurement":

    st.title(
        "Inventory & Procurement"
    )


    c1, c2, c3 = (
        st.columns(3)
    )


    with c1:

        st.metric(
            "Inventory Value",
            f"${total_inventory_value:,.0f}"
        )


    with c2:

        st.metric(
            "Open PO Value",
            f"${total_open_po_value:,.0f}"
        )


    with c3:

        st.metric(
            "Delayed Purchase Orders",
            delayed_po_count
        )


    st.subheader(
        "Open Purchase Orders"
    )


    st.dataframe(
        open_purchase_orders,
        use_container_width=True,
        hide_index=True
    )


    st.subheader(
        "Products Needing Attention"
    )


    if risk_df.empty:

        st.success(
            "No projected shortages."
        )

    else:

        st.dataframe(
            risk_df,
            use_container_width=True,
            hide_index=True
        )


# ============================================================
# PAGE 4 - SUPPLIER PERFORMANCE
# ============================================================

elif page == "Supplier Performance":

    st.title(
        "Supplier Performance"
    )


    st.dataframe(
        supplier_performance,
        use_container_width=True,
        hide_index=True
    )


    if not supplier_performance.empty:

        summary = (
            supplier_performance[
                "Supplier Risk"
            ]
            .value_counts()
            .reset_index()
        )


        summary.columns = [
            "Risk",
            "Suppliers"
        ]


        chart = px.bar(
            summary,
            x="Risk",
            y="Suppliers",
            title="Supplier Risk Summary"
        )


        st.plotly_chart(
            chart,
            use_container_width=True
        )


# ============================================================
# PAGE 5 - FORECAST EVALUATION
# ============================================================

elif page == "Forecast Evaluation":

    st.title(
        "Forecast Evaluation"
    )


    st.write(
        "This page reviews how the three-month "
        "moving-average forecast compares with "
        "historical sales."
    )


    st.caption(
        "The evaluation uses the most recent six "
        "available forecast periods for each SKU."
    )


    if forecast_evaluation_df.empty:

        st.info(
            "There is not enough historical data "
            "to evaluate the forecast."
        )

    else:

        if pd.isna(
            overall_mape
        ):

            overall_status = (
                "Not Available"
            )

        elif overall_mape < 10:

            overall_status = (
                "Very Good"
            )

        elif overall_mape < 20:

            overall_status = (
                "Good"
            )

        elif overall_mape < 30:

            overall_status = (
                "Moderate"
            )

        else:

            overall_status = (
                "Needs Review"
            )


        c1, c2, c3 = (
            st.columns(3)
        )


        with c1:

            st.metric(
                "Overall MAE",
                f"{overall_mae:.1f} units"
            )


        with c2:

            if pd.isna(
                overall_mape
            ):

                st.metric(
                    "Overall MAPE",
                    "N/A"
                )

            else:

                st.metric(
                    "Overall MAPE",
                    f"{overall_mape:.1f}%"
                )


        with c3:

            st.metric(
                "Forecast Status",
                overall_status
            )


        st.info(
            "MAE shows the average difference "
            "between forecast and actual demand. "
            "MAPE shows the average percentage error."
        )


        selected_eval_sku = (
            st.selectbox(
                "Choose Product SKU",
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
            pd.to_numeric(
                sku_eval[
                    "APE"
                ],
                errors="coerce"
            )
            .dropna()
            .mean()
        )


        if pd.isna(
            sku_mape
        ):

            sku_status = (
                "Not Available"
            )

        elif sku_mape < 10:

            sku_status = (
                "Very Good"
            )

        elif sku_mape < 20:

            sku_status = (
                "Good"
            )

        elif sku_mape < 30:

            sku_status = (
                "Moderate"
            )

        else:

            sku_status = (
                "Needs Review"
            )


        c1, c2, c3 = (
            st.columns(3)
        )


        with c1:

            st.metric(
                "SKU MAE",
                f"{sku_mae:.1f} units"
            )


        with c2:

            if pd.isna(
                sku_mape
            ):

                st.metric(
                    "SKU MAPE",
                    "N/A"
                )

            else:

                st.metric(
                    "SKU MAPE",
                    f"{sku_mape:.1f}%"
                )


        with c3:

            st.metric(
                "Accuracy Status",
                sku_status
            )


        comparison = (
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


        chart = px.line(
            comparison,
            x="Month Label",
            y="Units",
            color="Type",
            markers=True,
            title=(
                "Actual vs Forecast - "
                f"{selected_eval_sku}"
            )
        )


        st.plotly_chart(
            chart,
            use_container_width=True
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
            pd.to_numeric(
                display_eval[
                    "APE"
                ],
                errors="coerce"
            )
            .round(1)
        )


        display_eval = (
            display_eval
            .rename(
                columns={
                    "Month Label":
                        "Month",

                    "APE":
                        "Percentage Error (%)"
                }
            )
        )


        st.dataframe(
            display_eval,
            use_container_width=True,
            hide_index=True
        )


        st.download_button(
            "Download Forecast Evaluation",
            data=display_eval.to_csv(
                index=False
            ),
            file_name=(
                f"{selected_eval_sku}"
                "_forecast_evaluation.csv"
            ),
            mime="text/csv"
        )


        st.subheader(
            "Evaluation Notes"
        )


        st.write(
            "The three-month moving average "
            "is the baseline forecasting method "
            "for this project."
        )


        st.write(
            "The results show that forecast "
            "accuracy can vary between products. "
            "Another forecasting method may be "
            "compared with this baseline later."
        )


# ============================================================
# PAGE 6 - SKU ANALYSIS
# ============================================================

elif page == "SKU Analysis":

    st.title(
        "Product / SKU Analysis"
    )


    selected_sku = (
        st.selectbox(
            "Choose Product SKU",
            sorted(
                products[
                    "sku"
                ].unique()
            )
        )
    )


    product = products[
        products[
            "sku"
        ]
        ==
        selected_sku
    ].iloc[0]


    result = (
        calculate_sku_projection(
            selected_sku
        )
    )


    c1, c2, c3, c4 = (
        st.columns(4)
    )


    with c1:

        st.metric(
            "Category",
            product[
                "category"
            ]
        )


    with c2:

        st.metric(
            "Supplier",
            product[
                "supplier_id"
            ]
        )


    with c3:

        st.metric(
            "Lead Time",
            f"{int(product['lead_time_days'])} days"
        )


    with c4:

        st.metric(
            "Pack Size",
            int(
                product[
                    "pack_size"
                ]
            )
        )


    if result is None:

        st.warning(
            "Projection could not be "
            "calculated for this SKU."
        )

    else:

        st.metric(
            "Current Inventory",
            f"{result['current_inventory']:,} units"
        )


        st.metric(
            "3-Month Moving Average",
            f"{result['base_forecast']:.0f} units/month"
        )


        st.dataframe(
            result[
                "projection"
            ],
            use_container_width=True,
            hide_index=True
        )


        chart = px.line(
            result[
                "projection"
            ],
            x="Month",
            y="Closing Inventory",
            markers=True,
            title="Projected Inventory"
        )


        st.plotly_chart(
            chart,
            use_container_width=True
        )


        reorder = (
            calculate_reorder(
                product,
                result[
                    "base_forecast"
                ],
                result[
                    "shortage_month"
                ]
            )
        )


        if reorder:

            st.warning(
                "Projected shortage: "
                f"{result['shortage_month'].strftime('%b %Y')}"
            )


            st.write(
                "Suggested order date: "
                f"{reorder['order_date'].strftime('%d %b %Y')}"
            )


            st.write(
                "Suggested order quantity: "
                f"{reorder['order_quantity']:,} units"
            )

        else:

            st.success(
                "No immediate reorder "
                "is recommended."
            )


# ============================================================
# PAGE 7 - SCENARIO PLANNER
# ============================================================

elif page == "Scenario Planner":

    st.title(
        "What-If Scenario Planner"
    )


    selected_sku = (
        st.selectbox(
            "Choose Product SKU",
            sorted(
                products[
                    "sku"
                ].unique()
            ),
            key="scenario_sku"
        )
    )


    product = products[
        products[
            "sku"
        ]
        ==
        selected_sku
    ].iloc[0]


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


    base = (
        calculate_sku_projection(
            selected_sku
        )
    )


    scenario = (
        calculate_sku_projection(
            selected_sku,
            demand_increase,
            shipment_delay
        )
    )


    if (
        base is None
        or
        scenario is None
    ):

        st.warning(
            "Scenario results could not "
            "be calculated for this SKU."
        )

    else:

        base_reorder = (
            calculate_reorder(
                product,
                base[
                    "base_forecast"
                ],
                base[
                    "shortage_month"
                ]
            )
        )


        scenario_reorder = (
            calculate_reorder(
                product,
                scenario[
                    "adjusted_forecast"
                ],
                scenario[
                    "shortage_month"
                ]
            )
        )


        comparison = (
            pd.DataFrame(
                {
                    "Month":
                        base[
                            "projection"
                        ][
                            "Month"
                        ],

                    "Normal Projection":
                        base[
                            "projection"
                        ][
                            "Closing Inventory"
                        ],

                    "Scenario Projection":
                        scenario[
                            "projection"
                        ][
                            "Closing Inventory"
                        ]
                }
            )
        )


        comparison_long = (
            comparison
            .melt(
                id_vars="Month",
                var_name="Projection",
                value_name="Closing Inventory"
            )
        )


        chart = px.line(
            comparison_long,
            x="Month",
            y="Closing Inventory",
            color="Projection",
            markers=True,
            title=(
                "Normal vs Scenario "
                "Inventory Projection"
            )
        )


        st.plotly_chart(
            chart,
            use_container_width=True
        )


        summary = pd.DataFrame(
            {
                "Measure":
                [
                    "Monthly Demand",
                    "Projected Shortage",
                    "Suggested Order Date",
                    "Suggested Order Quantity"
                ],

                "Normal Plan":
                [
                    f"{base['base_forecast']:.0f} units",

                    (
                        base[
                            "shortage_month"
                        ].strftime(
                            "%b %Y"
                        )
                        if base[
                            "shortage_month"
                        ] is not None
                        else "No shortage"
                    ),

                    (
                        base_reorder[
                            "order_date"
                        ].strftime(
                            "%d %b %Y"
                        )
                        if base_reorder
                        else "Not required"
                    ),

                    (
                        f"{base_reorder['order_quantity']:,} units"
                        if base_reorder
                        else "0 units"
                    )
                ],

                "Scenario":
                [
                    f"{scenario['adjusted_forecast']:.0f} units",

                    (
                        scenario[
                            "shortage_month"
                        ].strftime(
                            "%b %Y"
                        )
                        if scenario[
                            "shortage_month"
                        ] is not None
                        else "No shortage"
                    ),

                    (
                        scenario_reorder[
                            "order_date"
                        ].strftime(
                            "%d %b %Y"
                        )
                        if scenario_reorder
                        else "Not required"
                    ),

                    (
                        f"{scenario_reorder['order_quantity']:,} units"
                        if scenario_reorder
                        else "0 units"
                    )
                ]
            }
        )


        st.dataframe(
            summary,
            use_container_width=True,
            hide_index=True
        )