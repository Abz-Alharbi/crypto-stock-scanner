from backend.clients.polygon import polygon
from backend.errors import ApiError
from backend.services.cache import cache_get, cache_set
from backend.symbols import canonicalize_symbol

# ============================================================
def _safe_val(obj, *keys, default=None):
    """Safely extract nested value from Polygon financials structure"""
    current = obj
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key)
        else:
            return default
        if current is None:
            return default
    # Polygon stores values as {'value': 123, 'unit': 'USD'} or just a number
    if isinstance(current, dict) and 'value' in current:
        return current['value']
    return current


def _pct(value, total):
    """Calculate percentage safely"""
    if not value or not total or total == 0:
        return None
    return round((value / total) * 100, 2)


def _ratio(numerator, denominator):
    """Calculate ratio safely"""
    if not numerator or not denominator or denominator == 0:
        return None
    return round(numerator / denominator, 2)


def _fmt_large(num):
    """Format large numbers: 1.5B, 340M, etc."""
    if num is None:
        return None
    num = float(num)
    if abs(num) >= 1e12:
        return f"${num/1e12:.2f}T"
    if abs(num) >= 1e9:
        return f"${num/1e9:.2f}B"
    if abs(num) >= 1e6:
        return f"${num/1e6:.1f}M"
    if abs(num) >= 1e3:
        return f"${num/1e3:.1f}K"
    return f"${num:.2f}"


def _generate_summary(company, valuation, profitability, growth, health, dividends_info):
    """Generate a plain-English summary of the fundamental analysis"""
    name = company.get('name', 'This company')
    sector = company.get('sector', '')
    industry = company.get('industry', '')
    market_cap = company.get('market_cap_formatted', '')

    lines = []

    # Company intro
    sector_str = f" in the {industry} industry ({sector} sector)" if industry and sector else (f" in the {sector} sector" if sector else "")
    cap_str = f" with a market capitalization of {market_cap}" if market_cap else ""
    lines.append(f"{name} operates{sector_str}{cap_str}.")

    # Valuation
    pe = valuation.get('pe_ratio')
    if pe is not None:
        if pe < 0:
            lines.append(f"The company currently has negative earnings with a P/E of {pe}, indicating it is not profitable at this time.")
        elif pe < 15:
            lines.append(f"With a P/E ratio of {pe}, the stock appears attractively valued relative to its earnings.")
        elif pe < 25:
            lines.append(f"The P/E ratio of {pe} suggests a fairly valued stock in line with market averages.")
        else:
            lines.append(f"At a P/E of {pe}, the stock carries a premium valuation, suggesting high growth expectations.")

    # Profitability
    margin = profitability.get('profit_margin')
    roe = profitability.get('roe')
    if margin is not None:
        if margin > 20:
            lines.append(f"Profitability is strong with a {margin}% net margin, indicating efficient operations.")
        elif margin > 5:
            lines.append(f"The company maintains moderate profitability with a {margin}% net margin.")
        elif margin > 0:
            lines.append(f"Profit margins are thin at {margin}%, leaving limited room for error.")
        else:
            lines.append(f"The company is currently unprofitable with a {margin}% net margin.")

    if roe is not None and roe > 15:
        lines.append(f"Return on equity of {roe}% demonstrates effective use of shareholder capital.")

    # Growth
    rev_growth = growth.get('revenue_growth')
    if rev_growth is not None:
        if rev_growth > 20:
            lines.append(f"Revenue growth of {rev_growth}% year-over-year signals strong business momentum.")
        elif rev_growth > 0:
            lines.append(f"Revenue grew {rev_growth}% year-over-year, showing steady expansion.")
        else:
            lines.append(f"Revenue declined {rev_growth}% year-over-year, which may concern investors.")

    # Financial Health
    de = health.get('debt_to_equity')
    fcf = health.get('free_cash_flow_formatted')
    if de is not None:
        if de < 0.5:
            lines.append(f"The balance sheet is conservative with a debt-to-equity ratio of {de}.")
        elif de < 1.5:
            lines.append(f"Debt levels are manageable with a debt-to-equity ratio of {de}.")
        else:
            lines.append(f"Leverage is elevated at a {de} debt-to-equity ratio, which adds financial risk.")
    if fcf:
        lines.append(f"Free cash flow stands at {fcf}.")

    # Dividends
    div_yield = dividends_info.get('dividend_yield')
    if div_yield and div_yield > 0:
        lines.append(f"The company pays a dividend with a {div_yield}% yield.")

    return ' '.join(lines)



