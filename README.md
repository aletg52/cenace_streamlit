# ⚡ CENACE Demand & Price Downloader - Streamlit App

A modern web application for downloading Mexico's electrical demand and zonal price data from CENACE's web services (SW-CAEZC for demand and SW-PEND for prices).

## 🌟 Features

- **Dual API Support**: Download both demand data (SW-CAEZC) and zonal prices (SW-PEND) simultaneously
- **Multi-System Support**: Download data from SIN, BCA, and BCS electrical systems
- **Smart Zone Selection**: Mix zones from different systems (up to 10 zones per analysis)
- **Automatic API Handling**: 
  - Automatic 7-day window chunking
  - 10-zone batch processing
  - Smart caching to avoid duplicate requests
  - Automatic data merging of demand and price records
- **Real-Time Progress**: Track download progress with time estimates for combined downloads
- **Comprehensive Data Visualization**: 
  - Interactive line graphs for time series analysis
  - Daily pattern analysis with demand and price trends
  - Zone comparison visualizations
  - Heatmaps for demand and price patterns
  - Peak analysis with dual-axis charts
  - Weekday vs weekend comparisons
- **Price Statistics**: 
  - Average, peak, and spread metrics
  - Price component breakdown (energy, losses, congestion)
  - Zone-level price analysis
- **Multiple Export Formats**: CSV, Excel, ZIP with individual files
- **Data Quality**: Automatic validation and anomaly detection

## 📋 Requirements

- Python 3.8 or higher
- Internet connection for API access
- ~100MB disk space for cache

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Run the Application

```bash
streamlit run app_streamlit.py
```

The app will open in your browser at `http://localhost:8501`

### 3. Alternative: Run with Custom Port

```bash
streamlit run app_streamlit.py --server.port 8080
```

## 📖 User Guide

### Step 1: Select Zones
1. Choose a system filter or select "All" to see zones from all systems
2. Use "Select All" to quickly select the first 10 zones
3. Or manually select up to 10 zones from the dropdown

### Step 2: Choose Date Range
1. Use preset options (Last 7/30 days, Current Month)
2. Or select custom dates (no limit)
3. Note: CENACE data has a 1-day delay

### Step 3: Configure Settings (Optional)
- **Process Type**: MDA (Mercado del Día en Adelanto)
- **SSL Verification**: Disable if you encounter SSL errors
- **Retry Attempts**: Number of retries for failed requests
- **Request Delay**: Time between API calls (be respectful!)

### Step 4: Download Data
1. Click "Start Download"
2. Monitor progress in real-time (downloads both demand and price data)
3. Data is automatically cached for 24 hours
4. Demand and price data are automatically merged by zone, date, and hour

### Step 5: Explore & Export
- **Dashboard**: View statistics, price metrics, and data preview
  - Key metrics for demand and prices
  - Zone-level statistics with price averages
  - Interactive data preview with filters
- **Visualizations**: Interactive line graphs and charts
  - Demand & Price Time Series (line graphs)
  - Daily Patterns with hourly averages
  - Zone Comparison with box plots and price overlays
  - Heatmaps for demand and price patterns
  - Peak Analysis with dual-axis charts
  - Weekday vs Weekend comparisons
- **Downloads**: Export in multiple formats (includes both demand and price fields)

## 📊 Available Systems & Zones

### BCA (Baja California) - 4 zones
- ENSENADA
- MEXICALI
- SAN LUIS
- TIJUANA

### BCS (Baja California Sur) - 3 zones
- CONSTITUCION
- LA PAZ
- LOS CABOS

### SIN (Sistema Interconectado Nacional) - 100+ zones
Covers most of Mexico with major cities and regions

## 🏗️ Architecture

```
cenace_streamlit/
├── app_streamlit.py          # Main Streamlit UI with visualizations
├── run_app.py               # Application launcher
├── requirements.txt         # Python dependencies
├── README.md               # This file
└── cenace_downloader/
    ├── __init__.py         # Package initialization
    ├── client.py           # API client with caching & retries
    │                         # - Handles SW-CAEZC (demand) API
    │                         # - Handles SW-PEND (price) API
    │                         # - XML parsing for both endpoints
    │                         # - Automatic data merging
    ├── assembler.py        # Data processing & export
    ├── zones.py            # Zone definitions for all systems
    └── utils.py            # Utility functions (time estimation, etc.)
```

### Key Components

- **client.py**: 
  - `CENACEClient`: Main API client handling both demand and price APIs
  - Automatic chunking and batching
  - XML parsing with support for SW-PEND price fields (`pz`, `pz_ene`, `pz_per`, `pz_cng`)
  - Data merging logic

- **assembler.py**:
  - `DataAssembler`: Processes and transforms raw API data
  - Creates datetime columns
  - Handles missing values
  - Prepares data for export

