"""
CENACE Demand Data Downloader - Streamlit App
==============================================
A modern web interface for downloading Mexico's electrical demand data from CENACE
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta, date
import zipfile
import io
import os
from pathlib import Path
import time
import json

# Import our custom CENACE module
from cenace_downloader import (
    CENACEClient, 
    DataAssembler,
    get_all_zones,
    estimate_download_time
)

# Page configuration
st.set_page_config(
    page_title="CENACE Demand Downloader",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better UI
st.markdown("""
<style>
    .stProgress > div > div > div > div {
        background-color: #00CC88;
    }
    .stat-card {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        margin: 10px 0;
    }
    .download-btn {
        background-color: #00CC88;
        color: white;
        padding: 10px 20px;
        border-radius: 5px;
        text-decoration: none;
        display: inline-block;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'download_data' not in st.session_state:
    st.session_state.download_data = None
if 'download_complete' not in st.session_state:
    st.session_state.download_complete = False
if 'progress_text' not in st.session_state:
    st.session_state.progress_text = ""
if 'data_refresh_key' not in st.session_state:
    st.session_state.data_refresh_key = 0
# Note: We don't use pending_rerun anymore - widget interactions handle reruns naturally

# Header
st.title("⚡ CENACE Demand & Price Downloader")
st.markdown("### Download Mexico's electrical demand and zonal price data from CENACE's web services")

# Sidebar for configuration
with st.sidebar:
    st.header("🔧 Configuration")
    
    # System and Zone Selection
    st.subheader("1️⃣ Select Zones")
    
    # Get all available zones
    all_zones = get_all_zones()
    
    # System filter
    systems = ["All"] + list(all_zones.keys())
    
    # System filter - this widget naturally triggers reruns when changed
    selected_system = st.selectbox(
        "Filter by System",
        systems,
        help="Filter zones by electrical system",
        key="system_filter_selectbox"
    )
    
    # Prepare zone options based on system filter
    if selected_system == "All":
        zone_options = []
        for system, zones in all_zones.items():
            for zone in zones:
                zone_options.append(f"{zone} ({system})")
    else:
        zone_options = [f"{zone} ({selected_system})" for zone in all_zones[selected_system]]
    
    # Select All checkbox
    select_all = st.checkbox("Select All Zones (max 10)", value=False)
    
    # Zone multiselect
    if select_all:
        # Take first 10 zones if Select All is checked
        default_zones = zone_options[:10]
        st.info(f"ℹ️ Selected first 10 zones due to API limit")
    else:
        default_zones = []
    
    selected_zones = st.multiselect(
        "Select Zones (max 10)",
        options=zone_options,
        default=default_zones,
        max_selections=10,
        help="Select up to 10 zones to download data"
    )
    
    # Parse selected zones to separate zone names and systems
    parsed_zones = []
    for zone_str in selected_zones:
        zone_name = zone_str.rsplit(" (", 1)[0]
        system_name = zone_str.rsplit(" (", 1)[1].rstrip(")")
        parsed_zones.append({"zone": zone_name, "system": system_name})
    
    # Date Range Selection
    st.subheader("2️⃣ Select Date Range")
    
    date_preset = st.radio(
        "Date Range Preset",
        ["Last 7 Days", "Last 30 Days", "Current Month", "Custom"],
        index=0
    )
    
    # Calculate date range based on preset
    today = date.today()
    if date_preset == "Last 7 Days":
        start_date = today - timedelta(days=7)
        end_date = today - timedelta(days=1)
    elif date_preset == "Last 30 Days":
        start_date = today - timedelta(days=30)
        end_date = today - timedelta(days=1)
    elif date_preset == "Current Month":
        start_date = today.replace(day=1)
        end_date = today - timedelta(days=1)
    else:  # Custom
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input(
                "Start Date",
                value=today - timedelta(days=7),
                max_value=today - timedelta(days=1)
            )
        with col2:
            end_date = st.date_input(
                "End Date",
                value=today - timedelta(days=1),
                min_value=start_date,
                max_value=today - timedelta(days=1)
            )
    
    # Validate date range (max 1 year)
    date_diff = (end_date - start_date).days
    if date_diff > 365:
        st.error("⚠️ Maximum date range is 1 year")
        start_date = end_date - timedelta(days=365)
    
    st.info(f"📅 Selected: {start_date} to {end_date} ({date_diff + 1} days)")
    
    # Advanced Options
    st.subheader("3️⃣ Advanced Options")
    
    process_type = st.selectbox(
        "Process Type",
        ["MDA"],
        help="MDA: Mercado del Día en Adelanto",
        key="process_type_selectbox"
    )
    
    # API Settings (with best practices)
    with st.expander("⚙️ API Settings"):
        verify_ssl = st.checkbox(
            "Verify SSL Certificate",
            value=False,
            help="CENACE's SSL certificate often has issues. Uncheck if you get SSL errors."
        )
        
        retry_attempts = st.number_input(
            "Retry Attempts",
            min_value=1,
            max_value=5,
            value=3,
            help="Number of retry attempts for failed requests"
        )
        
        delay_between_requests = st.slider(
            "Delay Between Requests (seconds)",
            min_value=0.5,
            max_value=5.0,
            value=1.0,
            step=0.5,
            help="Delay between API requests to avoid overwhelming the server"
        )
    
    # Download button
    st.subheader("4️⃣ Download Demand & Price Data")
    
    if len(selected_zones) == 0:
        st.warning("⚠️ Please select at least one zone")
        download_disabled = True
    else:
        # Estimate download time
        estimated_time = estimate_download_time(
            len(parsed_zones), 
            date_diff + 1,
            delay_between_requests
        )
        st.info(f"⏱️ Estimated time (demand + prices): {estimated_time}")
        download_disabled = False
    
    download_button = st.button(
        "🚀 Start Download",
        disabled=download_disabled,
        use_container_width=True,
        type="primary"
    )

# Main content area
main_container = st.container()

with main_container:
    # Create tabs for different views
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Dashboard", "📈 Visualizations", "📁 Downloads", "ℹ️ Help"])
    
    with tab1:
        # Dashboard Tab - Always read fresh from session state
        # Use .get() to ensure we're reading the current value, not a cached reference
        df = st.session_state.get('download_data')
        
        # Check if we have valid data
        has_valid_data = (df is not None and 
                         hasattr(df, 'empty') and 
                         not df.empty and
                         'fecha' in df.columns and 
                         'zona_carga' in df.columns)
        
        if not has_valid_data:
            # Show instructions when no data
            st.markdown("""
            ### 👋 Welcome to the CENACE Demand & Price Downloader
            
            **Quick Start:**
            1. Select zones from the sidebar (up to 10)
            2. Choose your date range
            3. Click "Start Download" to retrieve demand **and** zonal prices
            4. View, analyze, and export your merged dataset
            
            **Features:**
            - ✅ Mix zones from different systems
            - ✅ Automatic 7-day chunking for API limits
            - ✅ Smart caching to avoid duplicate requests
            - ✅ Real-time progress tracking
            - ✅ Demand & price preview and statistics
            - ✅ Multiple download formats (CSV, ZIP, Excel)
            """)
            
            # Show system information
            st.subheader("📍 Available Systems and Zones")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("SIN", f"{len(all_zones.get('SIN', []))} zones", 
                         "Sistema Interconectado Nacional")
            with col2:
                st.metric("BCA", f"{len(all_zones.get('BCA', []))} zones", 
                         "Baja California")
            with col3:
                st.metric("BCS", f"{len(all_zones.get('BCS', []))} zones", 
                         "Baja California Sur")
            
        else:
            # Show data dashboard
            # Check if DataFrame has required columns and data
            if 'fecha' not in df.columns or 'zona_carga' not in df.columns:
                st.warning("⚠️ No data available to display")
            else:
                st.subheader("📊 Data Overview")

                price_columns = [col for col in df.columns if col.startswith('precio')]
                primary_price_col = 'precio_total' if 'precio_total' in df.columns else (price_columns[0] if price_columns else None)
                price_series = df[primary_price_col].dropna() if primary_price_col else pd.Series(dtype=float)
                has_price = not price_series.empty

                # Key metrics
                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    st.metric("Total Records", f"{len(df):,}")
                with col2:
                    st.metric("Date Range", f"{df['fecha'].min().date()} to {df['fecha'].max().date()}")
                with col3:
                    st.metric("Zones", len(df['zona_carga'].unique()))
                with col4:
                    st.metric("Systems", len(df['sistema'].unique()))

                if has_price:
                    col5, col6, col7 = st.columns(3)
                    avg_price = price_series.mean()
                    max_price = price_series.max()
                    min_price = price_series.min()
                    price_spread = max_price - min_price

                    with col5:
                        st.metric("Average Price (MXN/MWh)", f"{avg_price:,.2f}")
                    with col6:
                        st.metric("Peak Price (MXN/MWh)", f"{max_price:,.2f}")
                    with col7:
                        st.metric("Price Spread", f"{price_spread:,.2f}")
                
                # Statistics by zone
                st.subheader("📈 Zone Statistics")

                agg_map = {
                    'demanda': ['mean', 'max', 'min', 'std'],
                    'fecha': 'count'
                }

                if has_price and primary_price_col:
                    agg_map[primary_price_col] = ['mean', 'max', 'min']

                zone_stats = df.groupby('zona_carga').agg(agg_map).round(2)

                if has_price and primary_price_col:
                    price_spread = (zone_stats[(primary_price_col, 'max')] - zone_stats[(primary_price_col, 'min')]).round(2)
                    zone_stats[(primary_price_col, 'spread')] = price_spread

                rename_map = {
                    ('demanda', 'mean'): 'Avg Demand (MW)',
                    ('demanda', 'max'): 'Peak Demand (MW)',
                    ('demanda', 'min'): 'Min Demand (MW)',
                    ('demanda', 'std'): 'Demand Std Dev',
                    ('fecha', 'count'): 'Records'
                }

                if has_price and primary_price_col:
                    rename_map.update({
                        (primary_price_col, 'mean'): 'Avg Price (MXN/MWh)',
                        (primary_price_col, 'max'): 'Peak Price (MXN/MWh)',
                        (primary_price_col, 'min'): 'Min Price (MXN/MWh)',
                        (primary_price_col, 'spread'): 'Price Spread (Max-Min)'
                    })

                def format_column(col):
                    if isinstance(col, tuple):
                        return rename_map.get(col, ' '.join(str(part).title() for part in col if part))
                    return rename_map.get(col, str(col))

                zone_stats.columns = [format_column(col) for col in zone_stats.columns]
                sort_column = 'Peak Demand (MW)' if 'Peak Demand (MW)' in zone_stats.columns else zone_stats.columns[0]
                zone_stats = zone_stats.sort_values(sort_column, ascending=False)

                st.dataframe(zone_stats, use_container_width=True)
                
                # Data preview
                st.subheader("🔍 Data Preview")
                st.caption("Preview includes merged demand and price data. Use filters to focus on a single zone.")

                # Add filters for preview
                col1, col2 = st.columns(2)
                with col1:
                    preview_zone = st.selectbox(
                        "Filter by Zone (Preview)",
                        ["All"] + list(df['zona_carga'].unique()),
                        key="preview_zone_selectbox"
                    )
                with col2:
                    preview_limit = st.number_input(
                        "Number of rows",
                        min_value=10,
                        max_value=1000,
                        value=100,
                        step=10
                    )
                
                # Apply preview filters
                preview_df = df if preview_zone == "All" else df[df['zona_carga'] == preview_zone]
                st.dataframe(preview_df.head(preview_limit), use_container_width=True)
    
    with tab2:
        # Visualizations Tab - Always get fresh data from session state
        df = st.session_state.get('download_data', None)
        # Check for all required columns including 'fecha' and 'datetime'
        has_valid_data = (df is not None and 
                         hasattr(df, 'empty') and 
                         not df.empty and
                         'zona_carga' in df.columns and
                         'fecha' in df.columns and
                         'datetime' in df.columns)
        
        if has_valid_data:

            st.subheader("📈 Data Visualizations")

            viz_df = df.copy()
            price_columns = [col for col in viz_df.columns if col.startswith('precio')]
            primary_price_col = 'precio_total' if 'precio_total' in viz_df.columns else (price_columns[0] if price_columns else None)
            price_series = viz_df[primary_price_col].dropna() if primary_price_col else pd.Series(dtype=float)
            has_price = not price_series.empty

            # Visualization selector
            viz_type = st.selectbox(
                "Select Visualization",
                ["Demand Time Series", "Daily Patterns", "Zone Comparison",
                 "Heatmap", "Peak Analysis", "Weekday vs Weekend"],
                key="viz_type_selectbox"
            )

            if viz_type == "Demand Time Series":
                zone_to_plot = st.selectbox(
                    "Select Zone",
                    viz_df['zona_carga'].unique(),
                    key="viz_zone_plot_selectbox"
                )

                zone_df = viz_df[viz_df['zona_carga'] == zone_to_plot].copy()
                zone_df = zone_df.sort_values('datetime')

                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=zone_df['datetime'],
                    y=zone_df['demanda'],
                    mode='lines',
                    name='Demand (MW)',
                    line=dict(color='#1f77b4', width=3)
                ))

                if has_price:
                    fig.add_trace(go.Scatter(
                        x=zone_df['datetime'],
                        y=zone_df[primary_price_col],
                        mode='markers',
                        name='Price (MXN/MWh)',
                        marker=dict(color='#ff7f0e', size=6),
                        yaxis='y2'
                    ))

                fig.update_layout(
                    title=f"Demand & Price Time Series - {zone_to_plot}",
                    xaxis_title="Date/Time",
                    yaxis=dict(title='Demand (MW)'),
                    yaxis2=dict(title='Price (MXN/MWh)', overlaying='y', side='right', showgrid=False),
                    height=500,
                    legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1)
                )
                st.plotly_chart(fig, use_container_width=True)

            elif viz_type == "Daily Patterns":
                zone_to_analyze = st.selectbox(
                    "Select Zone",
                    viz_df['zona_carga'].unique(),
                    key="viz_zone_analyze_selectbox"
                )

                zone_df = viz_df[viz_df['zona_carga'] == zone_to_analyze].copy()
                zone_df['hour'] = zone_df['datetime'].dt.hour

                agg_dict = {'demanda': ['mean', 'std']}
                if has_price and primary_price_col:
                    agg_dict[primary_price_col] = ['mean']

                hourly_stats = zone_df.groupby('hour').agg(agg_dict).sort_index()

                demand_mean = hourly_stats[('demanda', 'mean')]
                demand_std = hourly_stats[('demanda', 'std')].fillna(0)

                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=demand_mean.index,
                    y=demand_mean,
                    mode='lines',
                    name='Average Demand (MW)',
                    line=dict(color='#1f77b4', width=3)
                ))
                fig.add_trace(go.Scatter(
                    x=demand_mean.index,
                    y=demand_mean + demand_std,
                    mode='lines',
                    name='Demand Upper Bound',
                    line=dict(color='#1f77b4', dash='dash')
                ))
                fig.add_trace(go.Scatter(
                    x=demand_mean.index,
                    y=demand_mean - demand_std,
                    mode='lines',
                    name='Demand Lower Bound',
                    line=dict(color='#1f77b4', dash='dash')
                ))

                if has_price and primary_price_col:
                    price_mean = hourly_stats[(primary_price_col, 'mean')]
                    fig.add_trace(go.Scatter(
                        x=price_mean.index,
                        y=price_mean,
                        mode='markers',
                        name='Average Price (MXN/MWh)',
                        marker=dict(color='#ff7f0e', size=8),
                        yaxis='y2'
                    ))

                fig.update_layout(
                    title=f"Daily Demand & Price Pattern - {zone_to_analyze}",
                    xaxis_title="Hour of Day",
                    yaxis=dict(title='Demand (MW)'),
                    yaxis2=dict(title='Price (MXN/MWh)', overlaying='y', side='right', showgrid=False),
                    height=500,
                    legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1)
                )
                st.plotly_chart(fig, use_container_width=True)

            elif viz_type == "Zone Comparison":
                zone_order = list(viz_df['zona_carga'].unique())

                fig = go.Figure()
                fig.add_trace(go.Box(
                    x=viz_df['zona_carga'],
                    y=viz_df['demanda'],
                    name='Demand (MW)',
                    marker_color='#1f77b4',
                    boxmean=True
                ))

                if has_price and primary_price_col:
                    price_summary = (
                        viz_df.groupby('zona_carga')[primary_price_col]
                        .mean()
                        .reindex(zone_order)
                        .reset_index()
                        .dropna(subset=[primary_price_col])
                    )
                    if not price_summary.empty:
                        fig.add_trace(go.Scatter(
                            x=price_summary['zona_carga'],
                            y=price_summary[primary_price_col],
                            mode='markers',
                            name='Avg Price (MXN/MWh)',
                            marker=dict(color='#ff7f0e', size=10, symbol='diamond'),
                            yaxis='y2'
                        ))

                fig.update_layout(
                    title="Demand Distribution & Price by Zone",
                    xaxis=dict(title='Zone', categoryorder='array', categoryarray=zone_order),
                    yaxis=dict(title='Demand (MW)'),
                    yaxis2=dict(title='Price (MXN/MWh)', overlaying='y', side='right', showgrid=False),
                    height=500,
                    legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1)
                )
                st.plotly_chart(fig, use_container_width=True)

            elif viz_type == "Heatmap":
                zone_for_heatmap = st.selectbox(
                    "Select Zone",
                    viz_df['zona_carga'].unique(),
                    key="viz_zone_heatmap_selectbox"
                )

                zone_df = viz_df[viz_df['zona_carga'] == zone_for_heatmap].copy()
                zone_df['hour'] = zone_df['datetime'].dt.hour
                zone_df['date'] = zone_df['datetime'].dt.date

                heatmap_tabs = ["Demand Heatmap"] + (["Price Heatmap"] if has_price and primary_price_col else [])
                heatmap_containers = st.tabs(heatmap_tabs)

                demand_pivot = zone_df.pivot_table(values='demanda', index='hour', columns='date', aggfunc='mean')
                with heatmap_containers[0]:
                    fig = px.imshow(
                        demand_pivot,
                        labels=dict(x="Date", y="Hour", color="Demand (MW)"),
                        title=f"Demand Heatmap - {zone_for_heatmap}",
                        color_continuous_scale="RdYlGn_r",
                        aspect="auto"
                    )
                    fig.update_layout(height=600)
                    st.plotly_chart(fig, use_container_width=True)

                if has_price and primary_price_col:
                    price_pivot = zone_df.pivot_table(values=primary_price_col, index='hour', columns='date', aggfunc='mean')
                    with heatmap_containers[1]:
                        if price_pivot.empty or price_pivot.dropna(how='all').empty:
                            st.info("No price data available for the selected zone/date range.")
                        else:
                            fig_price = px.imshow(
                                price_pivot,
                                labels=dict(x="Date", y="Hour", color="Price (MXN/MWh)"),
                                title=f"Price Heatmap - {zone_for_heatmap}",
                                color_continuous_scale="Viridis",
                                aspect="auto"
                            )
                            fig_price.update_layout(height=600)
                            st.plotly_chart(fig_price, use_container_width=True)

            elif viz_type == "Peak Analysis":
                demand_peaks = viz_df.groupby([viz_df['fecha'].dt.date, 'zona_carga'])['demanda'].max().reset_index()
                demand_peaks.columns = ['date', 'zona_carga', 'peak_demand']

                fig = go.Figure()
                for zone in demand_peaks['zona_carga'].unique():
                    zone_peaks = demand_peaks[demand_peaks['zona_carga'] == zone]
                    fig.add_trace(go.Scatter(
                        x=zone_peaks['date'],
                        y=zone_peaks['peak_demand'],
                        mode='lines',
                        name=f"{zone} Demand",
                        legendgroup=zone,
                        line=dict(width=2)
                    ))

                if has_price and primary_price_col:
                    price_peaks = viz_df.groupby([viz_df['fecha'].dt.date, 'zona_carga'])[primary_price_col].max().reset_index()
                    price_peaks.columns = ['date', 'zona_carga', 'peak_price']
                    price_peaks = price_peaks.dropna(subset=['peak_price'])
                    for zone in price_peaks['zona_carga'].unique():
                        zone_prices = price_peaks[price_peaks['zona_carga'] == zone]
                        fig.add_trace(go.Scatter(
                            x=zone_prices['date'],
                            y=zone_prices['peak_price'],
                            mode='markers',
                            name=f"{zone} Price",
                            legendgroup=zone,
                            marker=dict(size=8, color='#ff7f0e'),
                            yaxis='y2'
                        ))

                fig.update_layout(
                    title="Daily Peak Demand & Price by Zone",
                    xaxis_title="Date",
                    yaxis=dict(title='Peak Demand (MW)'),
                    yaxis2=dict(title='Peak Price (MXN/MWh)', overlaying='y', side='right', showgrid=False),
                    height=500,
                    legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1)
                )
                st.plotly_chart(fig, use_container_width=True)

            elif viz_type == "Weekday vs Weekend":
                comparison_df = viz_df.copy()
                comparison_df['weekday'] = comparison_df['datetime'].dt.weekday
                comparison_df['day_type'] = comparison_df['weekday'].isin([5, 6]).map({True: 'Weekend', False: 'Weekday'})

                agg_map = {'demanda': 'mean'}
                if has_price and primary_price_col:
                    agg_map[primary_price_col] = 'mean'

                comparison = comparison_df.groupby(['zona_carga', 'day_type']).agg(agg_map).reset_index()

                fig = go.Figure()
                for idx, day_type in enumerate(sorted(comparison['day_type'].unique())):
                    subset = comparison[comparison['day_type'] == day_type]
                    fig.add_trace(go.Bar(
                        x=subset['zona_carga'],
                        y=subset['demanda'],
                        name=f"{day_type} Demand",
                        offsetgroup=idx,
                        marker_color='#1f77b4' if day_type == 'Weekday' else '#2ca02c',
                        legendgroup=day_type
                    ))

                if has_price and primary_price_col:
                    for idx, day_type in enumerate(sorted(comparison['day_type'].unique())):
                        subset = comparison[comparison['day_type'] == day_type]
                        subset = subset.dropna(subset=[primary_price_col])
                        if subset.empty:
                            continue
                        fig.add_trace(go.Scatter(
                            x=subset['zona_carga'],
                            y=subset[primary_price_col],
                            mode='markers',
                            name=f"{day_type} Price",
                            marker=dict(size=9, symbol='diamond', color='#ff7f0e'),
                            yaxis='y2',
                            legendgroup=day_type,
                            offsetgroup=idx
                        ))

                fig.update_layout(
                    title="Weekday vs Weekend Demand & Price",
                    xaxis_title="Zone",
                    yaxis=dict(title='Average Demand (MW)'),
                    yaxis2=dict(title='Average Price (MXN/MWh)', overlaying='y', side='right', showgrid=False),
                    barmode='group',
                    height=500,
                    legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1)
                )
                st.plotly_chart(fig, use_container_width=True)

        else:
            st.info("📊 Download data first to see visualizations")
    
    with tab3:
        # Downloads Tab - Always get fresh data from session state
        df = None
        if 'download_data' in st.session_state and st.session_state.download_data is not None:
            df = st.session_state.download_data.copy() if hasattr(st.session_state.download_data, 'copy') else st.session_state.download_data
        
        # Check for all required columns
        has_valid_data = (df is not None and 
                         hasattr(df, 'empty') and 
                         not df.empty and
                         'zona_carga' in df.columns and
                         'fecha' in df.columns)
        
        if has_valid_data:

            st.subheader("📁 Download Options")
            st.caption("All exports include hourly demand and zonal price fields.")

            price_columns = [col for col in df.columns if col.startswith('precio')]
            primary_price_col = 'precio_total' if 'precio_total' in df.columns else (price_columns[0] if price_columns else None)
            price_series = df[primary_price_col].dropna() if primary_price_col else pd.Series(dtype=float)
            has_price = not price_series.empty

            # Prepare different download formats
            col1, col2, col3 = st.columns(3)

            with col1:
                # Combined CSV
                st.markdown("### 📄 Combined Demand & Price Data")
                csv_buffer = io.StringIO()
                df.to_csv(csv_buffer, index=False)
                csv_data = csv_buffer.getvalue()
                
                st.download_button(
                    label="⬇️ Download All Data (CSV)",
                    data=csv_data,
                    file_name=f"cenace_data_{start_date}_{end_date}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            
            with col2:
                # ZIP file with individual CSVs
                st.markdown("### 📦 Individual Zone Files")
                
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for zone in df['zona_carga'].unique():
                        zone_df = df[df['zona_carga'] == zone]
                        csv_buffer = io.StringIO()
                        zone_df.to_csv(csv_buffer, index=False)
                        zipf.writestr(f"{zone.replace(' ', '_')}.csv", csv_buffer.getvalue())
                
                st.download_button(
                    label="⬇️ Download ZIP (Individual CSVs)",
                    data=zip_buffer.getvalue(),
                    file_name=f"cenace_zones_{start_date}_{end_date}.zip",
                    mime="application/zip",
                    use_container_width=True
                )
            
            with col3:
                # Excel file with analysis
                st.markdown("### 📊 Excel with Analysis")

                excel_buffer = io.BytesIO()
                with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
                    # Raw data
                    df.to_excel(writer, sheet_name='Raw Data', index=False)

                    # Zone statistics (calculate here)
                    if 'demanda' in df.columns:
                        zone_stats = df.groupby('zona_carga')['demanda'].agg(['mean', 'max', 'min', 'std', 'count']).round(2)
                        zone_stats.columns = ['Avg Demand (MW)', 'Peak Demand (MW)',
                                             'Min Demand (MW)', 'Std Dev', 'Records']
                        zone_stats.to_excel(writer, sheet_name='Zone Statistics')

                    if has_price and primary_price_col:
                        price_stats = df.groupby('zona_carga')[primary_price_col].agg(['mean', 'max', 'min', 'std']).round(2)
                        price_stats.columns = ['Avg Price (MXN/MWh)', 'Peak Price (MXN/MWh)',
                                               'Min Price (MXN/MWh)', 'Price Std Dev']
                        price_stats['Price Spread (Max-Min)'] = (price_stats['Peak Price (MXN/MWh)'] - price_stats['Min Price (MXN/MWh)']).round(2)
                        price_stats.to_excel(writer, sheet_name='Price Statistics')

                    # Daily summary (only if fecha exists and is datetime)
                    if 'fecha' in df.columns and pd.api.types.is_datetime64_any_dtype(df['fecha']):
                        agg_map = {'demanda': ['mean', 'max', 'min', 'sum']}
                        if has_price and primary_price_col:
                            agg_map[primary_price_col] = ['mean', 'max', 'min']

                        daily_summary = df.groupby(df['fecha'].dt.date).agg(agg_map).round(2)
                        # Flatten columns for Excel readability
                        daily_summary.columns = [
                            ' '.join(str(part).replace('_', ' ').title() for part in col if part)
                            for col in daily_summary.columns
                        ]
                        daily_summary.to_excel(writer, sheet_name='Daily Summary')

                st.download_button(
                    label="⬇️ Download Excel Report",
                    data=excel_buffer.getvalue(),
                    file_name=f"cenace_report_{start_date}_{end_date}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            
            # Individual zone downloads
            st.markdown("### 📑 Download Individual Zones")
            
            # Ensure we have zones to select from
            if len(df['zona_carga'].unique()) > 0:
                zone_to_download = st.selectbox(
                    "Select Zone",
                    df['zona_carga'].unique(),
                    key="download_tab_zone_selectbox"
                )
                
                zone_df = df[df['zona_carga'] == zone_to_download]
                csv_buffer = io.StringIO()
                zone_df.to_csv(csv_buffer, index=False)
                
                st.download_button(
                    label=f"⬇️ Download {zone_to_download} Data",
                    data=csv_buffer.getvalue(),
                    file_name=f"cenace_{zone_to_download.replace(' ', '_')}_{start_date}_{end_date}.csv",
                    mime="text/csv"
                )
            else:
                st.warning("No zones available for download")
            
        else:
            st.info("📁 Download data first to access download options")
    
    with tab4:
        # Help Tab
        st.subheader("ℹ️ Help & Documentation")
        
        st.markdown("""
        ### 📚 User Guide
        
        **1. Understanding the Systems:**
        - **SIN** (Sistema Interconectado Nacional): Main grid covering most of Mexico
        - **BCA** (Baja California): Isolated grid in Baja California
        - **BCS** (Baja California Sur): Isolated grid in Baja California Sur
        
        **2. API Limitations:**
        - Maximum 7 days per request (handled automatically)
        - Maximum 10 zones per request
        - Data available with 1-day delay
        
        **3. Data Fields:**
        - `sistema`: Electric system (SIN/BCA/BCS)
        - `zona_carga`: Load zone name
        - `fecha`: Date
        - `hora`: Hour (1-24)
        - `demanda`: Demand in MW
        - `precio_total`: Zonal price in MXN/MWh
        - Additional `precio_*` columns for price components (when available)
        - `datetime`: Combined date and time
        
        **4. Caching:**
        - Data is cached for 24 hours to improve performance
        - Cache is based on zones + date range
        - Clear cache in Settings if you need fresh data
        
        **5. Best Practices:**
        - Download data in weekly chunks for better performance
        - Use the delay setting to avoid overwhelming the server
        - For large date ranges, consider downloading by system
        - Demand and price requests run together; allow extra time for large date ranges
        
        **6. Troubleshooting:**
        - **SSL Errors**: Disable SSL verification in Advanced Options
        - **Timeout Errors**: Increase retry attempts and delay
        - **No Data**: Check if date range is too recent (1-day delay)
        
        ### 🔗 Resources
        - [CENACE Official Website](https://www.cenace.gob.mx)
        - [API Documentation](https://www.cenace.gob.mx/SIM/VISTA/REPORTES/DemandaZonaCarga.aspx)
        
        ### 📧 Support
        For issues or questions, please check the documentation or contact support.
        """)

# Download logic
if download_button:
    st.session_state.download_complete = False
    
    # Create progress container
    progress_container = st.container()
    
    with progress_container:
        st.subheader("⬇️ Downloading Data...")
        
        # Initialize progress tracking
        progress_bar = st.progress(0)
        status_text = st.empty()
        detail_text = st.empty()
        
        try:
            # Initialize client and assembler
            client = CENACEClient(
                verify_ssl=verify_ssl,
                retry_attempts=retry_attempts,
                delay=delay_between_requests
            )
            
            assembler = DataAssembler()
            
            # Group zones by system for efficient downloading
            zones_by_system = {}
            for zone_info in parsed_zones:
                system = zone_info['system']
                zone = zone_info['zone']
                if system not in zones_by_system:
                    zones_by_system[system] = []
                zones_by_system[system].append(zone)
            
            # Calculate total operations for progress tracking
            total_operations = 0
            for system, zones in zones_by_system.items():
                num_batches = (len(zones) + 9) // 10  # Ceiling division for 10-zone batches
                num_weeks = ((end_date - start_date).days + 6) // 7  # Ceiling division for 7-day chunks
                total_operations += num_batches * num_weeks
            
            current_operation = 0
            all_data = []
            
            # Download data for each system
            for system, zones in zones_by_system.items():
                status_text.text(f"Processing system: {system}")
                
                # Download data in batches
                system_data = client.download_data(
                    system=system,
                    zones=zones,
                    start_date=start_date,
                    end_date=end_date,
                    process=process_type,
                    data_type="combined",
                    progress_callback=lambda current, total, msg: [
                        progress_bar.progress(min((current_operation + current) / total_operations, 1.0)),
                        detail_text.text(msg)
                    ]
                )
                
                if system_data:
                    all_data.extend(system_data)
                
                current_operation += len(zones) * ((end_date - start_date).days + 6) // 7
            
            # Assemble final dataframe
            status_text.text("Assembling merged demand & price dataset...")
            final_df = assembler.assemble_data(all_data)

            # Store in session state
            st.session_state.download_data = final_df
            st.session_state.merged_data = final_df
            st.session_state.download_complete = True

            # Increment refresh key to ensure widgets update
            st.session_state.data_refresh_key += 1
            
            # Clear progress indicators
            progress_bar.progress(1.0)
            status_text.text("✅ Download complete!")
            detail_text.text(
                f"Downloaded {len(final_df):,} hourly records with demand and prices across {len(zones_by_system)} systems"
            )
            
        except Exception as e:
            st.error(f"""
            ❌ **Download Failed**
            
            Error: {str(e)}
            
            **Troubleshooting:**
            1. Check your internet connection
            2. Try disabling SSL verification
            3. Reduce the date range or number of zones
            4. Increase retry attempts in Advanced Options
            """)
            status_text.text("❌ Download failed")
            detail_text.text(str(e))

# Show download complete message with a prominent refresh button (outside download handler)
# This ensures the button persists even after reruns
if st.session_state.get('download_complete', False):
    df = st.session_state.get('download_data', None)
    if df is not None and not df.empty and 'fecha' in df.columns and 'zona_carga' in df.columns:
        st.markdown("---")
        st.success(f"""
        ✅ **Download Complete!**
        - Records: {len(df):,}
        - Zones: {len(df['zona_carga'].unique())}
        - Includes hourly demand and zonal prices
        - Date Range: {df['fecha'].min().date()} to {df['fecha'].max().date()}
        """)
        
        # Create a visually prominent section for the button
        st.markdown("""
        <div style='text-align: center; padding: 20px; background-color: #e8f5e9; border-radius: 10px; margin: 20px 0; border: 2px solid #4caf50;'>
            <h3 style='color: #2e7d32; margin-bottom: 10px;'>🎯 Your Data is Ready!</h3>
            <p style='font-size: 16px; color: #388e3c; margin-bottom: 15px;'>Click the button below to view your data in the Dashboard</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Large, prominent button in the main content area
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            view_button = st.button(
                "📊 **View Data in Dashboard**", 
                key="view_data_btn", 
                use_container_width=True, 
                type="primary"
            )
            if view_button:
                # Scroll to top or switch tab - the data is already in session_state
                # The button click will trigger a rerun and tabs will show the data
                st.rerun()
        
        st.markdown("---")

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #888;'>
    <p>CENACE Demand Downloader v1.0 | Data provided by CENACE Mexico</p>
    <p>Built with Streamlit and ❤️</p>
</div>
""", unsafe_allow_html=True)
