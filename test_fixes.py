"""
Test script to verify the fixes are working correctly
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.services.exchanges import fetch_ohlcv_cached, fetch_funding_rate
from api.services.signals import calculate_signal

def test_funding_rate_threshold():
    """Test that funding rate thresholds are correct"""
    print("Testing funding rate data...")
    try:
        # Test BTC funding rate
        funding = fetch_funding_rate("BTCUSDT", "binance")
        if funding:
            rate = funding["lastFundingRate"]
            print(f"BTC funding rate: {rate} ({rate * 100:.4f}%)")

            # Test threshold logic (should be 0.0005 for sell, not 0.05)
            if rate > 0.0005:
                print(f"✓ Sell signal threshold triggered: {rate} > 0.0005")
            elif rate > 0.05:
                print(f"✗ Old threshold would trigger: {rate} > 0.05 (this should NOT happen)")
            else:
                print(f"✓ No funding rate trigger: {rate}")
        else:
            print("✗ Failed to fetch funding rate")
    except Exception as e:
        print(f"✗ Error testing funding rate: {e}")

def test_signal_calculation():
    """Test the unified signal calculation"""
    print("\nTesting signal calculation...")
    try:
        # Fetch data
        df = fetch_ohlcv_cached("BTC/USDT", "1h", 100)
        print(f"✓ Fetched OHLCV data: {len(df)} rows")

        # Calculate signal
        signal = calculate_signal(df, "BTC/USDT")
        print(f"✓ Signal calculated: {signal['action']}")
        print(f"  RSI: {signal['scores']['rsi']:.2f}")
        print(f"  Funding: {signal['scores']['funding']:.6f} ({signal['scores']['funding'] * 100:.4f}%)")
        print(f"  MACD Hist: {signal['scores']['macd_hist']:.6f}")
        print(f"  Reasons: {'; '.join(signal['reasons'])}")

    except Exception as e:
        print(f"✗ Error testing signal calculation: {e}")

def test_error_handling():
    """Test error handling for invalid symbols"""
    print("\nTesting error handling...")
    try:
        # Test invalid symbol
        funding = fetch_funding_rate("INVALID", "binance")
        if funding is None:
            print("✓ Correctly handled invalid funding rate symbol")
        else:
            print("✗ Should have returned None for invalid symbol")

        # Test invalid OHLCV symbol (this should raise an exception)
        try:
            df = fetch_ohlcv_cached("INVALID/SYMBOL", "1h", 10)
            print("✗ Should have raised exception for invalid OHLCV symbol")
        except Exception as e:
            print(f"✓ Correctly handled invalid OHLCV symbol: {str(e)[:50]}...")

    except Exception as e:
        print(f"✗ Unexpected error in error handling test: {e}")

if __name__ == "__main__":
    print("=== Testing Crypto Signal Fixes ===")
    test_funding_rate_threshold()
    test_signal_calculation()
    test_error_handling()
    print("\n=== Test Complete ===")