- **app_streamlit.py**:
  - Complete Streamlit UI with tabs
  - Dashboard with statistics
  - Interactive visualizations using Plotly
  - Multiple export formats

## ⚙️ API Limitations

- **Maximum 7 days per request**: Handled automatically by chunking
- **Maximum 10 zones per request**: Enforced in UI
- **Data delay**: 1-day delay in data availability
- **Rate limiting**: Configurable delay between requests
- **Dual API calls**: Each request requires calls to both SW-CAEZC (demand) and SW-PEND (price) APIs

## 📡 API Endpoints

The application uses two CENACE web services:
- **SW-CAEZC**: Demand data API (returns XML format)
- **SW-PEND**: Zonal price data API (returns XML format with price fields: `pz`, `pz_ene`, `pz_per`, `pz_cng`)

Both APIs are called automatically when downloading "combined" data type, and results are merged based on system, zone, date, and hour.

## 💾 Caching Strategy

The app uses smart caching to improve performance:
- **Cache Duration**: 24 hours
- **Cache Key**: Based on system + zones + date range + data type (demand/price/combined)
- **Location**: `~/.cenace_cache/`
- **Benefits**: Avoid duplicate API calls when adjusting parameters
- **Separate Caching**: Demand and price data are cached separately for efficient retrieval

To clear cache:
```python
from cenace_downloader import CENACEClient
client = CENACEClient()
client.clear_cache()
```

To check cache info:
```python
cache_info = client.get_cache_info()
print(f"Cache files: {cache_info['num_files']}")
print(f"Cache size: {cache_info['total_size_mb']} MB")
```

## 📈 Data Fields

### Core Fields
| Field | Description | Type |
|-------|-------------|------|
| sistema | Electric system (SIN/BCA/BCS) | String |
| zona_carga | Load zone name | String |
| fecha | Date | Date |
| hora | Hour (1-24) | Integer |
| datetime | Combined date and time | Datetime |

### Demand Fields (from SW-CAEZC)
| Field | Description | Type |
|-------|-------------|------|
| demanda | Demand in MW | Float |

### Price Fields (from SW-PEND)
| Field | Description | Type |
|-------|-------------|------|
| precio_total | Total zonal price in MXN/MWh (from `pz` field) | Float |
| componente_energia | Energy component price (from `pz_ene`) | Float |
| componente_perdidas | Losses component price (from `pz_per`) | Float |
| componente_congestion | Congestion component price (from `pz_cng`) | Float |

### Derived Fields
| Field | Description | Type |
|-------|-------------|------|
| is_weekend | Weekend flag | Boolean |
| season | Season (Winter/Spring/Summer/Fall) | String |
| is_anomaly | Anomaly flag (>3 std dev) | Boolean |

**Note**: When downloading "combined" data type, all fields are included. Price fields may be `NaN` if price data is not available for that zone/date/hour combination.

## 🐛 Troubleshooting

### SSL Certificate Error
```python
# In Advanced Options, uncheck "Verify SSL Certificate"
```

### Timeout Errors
- Increase retry attempts in Advanced Options
- Increase delay between requests
- Try smaller date ranges

### No Data Returned
- Check date range (must be at least 1 day in the past)
- Verify zone names are correct
- Check internet connection
- Ensure both demand and price APIs are accessible (SW-CAEZC and SW-PEND)

### No Price Data
- Price data may not be available for all zones/dates
- Check that SW-PEND API is responding correctly
- Verify that price fields (`pz`, `pz_ene`, etc.) are present in API response
- Check logs for XML parsing errors

### Memory Issues
- Download data in smaller chunks
- Clear cache periodically
- Restart the app

## 📝 License

This project is for educational and research purposes. CENACE data is publicly available through their web service.

## 🔗 Resources

- [CENACE Official Website](https://www.cenace.gob.mx)
- [CENACE Data Portal](https://www.cenace.gob.mx/SIM/VISTA/REPORTES/DemandaZonaCarga.aspx)
- [CENACE API Documentation](https://www.cenace.gob.mx/SIM/VISTA/REPORTES/DemandaZonaCarga.aspx)

## 🎨 Visualization Features

The application includes comprehensive data visualization capabilities:

- **Time Series Charts**: Line graphs showing demand and price trends over time
- **Daily Patterns**: Hourly average demand and price patterns with standard deviation bands
- **Zone Comparison**: Box plots for demand distribution with price overlays
- **Heatmaps**: Visual patterns of demand and price by hour and date
- **Peak Analysis**: Daily peak demand and price tracking across zones
- **Weekday vs Weekend**: Comparison analysis with dual-axis charts

All visualizations support:
- Interactive zooming and panning
- Legend toggling
- Dual-axis display for demand (left) and price (right)
- Exportable as images

## 🤝 Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

## 📧 Support

For issues or questions, please check the documentation or create an issue on the project repository.

---

Built with ❤️ using Streamlit and Python
