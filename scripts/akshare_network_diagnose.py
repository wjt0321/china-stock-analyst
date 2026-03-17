import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

import stock_utils as su


def _print_env_snapshot():
    keys = ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY", "AKSHARE_USE_PROXY"]
    print("=== ENV ===")
    for key in keys:
        value = os.getenv(key)
        if value:
            print(f"{key}=SET")
        else:
            print(f"{key}=EMPTY")


def _print_akshare_basic():
    print("=== AKSHARE BASIC ===")
    module = su._load_akshare_module()
    if module is None:
        print("akshare_installed=False")
        return False
    print("akshare_installed=True")
    version = getattr(module, "__version__", "unknown")
    print(f"akshare_version={version}")
    return True


def _run_quote_check(symbol: str = "600000"):
    print("=== QUOTE CHECK ===")
    result = su.query_akshare_quote(symbol)
    print(f"success={result.get('success')}")
    if result.get("success"):
        quote = (result.get("data") or {}).get("quote") or {}
        print(f"symbol={quote.get('symbol')}")
        print(f"name={quote.get('name')}")
        print(f"last_price={quote.get('last_price')}")
        print(f"trade_date={quote.get('trade_date')}")
        print(f"endpoint={(result.get('meta') or {}).get('endpoint')}")
        return
    error = result.get("error") or {}
    details = error.get("details") or {}
    print(f"error_code={error.get('code')}")
    print(f"error_message={error.get('message')}")
    print(f"error_type={details.get('error_type')}")
    print(f"raw_error={details.get('error')}")


if __name__ == "__main__":
    print(f"diagnose_time={datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    _print_env_snapshot()
    if _print_akshare_basic():
        _run_quote_check("600000")