def get_fundamentals(symbol):
    """Get comprehensive fundamental analysis for a stock symbol"""
    canonical = canonicalize_symbol(symbol)
    symbol = canonical.provider_symbol
    cache_key = f"fundamentals:{symbol}"
    cached = cache_get(cache_key)
    if cached:
        return cached
    # ── Fetch all data ─────────────────────────────────
    details = polygon.get_ticker_details(symbol)
    if not details:
        raise ApiError(f'No data found for {symbol}. May not be a valid US stock ticker.', 404, 'not_found')
    prev_close = polygon.get_previous_close(symbol)
    financials_annual = polygon.get_financials(symbol, limit=3, timeframe='annual')
    financials_quarterly = polygon.get_financials(symbol, limit=4, timeframe='quarterly')
    dividends_data = polygon.get_dividends(symbol, limit=4)
    # Current price from previous close
    current_price = prev_close.get('c', 0) if prev_close else 0
    shares_outstanding = details.get('share_class_shares_outstanding') or details.get('weighted_shares_outstanding') or 0
    # ── Company Overview ───────────────────────────────
    market_cap = details.get('market_cap') or (current_price * shares_outstanding if shares_outstanding else None)
    company = {
        'name': details.get('name', symbol),
        'ticker': symbol,
        'description': details.get('description', ''),
        'sector': details.get('sic_description', '') or '',
        'industry': details.get('sic_description', '') or '',
        'market_cap': market_cap,
        'market_cap_formatted': _fmt_large(market_cap),
        'employees': details.get('total_employees'),
        'homepage': details.get('homepage_url', ''),
        'logo': details.get('branding', {}).get('icon_url', '') if details.get('branding') else '',
        'list_date': details.get('list_date', ''),
        'locale': details.get('locale', ''),
        'exchange': details.get('primary_exchange', ''),
        'current_price': current_price,
        'shares_outstanding': shares_outstanding,
    }
    # ── Parse Financial Statements ─────────────────────
    latest = financials_annual[0] if financials_annual else {}
    prev_annual = financials_annual[1] if len(financials_annual) > 1 else {}
    latest_q = financials_quarterly[0] if financials_quarterly else {}
    inc = latest.get('financials', {}).get('income_statement', {})
    bs = latest.get('financials', {}).get('balance_sheet', {})
    cf = latest.get('financials', {}).get('cash_flow_statement', {})
    prev_inc = prev_annual.get('financials', {}).get('income_statement', {})
    # Income statement values
    revenue = _safe_val(inc, 'revenues', default=0)
    net_income = _safe_val(inc, 'net_income_loss', default=0)
    gross_profit = _safe_val(inc, 'gross_profit', default=0)
    operating_income = _safe_val(inc, 'operating_income_loss', default=0)
    ebitda = _safe_val(inc, 'income_loss_from_continuing_operations_before_tax', default=0)
    eps_basic = _safe_val(inc, 'basic_earnings_per_share', default=None)
    eps_diluted = _safe_val(inc, 'diluted_earnings_per_share', default=None)
    # Previous year for growth
    prev_revenue = _safe_val(prev_inc, 'revenues', default=0)
    prev_net_income = _safe_val(prev_inc, 'net_income_loss', default=0)
    # Balance sheet values
    total_assets = _safe_val(bs, 'assets', default=0)
    total_liabilities = _safe_val(bs, 'liabilities', default=0)
    total_equity = _safe_val(bs, 'equity', default=0)
    current_assets = _safe_val(bs, 'current_assets', default=0)
    current_liabilities = _safe_val(bs, 'current_liabilities', default=0)
    long_term_debt = _safe_val(bs, 'long_term_debt') or _safe_val(bs, 'noncurrent_liabilities', default=0)
    # Book value
    book_value = total_equity if total_equity else (total_assets - total_liabilities) if total_assets else 0
    book_value_per_share = _ratio(book_value, shares_outstanding)
    # Cash flow values
    operating_cash_flow = _safe_val(cf, 'net_cash_flow_from_operating_activities', default=0)
    capex = abs(_safe_val(cf, 'net_cash_flow_from_investing_activities', default=0))
    free_cash_flow = (operating_cash_flow - capex) if operating_cash_flow else None
    # ── Valuation Metrics ──────────────────────────────
    pe_ratio = _ratio(current_price, eps_diluted) if eps_diluted else (_ratio(market_cap, net_income) if net_income and net_income != 0 else None)
    # Forward P/E using quarterly extrapolation
    q_net = _safe_val(latest_q.get('financials', {}).get('income_statement', {}), 'net_income_loss', default=0)
    forward_earnings = q_net * 4 if q_net else None
    forward_pe = _ratio(market_cap, forward_earnings) if forward_earnings and forward_earnings != 0 else None
    ps_ratio = _ratio(market_cap, revenue) if revenue and revenue != 0 else None
    pb_ratio = _ratio(current_price, book_value_per_share) if book_value_per_share and book_value_per_share != 0 else None
    # EV/EBITDA
    enterprise_value = (market_cap or 0) + (long_term_debt or 0) - _safe_val(bs, 'cash_and_cash_equivalents', default=0) if market_cap else None
    ev_ebitda = _ratio(enterprise_value, ebitda) if ebitda and ebitda != 0 else None
    # PEG (using earnings growth)
    earnings_growth = _pct(net_income - prev_net_income, abs(prev_net_income)) if prev_net_income and prev_net_income != 0 else None
    peg_ratio = _ratio(pe_ratio, earnings_growth) if pe_ratio and earnings_growth and earnings_growth > 0 else None
    valuation = {
        'pe_ratio': round(pe_ratio, 2) if pe_ratio else None,
        'forward_pe': round(forward_pe, 2) if forward_pe else None,
        'peg_ratio': round(peg_ratio, 2) if peg_ratio else None,
        'pb_ratio': round(pb_ratio, 2) if pb_ratio else None,
        'ps_ratio': round(ps_ratio, 2) if ps_ratio else None,
        'ev_ebitda': round(ev_ebitda, 2) if ev_ebitda else None,
        'enterprise_value': enterprise_value,
        'enterprise_value_formatted': _fmt_large(enterprise_value),
        'eps_basic': round(eps_basic, 2) if eps_basic else None,
        'eps_diluted': round(eps_diluted, 2) if eps_diluted else None,
    }
    # ── Profitability ──────────────────────────────────
    profitability = {
        'revenue': revenue,
        'revenue_formatted': _fmt_large(revenue),
        'net_income': net_income,
        'net_income_formatted': _fmt_large(net_income),
        'gross_profit': gross_profit,
        'gross_profit_formatted': _fmt_large(gross_profit),
        'operating_income': operating_income,
        'operating_income_formatted': _fmt_large(operating_income),
        'profit_margin': _pct(net_income, revenue),
        'operating_margin': _pct(operating_income, revenue),
        'gross_margin': _pct(gross_profit, revenue),
        'roe': _pct(net_income, total_equity) if total_equity and total_equity != 0 else None,
        'roa': _pct(net_income, total_assets) if total_assets and total_assets != 0 else None,
    }
    # ── Growth ─────────────────────────────────────────
    revenue_growth = _pct(revenue - prev_revenue, abs(prev_revenue)) if prev_revenue and prev_revenue != 0 else None
    growth = {
        'revenue_growth': revenue_growth,
        'earnings_growth': earnings_growth,
        'filing_date': latest.get('filing_date', ''),
        'fiscal_year': latest.get('fiscal_year', ''),
        'fiscal_period': latest.get('fiscal_period', ''),
    }
    # ── Financial Health ───────────────────────────────
    health = {
        'total_assets': total_assets,
        'total_assets_formatted': _fmt_large(total_assets),
        'total_liabilities': total_liabilities,
        'total_liabilities_formatted': _fmt_large(total_liabilities),
        'total_equity': total_equity,
        'total_equity_formatted': _fmt_large(total_equity),
        'debt_to_equity': _ratio(total_liabilities, total_equity) if total_equity and total_equity != 0 else None,
        'current_ratio': _ratio(current_assets, current_liabilities) if current_liabilities and current_liabilities != 0 else None,
        'long_term_debt': long_term_debt,
        'long_term_debt_formatted': _fmt_large(long_term_debt),
        'book_value_per_share': round(book_value_per_share, 2) if book_value_per_share else None,
        'free_cash_flow': free_cash_flow,
        'free_cash_flow_formatted': _fmt_large(free_cash_flow),
        'operating_cash_flow': operating_cash_flow,
        'operating_cash_flow_formatted': _fmt_large(operating_cash_flow),
    }
    # ── Dividends ──────────────────────────────────────
    annual_dividend = 0
    latest_div = None
    if dividends_data:
        latest_div = dividends_data[0]
        # Sum last 4 quarters for annual dividend
        for d in dividends_data[:4]:
            annual_dividend += d.get('cash_amount', 0)
    dividend_yield = _pct(annual_dividend, current_price) if annual_dividend and current_price else None
    dividends_info = {
        'dividend_yield': dividend_yield,
        'annual_dividend': round(annual_dividend, 4) if annual_dividend else None,
        'dividend_per_share': round(latest_div['cash_amount'], 4) if latest_div and latest_div.get('cash_amount') else None,
        'frequency': latest_div.get('frequency') if latest_div else None,
        'ex_dividend_date': latest_div.get('ex_dividend_date') if latest_div else None,
        'pay_date': latest_div.get('pay_date') if latest_div else None,
        'payout_ratio': _pct(annual_dividend * shares_outstanding, net_income) if annual_dividend and shares_outstanding and net_income and net_income > 0 else None,
    }
    # ── Generate Summary ───────────────────────────────
    summary_text = _generate_summary(company, valuation, profitability, growth, health, dividends_info)
    # ── Build response ─────────────────────────────────
    result = {
        'symbol': canonical.display_symbol,
        'raw_symbol': canonical.provider_symbol,
        'provider_symbol': canonical.provider_symbol,
        'display_symbol': canonical.display_symbol,
        'market': canonical.market,
        'canonical_symbol': canonical.to_dict(),
        'company': company,
        'valuation': valuation,
        'profitability': profitability,
        'growth': growth,
        'health': health,
        'dividends': dividends_info,
        'summary': summary_text,
        'data_source': 'polygon.io',
        'last_filing': latest.get('filing_date', 'N/A'),
    }
    cache_set(cache_key, result, ttl=3600)  # Cache 1 hour
    return result
