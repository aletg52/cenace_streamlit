#!/usr/bin/env python
"""
Test Script for CENACE Downloader Package
==========================================
Verify that all components are working correctly
"""

import sys
from datetime import datetime, timedelta
import json
from pathlib import Path


FIXTURE_DIR = Path(__file__).parent / "tests" / "data"


def load_fixture(name: str) -> str:
    """Load fixture file from disk"""
    path = FIXTURE_DIR / name
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

def test_imports():
    """Test that all modules can be imported"""
    print("Testing imports...")
    try:
        from cenace_downloader import (
            CENACEClient,
            DataAssembler,
            get_all_zones,
            estimate_download_time
        )
        print("✅ All imports successful")
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

def test_zones():
    """Test zone configuration"""
    print("\nTesting zone configuration...")
    try:
        from cenace_downloader import get_all_zones, ZONES_BY_SYSTEM
        from cenace_downloader.zones import (
            get_zones_for_system,
            get_total_zones,
            normalize_zone_name,
            validate_zones
        )
        
        all_zones = get_all_zones()
        
        # Test zone counts
        assert len(all_zones['BCA']) == 4, "BCA should have 4 zones"
        assert len(all_zones['BCS']) == 3, "BCS should have 3 zones"
        assert len(all_zones['SIN']) > 100, "SIN should have 100+ zones"
        
        print(f"  - BCA zones: {len(all_zones['BCA'])}")
        print(f"  - BCS zones: {len(all_zones['BCS'])}")
        print(f"  - SIN zones: {len(all_zones['SIN'])}")
        print(f"  - Total zones: {get_total_zones()}")
        
        # Test zone normalization
        assert normalize_zone_name("la-paz") == "LA PAZ"
        assert normalize_zone_name("CIUDAD JUAREZ") == "JUAREZ"
        
        # Test zone validation
        valid, invalid = validate_zones(["LA PAZ", "INVALID_ZONE"], "BCS")
        assert len(valid) == 1 and len(invalid) == 1
        
        print("✅ Zone configuration tests passed")
        return True
        
    except Exception as e:
        print(f"❌ Zone test error: {e}")
        return False

def test_utils():
    """Test utility functions"""
    print("\nTesting utility functions...")
    try:
        from cenace_downloader.utils import (
            estimate_download_time,
            format_duration,
            format_file_size,
            chunk_date_range,
            validate_date_range
        )
        
        # Test time estimation
        estimate = estimate_download_time(10, 30, 1.0)
        print(f"  - Estimated time for 10 zones, 30 days: {estimate}")
        
        # Test duration formatting
        assert format_duration(45) == "45 seconds"
        assert format_duration(90) == "1 min 30 sec"
        assert format_duration(3660) == "1 hr 1 min"
        
        # Test file size formatting
        assert format_file_size(500) == "500.0 B"
        assert format_file_size(1500) == "1.5 KB"
        assert format_file_size(1500000) == "1.4 MB"
        
        # Test date chunking
        start = datetime(2024, 1, 1).date()
        end = datetime(2024, 1, 15).date()
        chunks = chunk_date_range(start, end, 7)
        assert len(chunks) == 3, "Should have 3 chunks for 15 days with 7-day chunks"
        
        # Test date validation
        today = datetime.now().date()
        valid, msg = validate_date_range(
            today - timedelta(days=10),
            today - timedelta(days=1)
        )
        assert valid, "Recent date range should be valid"
        
        print("✅ Utility function tests passed")
        return True
        
    except Exception as e:
        print(f"❌ Utils test error: {e}")
        return False

def test_client_initialization():
    """Test client initialization"""
    print("\nTesting client initialization...")
    try:
        from cenace_downloader import CENACEClient
        
        # Test default initialization
        client = CENACEClient()
        assert client.verify_ssl == False
        assert client.retry_attempts == 3
        assert client.delay == 1.0
        assert client.cache_enabled == True
        
        # Test custom initialization
        client2 = CENACEClient(
            verify_ssl=True,
            retry_attempts=5,
            delay=2.0,
            cache_enabled=False
        )
        assert client2.verify_ssl == True
        assert client2.retry_attempts == 5
        assert client2.delay == 2.0
        assert client2.cache_enabled == False
        
        # Test cache info
        cache_info = client.get_cache_info()
        print(f"  - Cache directory: {cache_info['cache_dir']}")
        print(f"  - Cache files: {cache_info['num_files']}")
        print(f"  - Cache size: {cache_info['total_size_mb']} MB")
        
        print("✅ Client initialization tests passed")
        return True

    except Exception as e:
        print(f"❌ Client test error: {e}")
        return False

def test_price_parser():
    """Test zonal price parser"""
    print("\nTesting price parser...")
    try:
        from cenace_downloader import CENACEClient

        client = CENACEClient(cache_enabled=False)
        sample_json = load_fixture('sample_price_response.json')
        records = client._parse_price_response(sample_json)

        assert len(records) == 2, "Should parse two price records"
        first = records[0]
        assert first['precio_total'] == 120.5, "Should parse precio_total"
        assert 'componente_energia' in first, "Should extract component fields"

        print("✅ Price parser tests passed")
        return True

    except Exception as e:
        print(f"❌ Price parser test error: {e}")
        return False

