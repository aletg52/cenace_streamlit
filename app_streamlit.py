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
    get_all_zones_with_regional,
    get_regional_controls_for_system,
    get_zones_for_regional_control,
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
    /* Progress bar styling */
    .stProgress > div > div > div > div {
        background-color: #00CC88;
    }
    
    /* Card styling */
    .stat-card {
        background-color: #ffffff;
        padding: 24px;
        border-radius: 12px;
        margin: 12px 0;
        border: 1px solid #e0e0e0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    
    /* Metric card enhancements */
    .metric-card {
        background-color: #ffffff;
        padding: 20px;
        border-radius: 8px;
        border-left: 4px solid #1f77b4;
        margin-bottom: 12px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    }
    
    /* Info box styling */
    .info-box {
        background-color: #f8f9fa;
        padding: 20px;
        border-radius: 8px;
        border-left: 4px solid #6366f1;
        margin: 16px 0;
    }
    
    /* Breadcrumb styling */
    .breadcrumb {
        font-size: 14px;
        color: #6b7280;
        margin-bottom: 16px;
        padding: 8px 0;
    }
    
    .breadcrumb a {
        color: #6366f1;
        text-decoration: none;
    }
    
    .breadcrumb a:hover {
        text-decoration: underline;
    }
    
    /* Quick action buttons */
    .quick-action-btn {
        padding: 12px 24px;
        border-radius: 8px;
        margin: 8px;
        text-align: center;
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        transition: all 0.2s;
    }
    
    .quick-action-btn:hover {
        border-color: #6366f1;
        box-shadow: 0 2px 8px rgba(99, 102, 241, 0.15);
    }
    
    /* Increase spacing */
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    
    /* Tab styling improvements */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    
    .stTabs [data-baseweb="tab"] {
        padding: 12px 20px;
        border-radius: 8px 8px 0 0;
    }
    
    /* Better data table spacing */
    .dataframe {
        font-size: 14px;
    }
    
    /* Description text styling */
    .description-text {
        color: #6b7280;
        font-size: 14px;
        line-height: 1.6;
        margin-top: 8px;
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
    
    # Get all available zones (flattened) and with regional control structure
    all_zones = get_all_zones()
    zones_with_regional = get_all_zones_with_regional()
    
    # System filter
    systems = ["All"] + list(all_zones.keys())
    
    # System filter - this widget naturally triggers reruns when changed
    selected_system = st.selectbox(
        "Filter by System",
        systems,
        help="Filter zones by electrical system",
        key="system_filter_selectbox"
    )
    
    # Regional Control filter (only shown if a specific system is selected)
    selected_regional_control = None
    if selected_system != "All":
        regional_controls = get_regional_controls_for_system(selected_system)
        if regional_controls:
            regional_options = ["All"] + regional_controls
            selected_regional_control = st.selectbox(
                "Filter by Regional Control",
                regional_options,
                help="Filter zones by regional control area",
                key="regional_control_filter_selectbox"
            )
            if selected_regional_control == "All":
                selected_regional_control = None
    
    # Prepare zone options based on system and regional control filters
    if selected_system == "All":
        zone_options = []
        for system, zones in all_zones.items():
            for zone in zones:
                zone_options.append(f"{zone} ({system})")
    else:
        if selected_regional_control:
            # Filter by specific regional control
            zones = get_zones_for_regional_control(selected_system, selected_regional_control)
            zone_options = [f"{zone} ({selected_system})" for zone in zones]
            st.caption(f"📍 Showing zones from {selected_regional_control} regional control")
        else:
            # Show all zones from the selected system
            zone_options = [f"{zone} ({selected_system})" for zone in all_zones[selected_system]]
            st.caption(f"📍 Showing all zones from {selected_system} system")
    
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

# Helper function for breadcrumb navigation
def render_breadcrumb(tab_name="Dashboard", subpage=None):
    """Render breadcrumb navigation"""
    breadcrumb_items = ["Dashboard"]
    if tab_name != "Dashboard":
        breadcrumb_items.append(tab_name)
    if subpage:
        breadcrumb_items.append(subpage)
    
    breadcrumb_html = " > ".join(breadcrumb_items)
    st.markdown(f'<div class="breadcrumb">{breadcrumb_html}</div>', unsafe_allow_html=True)


# Helper function for contextual information box
def render_info_box(title, content):
    """Render contextual information box"""
    with st.expander(f"ℹ️ {title}", expanded=False):
        st.markdown(content)

# Main content area
main_container = st.container()

with main_container:
    # Create tabs for different views
    tab_names = ["📊 Dashboard", "📈 Visualizations", "📁 Downloads", "ℹ️ Help"]
    
    # Create tabs (Streamlit doesn't support programmatic switching, but we can use session state hints)
    tabs = st.tabs(tab_names)
    
    tab1, tab2, tab3, tab4 = tabs
    
    with tab1:
        # Dashboard Tab
        render_breadcrumb("Dashboard")
        
        # Always read fresh from session state
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
            
            Access Mexico's electrical demand and zonal price data from CENACE's web services.
            """)
            
            # Step-by-step guide in boxes
            st.markdown("### 🚀 Quick Start Guide")
            
            # Create 5 boxes for the 5 steps
            step_col1, step_col2, step_col3, step_col4, step_col5 = st.columns(5)
            
            with step_col1:
                st.markdown("""
                <div style='background-color: #f8f9fa; padding: 16px; border-radius: 8px; border-left: 4px solid #1f77b4; margin-bottom: 16px; height: 100%;'>
                    <h4 style='margin-top: 0; color: #1f77b4; font-size: 16px;'>1️⃣ Select Zones</h4>
                    <p style='color: #6b7280; font-size: 13px; line-height: 1.6; margin-bottom: 0;'>
                        Choose up to 10 zones from SIN, BCA, or BCS systems. Filter by Regional Control for easier selection.
                    </p>
                </div>
                """, unsafe_allow_html=True)
            
            with step_col2:
                st.markdown("""
                <div style='background-color: #f8f9fa; padding: 16px; border-radius: 8px; border-left: 4px solid #6366f1; margin-bottom: 16px; height: 100%;'>
                    <h4 style='margin-top: 0; color: #6366f1; font-size: 16px;'>2️⃣ Choose Date Range</h4>
                    <p style='color: #6b7280; font-size: 13px; line-height: 1.6; margin-bottom: 0;'>
                        Use presets (Last 7/30 days) or select custom dates. Maximum 1 year range. Data has 1-day delay.
                    </p>
                </div>
                """, unsafe_allow_html=True)
            
            with step_col3:
                st.markdown("""
                <div style='background-color: #f8f9fa; padding: 16px; border-radius: 8px; border-left: 4px solid #10b981; margin-bottom: 16px; height: 100%;'>
                    <h4 style='margin-top: 0; color: #10b981; font-size: 16px;'>3️⃣ Configure Settings</h4>
                    <p style='color: #6b7280; font-size: 13px; line-height: 1.6; margin-bottom: 0;'>
                        Adjust SSL verification if needed. Set retry attempts and request delays (optional).
                    </p>
                </div>
                """, unsafe_allow_html=True)
            
            with step_col4:
                st.markdown("""
                <div style='background-color: #f8f9fa; padding: 16px; border-radius: 8px; border-left: 4px solid #f59e0b; margin-bottom: 16px; height: 100%;'>
                    <h4 style='margin-top: 0; color: #f59e0b; font-size: 16px;'>4️⃣ Download Data</h4>
                    <p style='color: #6b7280; font-size: 13px; line-height: 1.6; margin-bottom: 0;'>
                        Click "Start Download" to retrieve demand and prices. Progress tracked in real-time. Data cached for 24 hours.
                    </p>
                </div>
                """, unsafe_allow_html=True)
            
            with step_col5:
                st.markdown("""
                <div style='background-color: #f8f9fa; padding: 16px; border-radius: 8px; border-left: 4px solid #ef4444; margin-bottom: 16px; height: 100%;'>
                    <h4 style='margin-top: 0; color: #ef4444; font-size: 16px;'>5️⃣ Explore & Analyze</h4>
                    <p style='color: #6b7280; font-size: 13px; line-height: 1.6; margin-bottom: 0;'>
                        View statistics in Dashboard, create visualizations, and export data in multiple formats.
                    </p>
                </div>
                """, unsafe_allow_html=True)
            
            st.markdown("---")
            
            # Show system information at same level as Quick Start
            st.markdown("### 📍 Available Systems and Zones")
            
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
                # Contextual information about the dashboard
                render_info_box("About This Data", """
                This dashboard shows your downloaded CENACE electrical demand and zonal price data.
                
                **What you're seeing:**
                - **Demand Data**: Hourly electrical demand in megawatts (MW) for each zone
                - **Price Data**: Zonal electricity prices in Mexican Pesos per megawatt-hour (MXN/MWh)
                - **Merged Dataset**: Demand and price data are automatically combined by zone, date, and hour
                
                **Data Structure:**
                - Each record represents one hour of data for one zone
                - Demand values show actual power consumption
                - Price values include total price and components (energy, losses, congestion)
                - Data spans the date range you selected during download
                
                **What you can do:**
                - View summary statistics for all zones
                - Filter and preview specific data points
                - Export data in multiple formats (see Downloads tab)
                - Analyze trends and patterns (see Visualizations tab)
                """)
                
                st.subheader("📊 Data Overview")

                price_columns = [col for col in df.columns if col.startswith('precio')]
                primary_price_col = 'precio_total' if 'precio_total' in df.columns else (price_columns[0] if price_columns else None)
                price_series = df[primary_price_col].dropna() if primary_price_col else pd.Series(dtype=float)
                has_price = not price_series.empty

                # Key metrics - enhanced card style
                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    st.metric(
                        "Total Records",
                        f"{len(df):,}",
                        help="Total number of hourly records in your dataset"
                    )
                    st.caption("Hourly data points")
                with col2:
                    date_range_str = f"{df['fecha'].min().date()} to {df['fecha'].max().date()}"
                    days = (df['fecha'].max() - df['fecha'].min()).days + 1
                    st.metric("Date Range", date_range_str)
                    st.caption(f"{days} days of data")
                with col3:
                    st.metric(
                        "Zones",
                        len(df['zona_carga'].unique()),
                        help="Number of different load zones in your dataset"
                    )
                    st.caption("Unique zones")
                with col4:
                    st.metric(
                        "Systems",
                        len(df['sistema'].unique()),
                        help="Number of electrical systems (SIN, BCA, BCS)"
                    )
                    st.caption("Electrical systems")

                if has_price:
                    col5, col6, col7 = st.columns(3)
                    avg_price = price_series.mean()
                    max_price = price_series.max()
                    min_price = price_series.min()
                    price_spread = max_price - min_price

                    with col5:
                        st.metric(
                            "Average Price",
                            f"{avg_price:,.2f} MXN/MWh",
                            help="Mean zonal price across all zones and hours"
                        )
                        st.caption("Mean price per MWh")
                    with col6:
                        st.metric(
                            "Peak Price",
                            f"{max_price:,.2f} MXN/MWh",
                            help="Highest zonal price in your dataset"
                        )
                        st.caption("Maximum price observed")
                    with col7:
                        st.metric(
                            "Price Spread",
                            f"{price_spread:,.2f} MXN/MWh",
                            help="Difference between highest and lowest prices"
                        )
                        st.caption("Price range")
                
                # Data Quality Indicators
                st.markdown("---")
                st.subheader("📊 Data Quality Indicators")
                
                # Calculate data completeness (24 hours per day)
                unique_zones_count = len(df['zona_carga'].unique())
                date_range = pd.date_range(df['fecha'].min(), df['fecha'].max(), freq='D')
                total_expected_records = unique_zones_count * len(date_range) * 24
                actual_records = len(df)
                completeness_pct = (actual_records / total_expected_records * 100) if total_expected_records > 0 else 100
                
                # Check for missing demand data
                demand_completeness = (1 - df['demanda'].isna().sum() / len(df)) * 100
                
                # Check for missing price data
                price_completeness = (1 - df[primary_price_col].isna().sum() / len(df)) * 100 if has_price else 0
                
                quality_col1, quality_col2, quality_col3, quality_col4 = st.columns(4)
                
                with quality_col1:
                    st.metric(
                        "Records Coverage",
                        f"{completeness_pct:.1f}%",
                        help="Percentage of expected hourly records present"
                    )
                    st.caption(f"{actual_records:,} / ~{total_expected_records:,}")
                
                with quality_col2:
                    st.metric(
                        "Demand Data",
                        f"{demand_completeness:.1f}%",
                        help="Percentage of records with demand values"
                    )
                    st.caption(f"{df['demanda'].notna().sum():,} records")
                
                with quality_col3:
                    if has_price:
                        st.metric(
                            "Price Data",
                            f"{price_completeness:.1f}%",
                            help="Percentage of records with price values"
                        )
                        st.caption(f"{df[primary_price_col].notna().sum():,} records")
                    else:
                        st.metric("Price Data", "N/A")
                        st.caption("No price data available")
                
                with quality_col4:
                    zones_with_full_data = len(df[df['demanda'].notna()].groupby('zona_carga'))
                    total_zones = len(df['zona_carga'].unique())
                    st.metric(
                        "Zones with Data",
                        f"{zones_with_full_data} / {total_zones}",
                        help="Number of zones with complete demand data"
                    )
                    st.caption(f"{zones_with_full_data / total_zones * 100:.0f}% coverage")
                
                # Statistics by zone
                st.markdown("---")
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
                
                # Data preview with better organization
                st.markdown("---")
                st.subheader("🔍 Data Preview")
                
                # Summary stats above preview
                preview_summary_col1, preview_summary_col2, preview_summary_col3 = st.columns(3)
                with preview_summary_col1:
                    st.metric("Total Records", f"{len(df):,}")
                with preview_summary_col2:
                    unique_dates = len(df['fecha'].unique())
                    st.metric("Unique Dates", f"{unique_dates}")
                with preview_summary_col3:
                    unique_zones = len(df['zona_carga'].unique())
                    st.metric("Unique Zones", f"{unique_zones}")
                
                st.caption("Preview includes merged demand and price data. Use filters to focus on a specific zone or date range.")

                # Add filters for preview
                preview_filter_col1, preview_filter_col2, preview_filter_col3 = st.columns(3)
                with preview_filter_col1:
                    preview_zone = st.selectbox(
                        "Filter by Zone",
                        ["All"] + sorted(list(df['zona_carga'].unique())),
                        key="preview_zone_selectbox",
                        help="Select a specific zone to preview"
                    )
                with preview_filter_col2:
                    preview_date = st.selectbox(
                        "Filter by Date",
                        ["All"] + sorted([str(d.date()) for d in df['fecha'].unique()]),
                        key="preview_date_selectbox",
                        help="Select a specific date to preview"
                    )
                with preview_filter_col3:
                    preview_limit = st.number_input(
                        "Number of rows",
                        min_value=10,
                        max_value=1000,
                        value=100,
                        step=10,
                        help="Maximum number of rows to display"
                    )
                
                # Apply preview filters
                preview_df = df.copy()
                if preview_zone != "All":
                    preview_df = preview_df[preview_df['zona_carga'] == preview_zone]
                if preview_date != "All":
                    preview_df = preview_df[preview_df['fecha'].astype(str).str.startswith(preview_date)]
                
                # Show filtered preview
                if len(preview_df) > 0:
                    st.dataframe(preview_df.head(preview_limit), use_container_width=True, height=400)
                    if len(preview_df) > preview_limit:
                        st.caption(f"Showing first {preview_limit} of {len(preview_df):,} filtered records")
                else:
                    st.info("No records match the selected filters. Try different zone or date selection.")
    
    with tab2:
        # Visualizations Tab
        render_breadcrumb("Visualizations")
        
        # Always get fresh data from session state
        df = st.session_state.get('download_data', None)
        # Check for all required columns including 'fecha' and 'datetime'
        has_valid_data = (df is not None and 
                         hasattr(df, 'empty') and 
                         not df.empty and
                         'zona_carga' in df.columns and
                         'fecha' in df.columns and
                         'datetime' in df.columns)
        
        if has_valid_data:
            # Contextual information about visualizations
            render_info_box("About Visualizations", """
            Interactive charts help you understand patterns and trends in your CENACE data.
            
            **Available Visualizations:**
            - **Time Series**: See how demand and prices change over time
            - **Daily Patterns**: Understand hourly patterns within a typical day
            - **Zone Comparison**: Compare metrics across different zones
            - **Heatmaps**: Spot patterns by hour and date
            - **Weekday vs Weekend**: Compare different day types
            
            **Tips:**
            - Use zoom and pan to focus on specific time periods
            - Hover over data points to see exact values
            - Toggle legend items to show/hide data series
            """)

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
                 "Heatmap", "Weekday vs Weekend"],
                key="viz_type_selectbox",
                help="Choose the type of analysis you want to perform"
            )
            
            render_breadcrumb("Visualizations", viz_type)

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
                        mode='lines',
                        name='Price (MXN/MWh)',
                        line=dict(color='#ff7f0e', width=2),
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
                        mode='lines',
                        name='Average Price (MXN/MWh)',
                        line=dict(color='#ff7f0e', width=2),
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
                        subset = comparison[comparison['day_type'] == day_type].sort_values('zona_carga')
                        subset = subset.dropna(subset=[primary_price_col])
                        if subset.empty:
                            continue
                        fig.add_trace(go.Scatter(
                            x=subset['zona_carga'],
                            y=subset[primary_price_col],
                            mode='lines+markers',
                            name=f"{day_type} Price",
                            line=dict(width=2, color='#ff7f0e', dash='dash' if day_type == 'Weekend' else 'solid'),
                            marker=dict(size=8, symbol='diamond' if day_type == 'Weekend' else 'circle'),
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
        # Downloads Tab
        render_breadcrumb("Downloads")
        
        # Always get fresh data from session state
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
            # Contextual information about downloads
            render_info_box("About Downloads", """
            Export your data in multiple formats for further analysis.
            
            **Available Formats:**
            - **CSV**: Combined dataset with all zones (best for Excel, Python, R)
            - **ZIP**: Individual CSV files per zone (organized by zone name)
            - **Excel**: Multi-sheet workbook with raw data, statistics, and summaries
            
            **What's Included:**
            - All hourly records with demand and price data
            - System, zone, date, and time information
            - Price components (energy, losses, congestion) when available
            - Derived fields (datetime, is_weekend, season)
            
            **File Naming:**
            Files are automatically named with date ranges for easy organization.
            """)

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
        render_breadcrumb("Help")
        st.subheader("ℹ️ Help & Documentation")
        
        # Organized help sections with tabs or expanders
        help_sections = st.tabs(["📖 Getting Started", "📊 Understanding Data", "⚙️ Technical Details", "🔧 Troubleshooting"])
        
        with help_sections[0]:
            st.markdown("### 🚀 Quick Start Guide")
            st.markdown("""
            **Step 1: Select Zones**
            - Use the sidebar to select up to 10 zones
            - Filter by System (SIN, BCA, BCS) for easier selection
            - Use Regional Control filter for SIN zones to narrow down options
            - Mix zones from different systems if needed
            
            **Step 2: Choose Date Range**
            - Use presets: Last 7 Days, Last 30 Days, Current Month
            - Or select custom dates (max 1 year)
            - Remember: CENACE data has a 1-day delay
            
            **Step 3: Download Data**
            - Click "Start Download" in the sidebar
            - Monitor progress in real-time
            - Wait for completion (usually 1-5 minutes depending on range)
            
            **Step 4: Explore Your Data**
            - **Dashboard Tab**: View summary statistics and data quality
            - **Visualizations Tab**: Create interactive charts and graphs
            - **Downloads Tab**: Export data in CSV, Excel, or ZIP formats
            """)
            
            st.markdown("### 💡 Pro Tips")
            st.markdown("""
            - Start with 1-2 zones to familiarize yourself with the interface
            - Use Regional Control filter when selecting SIN zones (makes selection easier)
            - Download data in smaller chunks for faster results
            - Check the Data Quality Indicators to understand data completeness
            - Use the "About This Data" expandable sections for context
            """)
        
        with help_sections[1]:
            st.markdown("### 📊 Understanding Your Data")
            
            st.markdown("""
            #### What is Demand Data?
            Demand data represents the actual electrical power consumption in megawatts (MW) for each zone.
            - Measured hourly (24 hours per day)
            - Shows real power consumption patterns
            - Useful for understanding consumption trends
            
            #### What is Price Data?
            Price data represents the zonal electricity prices in Mexican Pesos per megawatt-hour (MXN/MWh).
            - Includes total price (`precio_total`)
            - Breakdown into components:
              - Energy component (`componente_energia`)
              - Losses component (`componente_perdidas`)
              - Congestion component (`componente_congestion`)
            - Shows market dynamics and price volatility
            
            #### Understanding Data Structure
            Each record in your dataset represents:
            - One hour of data for one zone
            - Date and time information
            - Demand value (MW)
            - Price values (MXN/MWh) when available
            
            Data is automatically merged by zone, date, and hour. If price data is missing for a particular
            hour/zone combination, price fields will show as `NaN`.
            """)
            
            st.markdown("### 📈 Data Fields Reference")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("""
                **Core Fields:**
                - `sistema`: Electric system (SIN/BCA/BCS)
                - `zona_carga`: Load zone name
                - `fecha`: Date
                - `hora`: Hour (1-24)
                - `datetime`: Combined date and time
                
                **Demand Fields:**
                - `demanda`: Demand in MW
                """)
            
            with col2:
                st.markdown("""
                **Price Fields:**
                - `precio_total`: Total zonal price (MXN/MWh)
                - `componente_energia`: Energy component
                - `componente_perdidas`: Losses component
                - `componente_congestion`: Congestion component
                
                **Derived Fields:**
                - `is_weekend`: Weekend flag
                - `season`: Season classification
                """)
        
        with help_sections[2]:
            st.markdown("### ⚙️ Technical Details")
            
            st.markdown("""
            #### Electrical Systems
            
            **SIN** (Sistema Interconectado Nacional)
            - Main national grid covering most of Mexico
            - 100+ zones organized by Regional Controls
            - Regional Controls: Central, Noreste, Noroeste, Norte, Occidental, Oriental, Peninsular
            
            **BCA** (Baja California)
            - Isolated grid serving Baja California
            - 4 zones: Ensenada, Mexicali, San Luis, Tijuana
            
            **BCS** (Baja California Sur)
            - Isolated grid serving Baja California Sur
            - 3 zones: Constitucion, La Paz, Los Cabos
            
            #### API Limitations
            - **Maximum 7 days per request**: Automatically handled by chunking
            - **Maximum 10 zones per request**: Enforced in the UI
            - **Data delay**: 1-day delay in data availability
            - **Dual API calls**: Each download requires calls to both SW-CAEZC (demand) and SW-PEND (price) APIs
            
            #### Caching Strategy
            - Data cached for 24 hours
            - Cache key based on: system + zones + date range + data type
            - Demand and price data cached separately for efficiency
            - Cache location: `~/.cenace_cache/`
            
            #### Data Quality
            Check the Data Quality Indicators in the Dashboard to see:
            - Records coverage percentage
            - Demand data completeness
            - Price data completeness
            - Zones with complete data
            """)
        
        with help_sections[3]:
            st.markdown("### 🔧 Troubleshooting Guide")
            
            st.markdown("""
            #### Common Issues and Solutions
            
            **SSL Certificate Errors**
            - **Solution**: Disable SSL verification in Advanced Options
            - CENACE's SSL certificate often has issues
            - This is safe for data download purposes
            
            **Timeout Errors**
            - Increase retry attempts (Advanced Options)
            - Increase delay between requests
            - Try smaller date ranges first
            - Check your internet connection
            
            **No Data Returned**
            - Check date range (must be at least 1 day in the past)
            - Verify zone names are correct
            - Ensure both APIs (SW-CAEZC and SW-PEND) are accessible
            - Check internet connection
            
            **No Price Data**
            - Price data may not be available for all zones/dates
            - Check that SW-PEND API is responding correctly
            - Verify date range (price data might have different availability)
            - Some zones may not have price data for certain periods
            
            **Download Takes Too Long**
            - Reduce number of zones (API limit: 10 zones max)
            - Use smaller date ranges
            - Increase delay between requests (slower but more reliable)
            - Check network connection speed
            
            **Memory Issues**
            - Download data in smaller chunks
            - Clear cache periodically
            - Restart the application
            - Reduce date range or number of zones
            """)
            
            st.markdown("### 🔗 Additional Resources")
            st.markdown("""
            - [CENACE Official Website](https://www.cenace.gob.mx)
            - [CENACE Data Portal](https://www.cenace.gob.mx/SIM/VISTA/REPORTES/DemandaZonaCarga.aspx)
            
            For technical issues or questions, please refer to the project repository.
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

# Show download complete message with quick action buttons (outside download handler)
# This ensures the buttons persist even after reruns
if st.session_state.get('download_complete', False):
    df = st.session_state.get('download_data', None)
    if df is not None and not df.empty and 'fecha' in df.columns and 'zona_carga' in df.columns:
        st.markdown("---")
        
        # Success message in prominent card
        st.markdown("""
        <div style='background-color: #e8f5e9; padding: 24px; border-radius: 12px; margin: 20px 0; border-left: 4px solid #4caf50;'>
            <h2 style='color: #2e7d32; margin-top: 0; margin-bottom: 12px;'>✅ Download Complete!</h2>
            <p style='color: #388e3c; font-size: 16px; margin-bottom: 8px;'><strong>{records:,}</strong> records downloaded</p>
            <p style='color: #388e3c; font-size: 14px; margin-bottom: 0;'>
                <strong>{zones}</strong> zones • <strong>{date_range}</strong> • Includes demand & price data
            </p>
        </div>
        """.format(
            records=len(df),
            zones=len(df['zona_carga'].unique()),
            date_range=f"{df['fecha'].min().date()} to {df['fecha'].max().date()}"
        ), unsafe_allow_html=True)
        
        # Button to load and view the data
        st.markdown("### 📊 View Your Data")
        st.markdown("Click the button below to load and view your downloaded data in the Dashboard tab.")
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("🔄 Load Data in Dashboard", use_container_width=True, type="primary", key="load_data_button"):
                # Increment refresh key to trigger data reload
                st.session_state.data_refresh_key = st.session_state.get('data_refresh_key', 0) + 1
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
