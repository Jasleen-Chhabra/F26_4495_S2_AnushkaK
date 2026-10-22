import streamlit as st
import pandas as pd
import plotly.express as px
import math


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Inventory & Procurement Planning System",
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


# Convert date columns
sales["month"] = pd.to_datetime(
    sales["month"],
    errors="coerce"
)

inventory["as_of_date"] = pd.to_datetime(
    inventory["as_of_date"],
    errors="coerce"
)

purchase_orders["expected_arrival_date"] = pd.to_datetime(
    purchase_orders["expected_arrival_date"],
    errors="coerce"
)


# ============================================================
# SIDEBAR NAVIGATION
# ============================================================

st.sidebar.title("Navigation")

page = st.sidebar.radio(
    "Go to",
    [
        "Executive Dashboard",
        "SKU Analysis"
    ]
)

st.sidebar.markdown("---")

st.sidebar.write(
    "CSIS 4495 Applied Research Project"
)

st.sidebar.caption(
    "Inventory & Procurement Decision-Support System"
)


# ============================================================
# HELPER FUNCTION
# ============================================================

def calculate_sku_projection(selected_sku):

    selected_sales = sales[
        sales["sku"] == selected_sku
    ].copy()

    selected_inventory = inventory[
        inventory["sku"] == selected_sku
    ].copy()

    selected_pos = purchase_orders[
        (purchase_orders["sku"] == selected_sku)
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

    forecast_value = (
        monthly_sales
        .tail(3)["units_sold"]
        .mean()
    )

    forecast_demand = int(
        round(forecast_value)
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

        incoming_this_month = selected_pos[
            (
                selected_pos[
                    "expected_arrival_date"
                ] >= month_start
            )
            &
            (
                selected_pos[
                    "expected_arrival_date"
                ] <= month_end
            )
        ]["quantity"].sum()

        closing_inventory = (
            opening_inventory
            + int(incoming_this_month)
            - forecast_demand
        )

        projection_rows.append(
            {
                "sku": selected_sku,
                "Month Date": month,
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
        first_shortage_month = None
    else:
        first_shortage_month = (
            shortage_rows
            .iloc[0]["Month Date"]
        )

    return {
        "forecast": forecast_value,
        "projection": projection_df,
        "shortage_month": first_shortage_month
    }


# ============================================================
# PAGE 1 - EXECUTIVE DASHBOARD
# ============================================================

if page == "Executive Dashboard":

    latest_sales_month = sales[
        "month"
    ].max()

    current_year = latest_sales_month.year
    current_month_number = latest_sales_month.month
    previous_year = current_year - 1

    data_through = latest_sales_month.strftime(
        "%b %Y"
    )

    st.title(
        "Executive Inventory & Procurement Dashboard"
    )

    st.write(
        "High-level view of sales, inventory, "
        "purchase orders and stock risk."
    )

    st.caption(
        f"Data through {data_through}"
    )

    st.markdown("---")


    # --------------------------------------------------------
    # CURRENT YTD SALES
    # --------------------------------------------------------

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
                - previous_ytd_units
            )
            / previous_ytd_units
        ) * 100

    else:

        yoy_units_change = 0


    # --------------------------------------------------------
    # INVENTORY VALUE
    # --------------------------------------------------------

    inventory_with_cost = inventory.merge(
        products[
            [
                "sku",
                "unit_cost"
            ]
        ],
        on="sku",
        how="left"
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


    # --------------------------------------------------------
    # OPEN PURCHASE ORDERS
    # --------------------------------------------------------

    open_purchase_orders = purchase_orders[
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


    open_purchase_orders = (
        open_purchase_orders.merge(
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


    open_purchase_orders[
        "po_value"
    ] = (
        open_purchase_orders[
            "quantity"
        ]
        *
        open_purchase_orders[
            "unit_cost"
        ]
    )


    total_open_po_value = (
        open_purchase_orders[
            "po_value"
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


    # --------------------------------------------------------
    # TOP SELLING SKU
    # --------------------------------------------------------

    sku_sales_ytd = (
        current_ytd_sales
        .groupby(
            "sku",
            as_index=False
        )["units_sold"]
        .sum()
        .sort_values(
            "units_sold",
            ascending=False
        )
    )


    if not sku_sales_ytd.empty:

        top_sku = (
            sku_sales_ytd
            .iloc[0]["sku"]
        )

        top_sku_units = int(
            sku_sales_ytd
            .iloc[0]["units_sold"]
        )

    else:

        top_sku = "N/A"
        top_sku_units = 0


    # --------------------------------------------------------
    # CHECK ALL SKUS FOR SHORTAGE RISK
    # --------------------------------------------------------

    risk_rows = []

    for sku in products["sku"]:

        result = calculate_sku_projection(
            sku
        )

        if result is None:
            continue

        shortage_month = result[
            "shortage_month"
        ]

        if shortage_month is not None:

            risk_rows.append(
                {
                    "SKU": sku,
                    "Projected Shortage": (
                        shortage_month.strftime(
                            "%b %Y"
                        )
                    ),
                    "Shortage Date": shortage_month
                }
            )


    risk_df = pd.DataFrame(
        risk_rows
    )


    if not risk_df.empty:

        risk_df = (
            risk_df
            .sort_values(
                "Shortage Date"
            )
        )


    risk_count = len(
        risk_df
    )


    # ========================================================
    # NEW - BUSINESS HEALTH SUMMARY
    # ========================================================

    st.subheader(
        "Business Health"
    )

    health1, health2, health3 = st.columns(3)


    # Sales health
    with health1:

        if yoy_units_change > 0:

            st.success(
                f"Sales Performance: Growing\n\n"
                f"{yoy_units_change:+.1f}% vs {previous_year}"
            )

        elif yoy_units_change < 0:

            st.error(
                f"Sales Performance: Declining\n\n"
                f"{yoy_units_change:+.1f}% vs {previous_year}"
            )

        else:

            st.info(
                "Sales Performance: Stable"
            )


    # Inventory risk
    with health2:

        risk_percentage = (
            risk_count
            / len(products)
        ) * 100

        if risk_percentage >= 50:

            st.error(
                f"Inventory Risk: High Attention\n\n"
                f"{risk_count} products at risk"
            )

        elif risk_percentage >= 20:

            st.warning(
                f"Inventory Risk: Monitor\n\n"
                f"{risk_count} products at risk"
            )

        else:

            st.success(
                f"Inventory Risk: Healthy\n\n"
                f"{risk_count} products at risk"
            )


    # Purchase order health
    with health3:

        if delayed_po_count == 0:

            st.success(
                "Purchase Orders: Healthy\n\n"
                "No delayed POs"
            )

        elif delayed_po_count <= 5:

            st.warning(
                f"Purchase Orders: Monitor\n\n"
                f"{delayed_po_count} delayed POs"
            )

        else:

            st.error(
                f"Purchase Orders: Attention Needed\n\n"
                f"{delayed_po_count} delayed POs"
            )


    st.markdown("---")


    # --------------------------------------------------------
    # MANAGEMENT SUMMARY
    # --------------------------------------------------------

    st.subheader(
        "Key Business Indicators"
    )


    col1, col2, col3 = st.columns(3)


    with col1:

        st.metric(
            f"Units Sold YTD ({current_year})",
            f"{current_ytd_units:,}",
            f"{yoy_units_change:+.1f}% vs {previous_year}"
        )


    with col2:

        st.metric(
            "Inventory Value",
            f"${total_inventory_value:,.0f}"
        )

        st.caption(
            "Based on unit cost"
        )


    with col3:

        st.metric(
            "Open PO Value",
            f"${total_open_po_value:,.0f}"
        )

        st.caption(
            "Based on unit cost"
        )


    col4, col5, col6 = st.columns(3)


    with col4:

        st.metric(
            "Current Inventory Units",
            f"{total_inventory_units:,}"
        )


    with col5:

        st.metric(
            "Top-Selling SKU YTD",
            top_sku
        )

        st.caption(
            f"{top_sku_units:,} units sold"
        )


    with col6:

        st.metric(
            "Products Requiring Attention",
            risk_count
        )

        st.caption(
            "Projected shortage within 12 months"
        )


    st.markdown("---")


    # --------------------------------------------------------
    # SALES TREND
    # --------------------------------------------------------

    st.subheader(
        "Sales Trend"
    )


    current_monthly = (
        current_ytd_sales
        .groupby(
            current_ytd_sales[
                "month"
            ].dt.month
        )["units_sold"]
        .sum()
        .reset_index()
    )


    current_monthly.columns = [
        "month_number",
        "units_sold"
    ]


    current_monthly[
        "Year"
    ] = str(
        current_year
    )


    previous_monthly = (
        previous_ytd_sales
        .groupby(
            previous_ytd_sales[
                "month"
            ].dt.month
        )["units_sold"]
        .sum()
        .reset_index()
    )


    previous_monthly.columns = [
        "month_number",
        "units_sold"
    ]


    previous_monthly[
        "Year"
    ] = str(
        previous_year
    )


    monthly_comparison = pd.concat(
        [
            previous_monthly,
            current_monthly
        ],
        ignore_index=True
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


    monthly_comparison[
        "Month"
    ] = (
        monthly_comparison[
            "month_number"
        ].map(
            month_names
        )
    )


    monthly_comparison = (
        monthly_comparison.sort_values(
            [
                "Year",
                "month_number"
            ]
        )
    )


    sales_trend_chart = px.line(
        monthly_comparison,
        x="Month",
        y="units_sold",
        color="Year",
        markers=True,
        title=(
            f"Monthly Units Sold: "
            f"{previous_year} vs {current_year}"
        )
    )


    sales_trend_chart.update_layout(
        xaxis_title="Month",
        yaxis_title="Units Sold"
    )


    st.plotly_chart(
        sales_trend_chart,
        width="stretch"
    )


    # --------------------------------------------------------
    # TOP 5 SKUS
    # --------------------------------------------------------

    st.subheader(
        "Top 5 Selling SKUs"
    )


    top_5_skus = (
        sku_sales_ytd
        .head(5)
    )


    top_sku_chart = px.bar(
        top_5_skus,
        x="sku",
        y="units_sold",
        title=(
            f"Top 5 SKUs by Units Sold "
            f"({current_year} YTD)"
        )
    )


    top_sku_chart.update_layout(
        xaxis_title="SKU",
        yaxis_title="Units Sold"
    )


    st.plotly_chart(
        top_sku_chart,
        width="stretch"
    )


    # --------------------------------------------------------
    # INVENTORY / PROCUREMENT SUMMARY
    # --------------------------------------------------------

    st.subheader(
        "Inventory & Procurement Summary"
    )


    col7, col8 = st.columns(2)


    with col7:

        st.metric(
            "Open PO Quantity",
            f"{total_open_po_units:,} units"
        )


    with col8:

        st.metric(
            "Delayed Purchase Orders",
            delayed_po_count
        )


    # --------------------------------------------------------
    # SKUS AT RISK
    # --------------------------------------------------------

    st.subheader(
        "Products Requiring Attention"
    )


    if risk_df.empty:

        st.success(
            "No product is projected to run out "
            "within the next 12 months."
        )

    else:

        st.warning(
            f"{risk_count} product(s) are projected "
            "to run out within the next 12 months."
        )


        risk_display = risk_df[
            [
                "SKU",
                "Projected Shortage"
            ]
        ].copy()


        st.dataframe(
            risk_display,
            width="stretch",
            hide_index=True
        )


    st.info(
        "Revenue, profit, break-even and customer-level "
        "analysis will be added after the dataset is "
        "expanded with selling prices, customer data "
        "and operating cost information."
    )


# ============================================================
# PAGE 2 - SKU ANALYSIS
# ============================================================

elif page == "SKU Analysis":

    st.title(
        "SKU Inventory & Procurement Analysis"
    )

    st.write(
        "Detailed product-level inventory planning, "
        "forecasting and reorder analysis."
    )


    # --------------------------------------------------------
    # PRODUCT SELECTION
    # --------------------------------------------------------

    st.subheader(
        "Select a Product"
    )


    selected_sku = st.selectbox(
        "Choose SKU",
        products["sku"]
    )


    selected_product = products[
        products["sku"]
        == selected_sku
    ]


    product = selected_product.iloc[0]


    # --------------------------------------------------------
    # PRODUCT DETAILS
    # --------------------------------------------------------

    st.subheader(
        "Product Details"
    )


    col1, col2, col3 = st.columns(3)


    with col1:

        st.metric(
            "Category",
            product["category"]
        )


    with col2:

        st.metric(
            "Supplier",
            product["supplier_id"]
        )


    with col3:

        st.metric(
            "Lead Time",
            f'{product["lead_time_days"]} days'
        )


    col4, col5, col6 = st.columns(3)


    with col4:

        st.metric(
            "Pack Size",
            product["pack_size"]
        )


    with col5:

        st.metric(
            "Unit Cost",
            f'${product["unit_cost"]:.2f}'
        )


    with col6:

        st.metric(
            "Warehouse",
            product["warehouses"]
        )


    # --------------------------------------------------------
    # CURRENT INVENTORY
    # --------------------------------------------------------

    st.subheader(
        "Current Inventory"
    )


    selected_inventory = inventory[
        inventory["sku"]
        == selected_sku
    ].copy()


    total_inventory = (
        selected_inventory[
            "on_hand_qty"
        ].sum()
    )


    st.metric(
        "Total On-Hand Inventory",
        f"{int(total_inventory):,} units"
    )


    st.write(
        "Inventory by Warehouse"
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
    # INCOMING PURCHASE ORDERS
    # --------------------------------------------------------

    st.subheader(
        "Incoming Purchase Orders"
    )


    selected_pos = purchase_orders[
        (
            purchase_orders["sku"]
            == selected_sku
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
    ].copy()


    if selected_pos.empty:

        total_incoming = 0

        st.info(
            "No open purchase orders "
            "for this SKU."
        )

    else:

        total_incoming = (
            selected_pos[
                "quantity"
            ].sum()
        )


        st.metric(
            "Total Incoming Quantity",
            f"{int(total_incoming):,} units"
        )


        st.dataframe(
            selected_pos[
                [
                    "po_id",
                    "container_id",
                    "warehouse",
                    "quantity",
                    "expected_arrival_date",
                    "status"
                ]
            ],
            width="stretch",
            hide_index=True
        )


    # --------------------------------------------------------
    # HISTORICAL SALES
    # --------------------------------------------------------

    st.subheader(
        "Historical Sales"
    )


    selected_sales = sales[
        sales["sku"]
        == selected_sku
    ].copy()


    monthly_sales = (
        selected_sales
        .groupby(
            "month",
            as_index=False
        )["units_sold"]
        .sum()
        .sort_values(
            "month"
        )
    )


    average_monthly_sales = (
        monthly_sales[
            "units_sold"
        ].mean()
    )


    st.metric(
        "Average Monthly Sales",
        f"{average_monthly_sales:.0f} units"
    )


    fig = px.line(
        monthly_sales,
        x="month",
        y="units_sold",
        markers=True,
        title="Monthly Sales History"
    )


    fig.update_layout(
        xaxis_title="Month",
        yaxis_title="Units Sold"
    )


    st.plotly_chart(
        fig,
        width="stretch"
    )


    # --------------------------------------------------------
    # BASIC DEMAND FORECAST
    # --------------------------------------------------------

    st.subheader(
        "Basic Demand Forecast"
    )


    last_3_months = (
        monthly_sales.tail(3)
    )


    forecast_value = (
        last_3_months[
            "units_sold"
        ].mean()
    )


    st.metric(
        "3-Month Moving Average Forecast",
        f"{forecast_value:.0f} units / month"
    )


    st.write(
        "Forecast is based on the average sales "
        "of the most recent 3 months."
    )


    last_3_display = (
        last_3_months.copy()
    )


    last_3_display[
        "month"
    ] = (
        last_3_display[
            "month"
        ].dt.strftime(
            "%b %Y"
        )
    )


    st.dataframe(
        last_3_display,
        width="stretch",
        hide_index=True
    )


    # --------------------------------------------------------
    # PROJECTED INVENTORY
    # --------------------------------------------------------

    st.subheader(
        "Projected Inventory"
    )


    inventory_date = (
        selected_inventory[
            "as_of_date"
        ].max()
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


    projection_rows = []


    opening_inventory = int(
        total_inventory
    )


    forecast_demand = int(
        round(
            forecast_value
        )
    )


    for month in future_months:

        month_start = month

        month_end = (
            month
            + pd.offsets.MonthEnd(1)
        )


        incoming_this_month = selected_pos[
            (
                selected_pos[
                    "expected_arrival_date"
                ] >= month_start
            )
            &
            (
                selected_pos[
                    "expected_arrival_date"
                ] <= month_end
            )
        ]["quantity"].sum()


        closing_inventory = (
            opening_inventory
            + int(
                incoming_this_month
            )
            - forecast_demand
        )


        projection_rows.append(
            {
                "Month Date": month,

                "Month": (
                    month.strftime(
                        "%b %Y"
                    )
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


    display_projection = (
        projection_df[
            [
                "Month",
                "Opening Inventory",
                "Incoming",
                "Forecast Demand",
                "Closing Inventory"
            ]
        ]
    )


    st.dataframe(
        display_projection,
        width="stretch",
        hide_index=True
    )


    # --------------------------------------------------------
    # INVENTORY PROJECTION CHART
    # --------------------------------------------------------

    projection_chart = px.line(
        projection_df,
        x="Month",
        y="Closing Inventory",
        markers=True,
        title="Projected Inventory Over Time"
    )


    projection_chart.update_layout(
        xaxis_title="Month",
        yaxis_title="Projected Units"
    )


    st.plotly_chart(
        projection_chart,
        width="stretch"
    )


    # --------------------------------------------------------
    # SHORTAGE CHECK
    # --------------------------------------------------------

    shortage_rows = projection_df[
        projection_df[
            "Closing Inventory"
        ] < 0
    ]


    if shortage_rows.empty:

        st.success(
            "No stock shortage is projected "
            "during the next 12 months."
        )

    else:

        first_shortage = (
            shortage_rows.iloc[0]
        )


        first_shortage_month = (
            first_shortage[
                "Month Date"
            ]
        )


        st.error(
            "Projected shortage detected in "
            f"{first_shortage_month.strftime('%b %Y')}."
        )


    # --------------------------------------------------------
    # BASIC REORDER RECOMMENDATION
    # --------------------------------------------------------

    st.subheader(
        "Basic Reorder Recommendation"
    )


    if shortage_rows.empty:

        st.success(
            "No immediate reorder is suggested "
            "based on the current 12-month projection."
        )

    else:

        lead_time_days = int(
            product[
                "lead_time_days"
            ]
        )


        suggested_order_date = (
            first_shortage_month
            - pd.Timedelta(
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
                / pack_size
            )
            * pack_size
        )


        col7, col8 = st.columns(2)


        with col7:

            st.metric(
                "Suggested Order Date",

                suggested_order_date
                .strftime(
                    "%d %b %Y"
                )
            )


        with col8:

            st.metric(
                "Suggested Order Quantity",
                f"{suggested_order_quantity:,} units"
            )


        st.write(
            "The suggested order date is calculated "
            "by working backwards from the projected "
            "shortage using the supplier lead time."
        )


        st.write(
            "For this initial version, the suggested "
            "order quantity is approximately three "
            "months of forecast demand, rounded up "
            "to the product pack size."
        )