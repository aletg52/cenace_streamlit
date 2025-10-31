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
if 'trigger_rerun' not in st.session_state:
    st.session_state.trigger_rerun = False

# Header
st.title("⚡ CENACE Demand Data Downloader")
st.markdown("### Download Mexico's electrical demand data from CENACE's web service")

# Sidebar for configuration
with st.sidebar:
    st.header("🔧 Configuration")
    
    # System and Zone Selection
    st.subheader("1️⃣ Select Zones")
    
    # Get all available zones
    all_zones = get_all_zones()
    
    # System filter
    systems = ["All"] + list(all_zones.keys())
    selected_system = st.selectbox(
        "Filter by System",
        systems,
        help="Filter zones by electrical system"
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
        help="MDA: Mercado del Día en Adelanto"
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
    st.subheader("4️⃣ Download Data")
    
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
        st.info(f"⏱️ Estimated time: {estimated_time}")
        download_disabled = False
    
    download_button = st.button(
        "🚀 Start Download",
        disabled=download_disabled,
        use_container_width=True,
        type="primary"
    )

# Main content area
# Show success message if download just completed (after rerun)
if st.session_state.download_complete and st.session_state.download_data is not None:
    df_check = st.session_state.download_data
    if not df_check.empty and 'fecha' in df_check.columns and 'zona_carga' in df_check.columns:
        st.success(f"""
        ✅ **Download Complete!**
        - Records: {len(df_check):,}
        - Zones: {len(df_check['zona_carga'].unique())}
        - Date Range: {df_check['fecha'].min().date()} to {df_check['fecha'].max().date()}
        """)
        st.balloons()

main_container = st.container()

with main_container:
    # Create tabs for different views
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Dashboard", "📈 Visualizations", "📁 Downloads", "ℹ️ Help"])
    
    with tab1:
        # Dashboard Tab
        df = st.session_state.download_data
        if df is None or (hasattr(df, 'empty') and df.empty):
            # Show instructions when no data
            st.markdown("""
            ### 👋 Welcome to CENACE Demand Downloader
            
            **Quick Start:**
            1. Select zones from the sidebar (up to 10)
            2. Choose your date range
            3. Click "Start Download"
            4. View and download your data
            
            **Features:**
            - ✅ Mix zones from different systems
            - ✅ Automatic 7-day chunking for API limits
            - ✅ Smart caching to avoid duplicate requests
            - ✅ Real-time progress tracking
            - ✅ Data preview and statistics
            - ✅ Multiple download formats
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
                
                # Statistics by zone
                st.subheader("📈 Zone Statistics")
                
                zone_stats = df.groupby('zona_carga').agg({
                    'demanda': ['mean', 'max', 'min', 'std'],
                    'fecha': 'count'
                }).round(2)
                
                zone_stats.columns = ['Avg Demand (MW)', 'Peak Demand (MW)', 
                                     'Min Demand (MW)', 'Std Dev', 'Records']
                zone_stats = zone_stats.sort_values('Peak Demand (MW)', ascending=False)
                
                st.dataframe(zone_stats, use_container_width=True)
                
                # Data preview
                st.subheader("🔍 Data Preview")
                
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
        # Visualizations Tab
        df = st.session_state.download_data
        if df is not None and not df.empty and 'zona_carga' in df.columns:
            
            st.subheader("📈 Data Visualizations")
            
            # Visualization selector
            viz_type = st.selectbox(
                "Select Visualization",
                ["Demand Time Series", "Daily Patterns", "Zone Comparison", 
                 "Heatmap", "Peak Analysis", "Weekday vs Weekend"]
            )
            
            if viz_type == "Demand Time Series":
                # Time series plot
                zone_to_plot = st.selectbox(
                    "Select Zone",
                    df['zona_carga'].unique()
                )
                
                zone_df = df[df['zona_carga'] == zone_to_plot].copy()
                
                fig = px.line(zone_df, x='datetime', y='demanda',
                            title=f"Demand Time Series - {zone_to_plot}",
                            labels={'demanda': 'Demand (MW)', 'datetime': 'Date/Time'})
                fig.update_layout(height=500)
                st.plotly_chart(fig, use_container_width=True)
                
            elif viz_type == "Daily Patterns":
                # Daily pattern analysis
                zone_to_analyze = st.selectbox(
                    "Select Zone",
                    df['zona_carga'].unique()
                )
                
                zone_df = df[df['zona_carga'] == zone_to_analyze].copy()
                zone_df['hour'] = zone_df['datetime'].dt.hour
                
                hourly_avg = zone_df.groupby('hour')['demanda'].agg(['mean', 'std']).reset_index()
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=hourly_avg['hour'],
                    y=hourly_avg['mean'],
                    mode='lines+markers',
                    name='Average',
                    line=dict(color='blue', width=3)
                ))
                fig.add_trace(go.Scatter(
                    x=hourly_avg['hour'],
                    y=hourly_avg['mean'] + hourly_avg['std'],
                    mode='lines',
                    name='Upper Bound',
                    line=dict(color='lightblue', dash='dash')
                ))
                fig.add_trace(go.Scatter(
                    x=hourly_avg['hour'],
                    y=hourly_avg['mean'] - hourly_avg['std'],
                    mode='lines',
                    name='Lower Bound',
                    line=dict(color='lightblue', dash='dash')
                ))
                
                fig.update_layout(
                    title=f"Daily Demand Pattern - {zone_to_analyze}",
                    xaxis_title="Hour of Day",
                    yaxis_title="Demand (MW)",
                    height=500
                )
                st.plotly_chart(fig, use_container_width=True)
                
            elif viz_type == "Zone Comparison":
                # Zone comparison box plot
                fig = px.box(df, x='zona_carga', y='demanda',
                           title="Demand Distribution by Zone",
                           labels={'demanda': 'Demand (MW)', 'zona_carga': 'Zone'})
                fig.update_layout(height=500)
                st.plotly_chart(fig, use_container_width=True)
                
            elif viz_type == "Heatmap":
                # Create hourly heatmap
                zone_for_heatmap = st.selectbox(
                    "Select Zone",
                    df['zona_carga'].unique()
                )
                
                zone_df = df[df['zona_carga'] == zone_for_heatmap].copy()
                zone_df['hour'] = zone_df['datetime'].dt.hour
                zone_df['date'] = zone_df['datetime'].dt.date
                
                pivot = zone_df.pivot_table(values='demanda', index='hour', columns='date', aggfunc='mean')
                
                fig = px.imshow(pivot,
                             labels=dict(x="Date", y="Hour", color="Demand (MW)"),
                             title=f"Demand Heatmap - {zone_for_heatmap}",
                             color_continuous_scale="RdYlGn_r",
                             aspect="auto")
                fig.update_layout(height=600)
                st.plotly_chart(fig, use_container_width=True)
                
            elif viz_type == "Peak Analysis":
                # Peak demand analysis
                daily_peaks = df.groupby([df['fecha'].dt.date, 'zona_carga'])['demanda'].max().reset_index()
                daily_peaks.columns = ['date', 'zona_carga', 'peak_demand']
                
                fig = px.line(daily_peaks, x='date', y='peak_demand', color='zona_carga',
                           title="Daily Peak Demand by Zone",
                           labels={'peak_demand': 'Peak Demand (MW)', 'date': 'Date'})
                fig.update_layout(height=500)
                st.plotly_chart(fig, use_container_width=True)
                
            elif viz_type == "Weekday vs Weekend":
                # Weekday vs Weekend analysis
                df['weekday'] = df['datetime'].dt.weekday
                df['is_weekend'] = df['weekday'].isin([5, 6])
                df['day_type'] = df['is_weekend'].map({True: 'Weekend', False: 'Weekday'})
                
                comparison = df.groupby(['zona_carga', 'day_type'])['demanda'].agg(['mean', 'max']).reset_index()
                
                fig = px.bar(comparison, x='zona_carga', y='mean', color='day_type',
                          barmode='group',
                          title="Weekday vs Weekend Average Demand",
                          labels={'mean': 'Average Demand (MW)', 'zona_carga': 'Zone'})
                fig.update_layout(height=500)
                st.plotly_chart(fig, use_container_width=True)
                
        else:
            st.info("📊 Download data first to see visualizations")
    
    with tab3:
        # Downloads Tab
        df = st.session_state.download_data
        if df is not None and not df.empty and 'zona_carga' in df.columns:
            
            st.subheader("📁 Download Options")
            
            # Prepare different download formats
            col1, col2, col3 = st.columns(3)
            
            with col1:
                # Combined CSV
                st.markdown("### 📄 Combined Data")
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
                    
                    # Zone statistics
                    zone_stats.to_excel(writer, sheet_name='Zone Statistics')
                    
                    # Daily summary
                    daily_summary = df.groupby(df['fecha'].dt.date).agg({
                        'demanda': ['mean', 'max', 'min', 'sum']
                    }).round(2)
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
            
            zone_to_download = st.selectbox(
                "Select Zone",
                df['zona_carga'].unique()
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
        - `datetime`: Combined date and time
        
        **4. Caching:**
        - Data is cached for 24 hours to improve performance
        - Cache is based on zones + date range
        - Clear cache in Settings if you need fresh data
        
        **5. Best Practices:**
        - Download data in weekly chunks for better performance
        - Use the delay setting to avoid overwhelming the server
        - For large date ranges, consider downloading by system
        
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
                    progress_callback=lambda current, total, msg: [
                        progress_bar.progress(min((current_operation + current) / total_operations, 1.0)),
                        detail_text.text(msg)
                    ]
                )
                
                if system_data:
                    all_data.extend(system_data)
                
                current_operation += len(zones) * ((end_date - start_date).days + 6) // 7
            
            # Assemble final dataframe
            status_text.text("Assembling final dataset...")
            final_df = assembler.assemble_data(all_data)
            
            # Store in session state FIRST - this is critical for rerun to see the data
            st.session_state.download_data = final_df
            st.session_state.download_complete = True
            
            # Clear progress indicators
            progress_bar.progress(1.0)
            status_text.text("✅ Download complete!")
            detail_text.text(f"Downloaded {len(final_df):,} records from {len(zones_by_system)} systems")
            
            # Force rerun IMMEDIATELY after storing data - before any UI messages
            # This ensures tabs refresh with new data
            st.rerun()
            
            # Note: The success message will show on the next rerun
            # We'll handle that in the main tab rendering
            
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

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #888;'>
    <p>CENACE Demand Downloader v1.0 | Data provided by CENACE Mexico</p>
    <p>Built with Streamlit and ❤️</p>
</div>
""", unsafe_allow_html=True)
