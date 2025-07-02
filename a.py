import streamlit as st
import pandas as pd
import mysql.connector
from datetime import datetime

st.set_page_config(page_title="Depot Productivity Dashboard", layout="wide")

def main():
    st.markdown("<h1 style='text-align: left;'>🚍 Depot Productivity Dashboard</h1>", unsafe_allow_html=True)

    # --- MySQL Connection ---
    try:
        conn = mysql.connector.connect(
            host="192.168.137.235",
            user="root",
            password="system",
            database="a"
        )
    except mysql.connector.Error as err:
        st.error(f"MySQL connection error: {err}")
        st.stop()

    # --- Fetch Data ---
    query = "SELECT * FROM depot_data"
    df = pd.read_sql(query, conn)
    conn.close()

    if 'id' in df.columns:
        df = df.drop(columns=['id'])

    df['entry_date'] = pd.to_datetime(df['entry_date'], errors='coerce')

    # --- Sidebar Filters ---
    st.sidebar.header("🔎 Filter Options")
    all_depots = sorted(df['depot_name'].dropna().unique())
    time_periods = ['Daily', 'Monthly', 'Quarterly', 'Yearly']

    selected_depot = st.sidebar.selectbox("Select Depot:", all_depots)
    selected_time_period = st.sidebar.selectbox("Select Time Period:", time_periods)

    filtered_df = df[df['depot_name'] == selected_depot]

    # --- Time Filters ---
    if selected_time_period == "Daily":
        date_filter = st.sidebar.date_input("Select Date")
        filtered_df = filtered_df[filtered_df['entry_date'] == pd.to_datetime(date_filter)]

    elif selected_time_period == "Monthly":
        year_filter = st.sidebar.selectbox("Select Year:", sorted(filtered_df['entry_date'].dt.year.dropna().unique(), reverse=True))
        month_filter = st.sidebar.selectbox(
            "Select Month:",
            options=list(range(1, 13)),
            format_func=lambda x: ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][x - 1]
        )
        filtered_df = filtered_df[
            (filtered_df['entry_date'].dt.year == year_filter) &
            (filtered_df['entry_date'].dt.month == month_filter)
        ]

    elif selected_time_period == "Quarterly":
        year_filter = st.sidebar.selectbox("Select Year:", sorted(filtered_df['entry_date'].dt.year.dropna().unique(), reverse=True))
        quarter_filter = st.sidebar.selectbox("Select Quarter:", ["Q1 (Jan,Feb,Mar)", "Q2 (Apr,May,Jun)",
                                                                   "Q3 (Jul,Aug,Sep)", "Q4 (Oct,Nov,Dec)"])
        quarter_map = {
            "Q1 (Jan,Feb,Mar)": (1, 3),
            "Q2 (Apr,May,Jun)": (4, 6),
            "Q3 (Jul,Aug,Sep)": (7, 9),
            "Q4 (Oct,Nov,Dec)": (10, 12)
        }
        start_month, end_month = quarter_map[quarter_filter]
        filtered_df = filtered_df[
            (filtered_df['entry_date'].dt.year == year_filter) &
            (filtered_df['entry_date'].dt.month >= start_month) &
            (filtered_df['entry_date'].dt.month <= end_month)
        ]

    elif selected_time_period == "Yearly":
        year_filter = st.sidebar.selectbox("Select Year:", sorted(filtered_df['entry_date'].dt.year.dropna().unique(), reverse=True))
        filtered_df = filtered_df[filtered_df['entry_date'].dt.year == year_filter]

    # --- If Data Found ---
    if not filtered_df.empty:
        num_days = filtered_df['entry_date'].nunique()
        category = filtered_df['category'].iloc[0]

        st.subheader(f"Productivity Ratios for {selected_depot}")
        st.markdown(f"*Category:* {category}  |  *Days Considered:* {num_days}")

        # --- Metric Cards ---
        planned_schedules = int(filtered_df['planned_schedules'].sum())
        total_drivers = int(filtered_df['total_drivers'].sum())

        drivers_per_schedule = (total_drivers / planned_schedules) if planned_schedules != 0 else 0
        drivers_per_schedule = round(drivers_per_schedule, 2)
        
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric(label="Planned Schedules", value=f"{planned_schedules:,}")

        with col2:
            st.metric(label="Total Drivers", value=f"{total_drivers}")

        with col3:
            st.metric(label="Drivers/Schedule (%)", value=f"{drivers_per_schedule} %")

        # --- Thresholds ---
        rural_thresholds = {
            "Weekly Off": 14.0,
            "Special Off (Night Out/IC, Online)": 25.0,
            "Others": 1.70,
            "Long Leave & Absent": 2.0,
            "Sick Leave": 2.0,
            "Spot Absent": 1.0,
            "Double Duty": 16.0,
            "Off Cancellation": 0.00,
            "Services / Driver Check": 2.18
        }
        urban_thresholds = {
            "Weekly Off": 14.0,
            "Special Off (Night Out/IC, Online)": 27.4,
            "Others": 1.0,
            "Long Leave & Absent": 6.0,
            "Sick Leave": 2.0,
            "Spot Absent": 2.0,
            "Double Duty": 8.0,
            "Off Cancellation": 0.00,
            "Services / Driver Check": 2.43
        }
        thresholds = rural_thresholds if category == "Rural" else urban_thresholds if category == "Urban" else {}

        # --- Metric Mapping ---
        metric_map = {
            "Planned Schedules": "planned_schedules",
            "Total Drivers": "total_drivers",
            "Weekly Off (%)": "Day_weekly_off_per",
            "Special Off (Night Out/IC, Online) (%)": "Day_special_off_per",
            "Others (%)": "Day_other_per",
            "Long Leave & Absent (%)": "Day_leave_absent_per",
            "Sick Leave (%)": "Day_sick_leave_per",
            "Spot Absent (%)": "Day_spot_absent_per",
            "Double Duty (%)": "Day_double_duty_per",
            "Off Cancellation (%)": "Mon_off_cancellation_per",
            "Services / Driver Check (%)": "service_driver_check"
        }

        # --- Aggregation ---
        display_data = []
        for label, col in metric_map.items():
            if label in ["Planned Schedules", "Total Drivers"]:
                value = filtered_df[col].sum()
            else:
                value = filtered_df[col].mean()

            base_label = label.replace(" (%)", "")
            threshold_value = thresholds.get(base_label, None)

            if isinstance(threshold_value, (int, float)):
                variance = round(value - threshold_value, 2)
            else:
                variance = None

            display_data.append({
                'Metric': label,
                'Benchmark': threshold_value if pd.notnull(threshold_value) else None,
                'Value': round(value, 2) if pd.notnull(value) else None,
                'Variance': variance if pd.notnull(variance) else None
            })

        display_df = pd.DataFrame(display_data)

        # --- Percentage Columns ---
        is_percent = display_df['Metric'].str.contains(r'\(.*%\)', regex=True)

        # --- Formatting ---
        def format_value(val, is_per):
            if pd.isna(val):
                return ''
            return f"{val:.1f}%" if is_per else f"{val:.0f}"

        def format_variance(val, is_per):
            if pd.isna(val):
                return ''
            return f"{val:+.1f}%" if is_per else f"{val:+.0f}"

        display_df['Value'] = [
            format_value(v, p) for v, p in zip(display_df['Value'], is_percent)
        ]
        display_df['Benchmark'] = [
            format_value(b, p) if pd.notna(b) else '' for b, p in zip(display_df['Benchmark'], is_percent)
        ]
        display_df['Variance'] = [
            format_variance(v, p) if pd.notna(v) else '' for v, p in zip(display_df['Variance'], is_percent)
        ]

        # --- Styling Functions ---
        def style_variance(val):
            if isinstance(val, str) and val.startswith('+'):
                return 'background-color: #f47b7b; font-weight: bold'
            elif isinstance(val, str) and val.startswith('-'):
                return 'background-color: #b6e2b6; font-weight: bold'
            return ''

        def style_benchmark(val):
            if val != '':
                return 'background-color: #fff7a7; font-weight: bold'
            return ''

        styled_df = display_df.style \
            .applymap(style_variance, subset=['Variance']) \
            .applymap(style_benchmark, subset=['Benchmark']) \
            .set_table_styles([
                {'selector': 'th', 'props': [('font-weight', 'bold'), ('background-color', '#f0f0f0'), ('color', 'black')]},
                {'selector': 'td', 'props': [('text-align', 'center')]}
            ])

        st.dataframe(styled_df, use_container_width=True, hide_index=True)

        # --- Data Labels Legend ---
        st.markdown("""
        <div style="display: flex; gap: 20px; align-items: center; margin-top: 10px;">
            <div style="display: flex; align-items: center;">
                <div style="width: 20px; height: 20px; background-color: #fff7a7; border: 1px solid #ccc; margin-right: 8px;"></div>
                <div>Benchmark</div>
            </div>
            <div style="display: flex; align-items: center;">
                <div style="width: 20px; height: 20px; background-color: #b6e2b6; border: 1px solid #ccc; margin-right: 8px;"></div>
                <div>Within / Below Benchmark</div>
            </div>
            <div style="display: flex; align-items: center;">
                <div style="width: 20px; height: 20px; background-color: #f47b7b; border: 1px solid #ccc; margin-right: 8px;"></div>
                <div>Above Benchmark</div>
            </div>
        </div>
        """, unsafe_allow_html=True)


        st.info("""
        • 'Planned Schedules' and 'Total Drivers' are total sums.

        • Variance has *red background* if exceeding benchmark, *green background* if within or better.
        
        • Benchmark is highlighted in *yellow*.
        """)

    else:
        st.warning("⚠ No data available for the selected filters.")


if __name__ == "__main__":
    main()
