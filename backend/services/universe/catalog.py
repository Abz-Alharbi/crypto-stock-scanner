"""Frozen legacy universe constituents used as compatibility fallbacks."""

NASDAQ_SYMBOLS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AVGO", "COST", "NFLX",
    "AMD", "PEP", "ADBE", "CSCO", "CMCSA", "INTC", "TMUS", "INTU", "TXN", "QCOM",
    "AMAT", "HON", "AMGN", "SBUX", "ISRG", "BKNG", "VRTX", "ADI", "GILD", "MDLZ",
    "REGN", "LRCX", "PYPL", "ADP", "PANW", "KLAC", "SNPS", "CDNS", "MELI", "ABNB",
    "ASML", "MNST", "FTNT", "MAR", "NXPI", "MRVL", "ORLY", "ADSK", "CTAS", "WDAY",
]

NYSE_SYMBOLS = [
    "JPM", "V", "WMT", "JNJ", "PG", "MA", "HD", "UNH", "BAC", "DIS",
    "KO", "MRK", "PFE", "ABT", "TMO", "CVX", "XOM", "LLY", "ABBV", "NKE",
    "CRM", "DHR", "NEE", "UPS", "RTX", "LOW", "GS", "BLK", "BA", "CAT",
]

CRYPTO_SYMBOLS = [
    "X:BTCUSD", "X:ETHUSD", "X:SOLUSD", "X:ADAUSD", "X:DOTUSD",
    "X:DOGEUSD", "X:AVAXUSD", "X:MATICUSD", "X:LINKUSD", "X:UNIUSD",
    "X:XRPUSD", "X:LTCUSD", "X:ATOMUSD", "X:ALGOUSD", "X:NEARUSD",
]

ALL_STOCK_SYMBOLS = NASDAQ_SYMBOLS + NYSE_SYMBOLS

__all__ = ["ALL_STOCK_SYMBOLS", "CRYPTO_SYMBOLS", "NASDAQ_SYMBOLS", "NYSE_SYMBOLS"]
