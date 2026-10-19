import streamlit as st
import pandas as pd
import plotly.express as px
import math



st.title("Inventory & Procurement Planning System")
st.write("CSIS 4495 Applied Research Project")



products = pd.read_csv("Data/products.csv")
inventory = pd.read_csv("Data/inventory.csv")
purchase_orders = pd.read_csv("Data/purchase_orders.csv")
sales = pd.read_csv("Data/sales_monthly.csv")




st.subheader("Select a Product")

selected_sku = st.selectbox(
    "Choose SKU",
    products["sku"]
)

selected_product = products[
    products["sku"] == selected_sku
]

product = selected_product.iloc[0]



st.subheader("Product Details")

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



st.subheader("Current Inventory")

selected_inventory = inventory[
    inventory["sku"] == selected_sku
]

total_inventory = selected_inventory[
    "on_hand_qty"
].sum()


st.metric(
    "Total On-Hand Inventory",
    f"{int(total_inventory):,} units"
)


st.write("Inventory by Warehouse")

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



st.subheader("Incoming Purchase Orders")

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


if selected_pos.empty:

    total_incoming = 0

    st.info(
        "No open purchase orders for this SKU."
    )

else:

    total_incoming = selected_pos[
        "quantity"
    ].sum()

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



st.subheader("Historical Sales")

selected_sales = sales[
    sales["sku"] == selected_sku
].copy()


selected_sales["month"] = pd.to_datetime(
    selected_sales["month"]
)


monthly_sales = (
    selected_sales
    .groupby(
        "month",
        as_index=False
    )["units_sold"]
    .sum()
    .sort_values("month")
)


average_monthly_sales = monthly_sales[
    "units_sold"
].mean()


st.metric(
    "Average Monthly Sales",
    f"{average_monthly_sales:.0f} units"
)


# Historical sales chart

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



st.subheader("Basic Demand Forecast")


last_3_months = monthly_sales.tail(3)


forecast_value = last_3_months[
    "units_sold"
].mean()


st.metric(
    "3-Month Moving Average Forecast",
    f"{forecast_value:.0f} units / month"
)


st.write(
    "Forecast is based on the average sales "
    "of the most recent 3 months."
)


# Clean last 3 months display

last_3_display = last_3_months.copy()

last_3_display["month"] = (
    last_3_display["month"]
    .dt.strftime("%b %Y")
)


st.dataframe(
    last_3_display,
    width="stretch",
    hide_index=True
)



st.subheader("Projected Inventory")



selected_pos["expected_arrival_date"] = pd.to_datetime(
    selected_pos["expected_arrival_date"]
)


inventory_date = pd.to_datetime(
    selected_inventory["as_of_date"].iloc[0]
)




projection_start = (
    inventory_date
    + pd.offsets.MonthBegin(1)
)


# Project 12 months

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
    round(forecast_value)
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
        + int(incoming_this_month)
        - forecast_demand
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



display_projection = projection_df[
    [
        "Month",
        "Opening Inventory",
        "Incoming",
        "Forecast Demand",
        "Closing Inventory"
    ]
]


st.dataframe(
    display_projection,
    width="stretch",
    hide_index=True
)




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

    first_shortage = shortage_rows.iloc[0]

    first_shortage_month = first_shortage[
        "Month Date"
    ]

    st.error(
        "Projected shortage detected in "
        f"{first_shortage_month.strftime('%b %Y')}."
    )



st.subheader("Basic Reorder Recommendation")


if shortage_rows.empty:

    st.success(
        "No immediate reorder is suggested "
        "based on the current 12-month projection."
    )

else:

    # Product lead time
    lead_time_days = int(
        product["lead_time_days"]
    )


    # Calculate latest suggested order date
    suggested_order_date = (
        first_shortage_month
        - pd.Timedelta(
            days=lead_time_days
        )
    )


    # Basic suggested order quantity:
    # 3 months of forecast demand
    raw_order_quantity = (
        forecast_value * 3
    )


    # Round quantity up to pack size
    pack_size = int(
        product["pack_size"]
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
            suggested_order_date.strftime(
                "%d %b %Y"
            )
        )


    with col8:

        st.metric(
            "Suggested Order Quantity",
            f"{suggested_order_quantity:,} units"
        )


    st.write(
        "The suggested order date is calculated by "
        "working backwards from the projected shortage "
        "using the supplier lead time."
    )


    st.write(
        "For this initial version, the suggested order "
        "quantity is approximately three months of "
        "forecast demand, rounded up to the product pack size."
    )