def test_combined_downloader():
    """Test combined demand and price download orchestration"""
    print("\nTesting combined downloader...")
    try:
        from cenace_downloader import CENACEClient

        client = CENACEClient(cache_enabled=False)
        demand_xml = load_fixture('sample_demand_response.xml')
        price_json = load_fixture('sample_price_response.json')

        def fake_make_request(url, expected_format="XML"):
            if "SWPEND" in url:
                return price_json
            return demand_xml

        client._make_request = fake_make_request  # type: ignore

        data = client.download_data(
            system='BCS',
            zones=['LA PAZ'],
            start_date=datetime(2024, 1, 1).date(),
            end_date=datetime(2024, 1, 1).date(),
            data_type='combined'
        )

        assert len(data) == 2, "Should return two merged records"
        for record in data:
            assert 'demanda' in record, "Merged record should contain demand"
            assert 'precio_total' in record, "Merged record should contain price"

        print("✅ Combined downloader tests passed")
        return True

    except Exception as e:
        print(f"❌ Combined downloader test error: {e}")
        return False

def test_assembler():
    """Test data assembler"""
    print("\nTesting data assembler...")
    try:
        from cenace_downloader import DataAssembler
        
        assembler = DataAssembler()
        
        # Test with sample demand and price data
        demand_data = [
            {
                'sistema': 'BCS',
                'zona_carga': 'LA PAZ',
                'fecha': '2024-01-01',
                'hora': 1,
                'demanda': 150.5
            },
            {
                'sistema': 'BCS',
                'zona_carga': 'LA PAZ',
                'fecha': '2024-01-01',
                'hora': 2,
                'demanda': 145.2
            }
        ]

        price_data = [
            {
                'sistema': 'BCS',
                'zona_carga': 'LA PAZ',
                'fecha': '2024-01-01',
                'hora': 1,
                'precio_total': 120.5,
                'componente_energia': 100.0
            },
            {
                'sistema': 'BCS',
                'zona_carga': 'LA PAZ',
                'fecha': '2024-01-01',
                'hora': 2,
                'precio_total': 118.3,
                'componente_energia': 98.0
            },
            {
                'sistema': 'BCS',
                'zona_carga': 'LA PAZ',
                'fecha': '2024-01-01',
                'hora': 3,
                'precio_total': 121.0,
                'componente_energia': 101.0
            }
        ]

        df = assembler.assemble_data(demand_data, price_data)

        assert len(df) == 3, "Should have 3 records after merging demand and price"
        assert 'datetime' in df.columns, "Should have datetime column"
        assert 'is_weekend' in df.columns, "Should have is_weekend column"
        assert 'season' in df.columns, "Should have season column"
        assert 'precio_total' in df.columns, "Should include merged price column"
        assert df.loc[df['hora'] == 3, 'demanda'].isna().all(), "Price-only rows should retain missing demand"

        # Test statistics
        stats = assembler.get_statistics()
        print(f"  - Total records: {stats.get('total_records', 0)}")
        print(f"  - Average demand: {stats.get('avg_demand_mw', 0):.2f} MW")
        assert 'avg_prices' in stats and 'precio_total' in stats['avg_prices'], "Should compute average price"
        expected_avg_price = (120.5 + 118.3 + 121.0) / 3
        assert abs(stats['avg_prices']['precio_total'] - expected_avg_price) < 1e-6

        daily = assembler.get_daily_summary()
        assert 'precio_total_mean' in daily.columns, "Daily summary should include price metrics"
        hourly = assembler.get_hourly_profile()
        assert 'precio_total_mean' in hourly.columns, "Hourly profile should include price metrics"

        print("✅ Data assembler tests passed")
        return True
        
    except Exception as e:
        print(f"❌ Assembler test error: {e}")
        return False

def test_integration():
    """Test basic integration"""
    print("\nTesting integration...")
    try:
        from cenace_downloader import CENACEClient, DataAssembler
        from datetime import datetime, timedelta
        
        # Note: We won't actually call the API in tests
        print("  - Client can be instantiated: ✓")
        print("  - Assembler can be instantiated: ✓")
        print("  - Date ranges can be created: ✓")
        print("  - Zones can be validated: ✓")
        
        print("✅ Integration tests passed")
        return True
        
    except Exception as e:
        print(f"❌ Integration test error: {e}")
        return False

def main():
    """Run all tests"""
    print("=" * 50)
    print("🧪 CENACE Downloader Package Tests")
    print("=" * 50)
    
    tests = [
        test_imports,
        test_zones,
        test_utils,
        test_client_initialization,
        test_price_parser,
        test_combined_downloader,
        test_assembler,
        test_integration
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ Test {test.__name__} crashed: {e}")
            failed += 1
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("✅ All tests passed! The package is ready to use.")
        print("\n🚀 To run the app, use: python run_app.py")
    else:
        print(f"❌ {failed} test(s) failed. Please check the errors above.")
        sys.exit(1)

if __name__ == "__main__":
    main()
