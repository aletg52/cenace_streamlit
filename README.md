# ⚡ CENACE Demand Downloader - Streamlit App

A modern web application for downloading Mexico's electrical demand data from CENACE's web service (SW-CAEZC).

## 🌟 Features

- **Multi-System Support**: Download data from SIN, BCA, and BCS electrical systems
- **Smart Zone Selection**: Mix zones from different systems (up to 10 zones per analysis)
- **Automatic API Handling**: 
  - Automatic 7-day window chunking
  - 10-zone batch processing
  - Smart caching to avoid duplicate requests
- **Real-Time Progress**: Track download progress with time estimates
- **Data Visualization**: Interactive charts and statistics
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
2. Or select custom dates (max 1 year range)
3. Note: CENACE data has a 1-day delay

### Step 3: Configure Settings (Optional)
- **Process Type**: MDA (Mercado del Día en Adelanto)
- **SSL Verification**: Disable if you encounter SSL errors
- **Retry Attempts**: Number of retries for failed requests
- **Request Delay**: Time between API calls (be respectful!)

### Step 4: Download Data
1. Click "Start Download"
2. Monitor progress in real-time
3. Data is automatically cached for 24 hours

### Step 5: Explore & Export
- **Dashboard**: View statistics and data preview
- **Visualizations**: Interactive charts and analysis
- **Downloads**: Export in multiple formats

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
cenace_downloader/
├── app_streamlit.py       # Main Streamlit UI
└── cenace_downloader/
    ├── __init__.py       # Package initialization
    ├── client.py         # API client with caching & retries
    ├── assembler.py      # Data processing & export
    ├── zones.py          # Zone definitions
    └── utils.py          # Utility functions
```

## ⚙️ API Limitations

- **Maximum 7 days per request**: Handled automatically by chunking
- **Maximum 10 zones per request**: Enforced in UI
- **Data delay**: 1-day delay in data availability
- **Rate limiting**: Configurable delay between requests

## 💾 Caching Strategy

The app uses smart caching to improve performance:
- **Cache Duration**: 24 hours
- **Cache Key**: Based on system + zones + date range
- **Location**: `~/.cenace_cache/`
- **Benefits**: Avoid duplicate API calls when adjusting parameters

To clear cache:
```python
from cenace_downloader import CENACEClient
client = CENACEClient()
client.clear_cache()
```

## 📈 Data Fields

| Field | Description | Type |
|-------|-------------|------|
| sistema | Electric system (SIN/BCA/BCS) | String |
| zona_carga | Load zone name | String |
| fecha | Date | Date |
| hora | Hour (1-24) | Integer |
| demanda | Demand in MW | Float |
| datetime | Combined date and time | Datetime |
| is_weekend | Weekend flag | Boolean |
| season | Season (Winter/Spring/Summer/Fall) | String |
| is_anomaly | Anomaly flag (>3 std dev) | Boolean |

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

### Memory Issues
- Download data in smaller chunks
- Clear cache periodically
- Restart the app

## 📝 License

This project is for educational and research purposes. CENACE data is publicly available through their web service.

## 🔗 Resources

- [CENACE Official Website](https://www.cenace.gob.mx)
- [CENACE Data Portal](https://www.cenace.gob.mx/SIM/VISTA/REPORTES/DemandaZonaCarga.aspx)

## 🤝 Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

## 📧 Support

For issues or questions, please check the documentation or create an issue on the project repository.

---

Built with ❤️ using Streamlit and Python
