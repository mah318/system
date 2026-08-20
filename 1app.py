import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from openai import OpenAI
import pandas as pd
import numpy as np
import requests
import concurrent.futures
import json
import urllib.parse

st.set_page_config(page_title="AI Financial Terminal", layout="wide")

# ==================== 在这里直接内置你的 API Key ====================
BUILTIN_API_KEY = "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"
# =================================================================-

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
})

def load_data():
    try:
        encoded_data = st.query_params.get("portfolio_data", None)
        if encoded_data:
            decoded_json = urllib.parse.unquote(encoded_data)
            return json.loads(decoded_json)
    except Exception:
        pass
    return {"cash": 100000.0, "portfolio": {}}

def save_data():
    try:
        data = {
            "cash": st.session_state.cash,
            "portfolio": st.session_state.portfolio
        }
        json_str = json.dumps(data, ensure_ascii=False)
        st.query_params["portfolio_data"] = urllib.parse.quote(json_str)
    except Exception as e:
        print(f"Save error: {e}")

saved_data = load_data()
if 'cash' not in st.session_state:
    st.session_state.cash = saved_data.get("cash", 100000.0)
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = saved_data.get("portfolio", {})

def show_custom_alert(text, alert_type="info"):
    colors = {
        "info": "#a0a0a0",
        "success": "#4CAF50",
        "warning": "#FFA726",
        "error": "#EF5350"
    }
    color = colors.get(alert_type, "#f0f0f0")
    st.markdown(f"""
    <div style="background-color: #1a1a1a; padding: 14px 20px; border-radius: 8px; border: 1px solid #333333; color: {color}; font-size: 14px; margin-bottom: 10px;">
        {text}
    </div>
    """, unsafe_allow_html=True)

@st.cache_data(ttl=3600)
def get_ticker_from_name(query):
    query = query.strip()
    if not query:
        return ""
    url = f"https://query2.finance.yahoo.com/v1/finance/search?q={query}"
    try:
        r = session.get(url, timeout=5)
        data = r.json()
        if 'quotes' in data and len(data['quotes']) > 0:
            return data['quotes'][0]['symbol']
    except Exception:
        pass
    return query.upper()

@st.cache_data(ttl=600)
def get_stock_data(ticker, period):
    try:
        stock = yf.Ticker(ticker, session=session)
        df = stock.history(period=period)
        return df
    except Exception:
        return pd.DataFrame()

# 采用 yfinance 原生 .info 属性，彻底根治 N/A 问题
@st.cache_data(ttl=600)
def get_stock_info(ticker):
    info_dict = {
        'marketCap': 'N/A',
        'currentPrice': 'N/A',
        'trailingPE': 'N/A',
        'priceToBook': 'N/A',
        'profitMargins': 'N/A',
        'revenueGrowth': 'N/A',
        'shortName': ticker,
        'sector': 'Others'
    }
    
    try:
        stock = yf.Ticker(ticker, session=session)
        inf = stock.info
        if inf:
            info_dict['marketCap'] = inf.get('marketCap', 'N/A')
            info_dict['currentPrice'] = inf.get('currentPrice', inf.get('regularMarketPrice', 'N/A'))
            info_dict['trailingPE'] = inf.get('trailingPE', 'N/A')
            info_dict['priceToBook'] = inf.get('priceToBook', 'N/A')
            info_dict['profitMargins'] = inf.get('profitMargins', 'N/A')
            info_dict['revenueGrowth'] = inf.get('revenueGrowth', 'N/A')
            info_dict['shortName'] = inf.get('shortName', inf.get('longName', ticker))
            info_dict['sector'] = inf.get('sector', 'Others')
    except Exception:
        pass

    return info_dict

@st.cache_data(ttl=600)
def get_stock_news(ticker):
    try:
        stock = yf.Ticker(ticker, session=session)
        news = stock.news
        titles = []
        if news:
            for item in news:
                title = item.get('title') or item.get('content', {}).get('title')
                if title:
                    titles.append(title)
        return titles[:5]
    except:
        return []

st.title("📈 AI Financial Terminal ")

try:
    api_key = st.secrets["GROQ_API_KEY"]
except:
    api_key = BUILTIN_API_KEY

st.sidebar.header("Function")
app_mode = st.sidebar.radio("Select Mode", ["📊 Data Analysis", "🪙 Trading System", "⚔️ Companies Comparison", "🏆 Top 50 Companies"])

if app_mode == "📊 Data Analysis":
    st.sidebar.header("Report Parameters")
    tickers_raw = st.sidebar.text_input("Enter Company Name:", "Apple")
    period = st.sidebar.selectbox("Time:", ["1D", "10D", "1mo", "3mo", "6mo", "1y", "10y", "20y"], index=2)
    normalize = st.sidebar.checkbox("Normalize Comparison (Start from 0%)", value=True)

    raw_inputs = [t.strip() for t in tickers_raw.split(',') if t.strip()]
    
    if not raw_inputs:
        show_custom_alert("Please enter a company name or ticker", "error")
    else:
        tickers_input = []
        mapping_info = []
        for item in raw_inputs:
            resolved = get_ticker_from_name(item)
            if resolved:
                tickers_input.append(resolved)
                mapping_info.append(f"**{item}** ➔ `{resolved}`")
        
        st.markdown(f"""
        <div style="background-color: #1a1a1a; padding: 12px 18px; border-radius: 8px; border: 1px solid #333333; color: #f0f0f0; font-size: 14px; margin-bottom: 15px;">
            {' | '.join(mapping_info)}
        </div>
        """, unsafe_allow_html=True)

        try:
            fig = go.Figure()
            for t in tickers_input:
                df = get_stock_data(t, period)
                if df.empty: continue
                y_data = (df['Close'] / df['Close'].iloc[0] - 1) * 100 if normalize else df['Close']
                fig.add_trace(go.Scatter(x=df.index, y=y_data, mode='lines', name=t))

            fig.update_layout(template="plotly_dark", title="收益率对比" if normalize else "价格对比")
            st.plotly_chart(fig, use_container_width=True)

            primary_ticker = tickers_input[0]
            df_primary = get_stock_data(primary_ticker, period)
            if df_primary.empty:
                show_custom_alert(f"未获取到 {primary_ticker} 的行情数据。", "error")
                st.stop()
                
            info = get_stock_info(primary_ticker)
            raw_market_cap = info.get('marketCap', 'N/A')
            raw_pe = info.get('trailingPE', 'N/A')
            raw_pb = info.get('priceToBook', 'N/A')
            raw_margin = info.get('profitMargins', 'N/A')
            raw_growth = info.get('revenueGrowth', 'N/A')
            
            market_cap_str = f"{raw_market_cap:,}" if isinstance(raw_market_cap, (int, float)) else str(raw_market_cap)
            pe_str = f"{raw_pe:.2f}" if isinstance(raw_pe, (int, float)) else str(raw_pe)
            pb_str = f"{raw_pb:.2f}" if isinstance(raw_pb, (int, float)) else str(raw_pb)
            margin_str = f"{raw_margin * 100:.2f}%" if isinstance(raw_margin, (int, float)) else "N/A"
            growth_str = f"{raw_growth * 100:.2f}%" if isinstance(raw_growth, (int, float)) else "N/A"
            
            delta = df_primary['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df_primary['RSI'] = 100 - (100 / (1 + rs))
            ema12 = df_primary['Close'].ewm(span=12, adjust=False).mean()
            ema26 = df_primary['Close'].ewm(span=26, adjust=False).mean()
            df_primary['MACD'] = ema12 - ema26
            df_primary['Signal'] = df_primary['MACD'].ewm(span=9, adjust=False).mean()

            latest = df_primary.iloc[-1]

            st.subheader(f"Dashboard: {primary_ticker}")
            if not api_key or api_key == "你的API_KEY填在这里":
                show_custom_alert("检测到未正确配置 API Key，请配置对应的 Key。", "warning")
            else:
                try:
                    client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
                    
                    models_response = client.models.list()
                    available_models = [m.id for m in models_response.data]
                    
                    auto_model = available_models[0] if available_models else "openai/gpt-oss-120b"
                    for m in available_models:
                        if any(k in m.lower() for k in ['chat', 'versatile', 'instant', '8b', '70b', 'gpt-oss', 'instruct']):
                            auto_model = m
                            break

                    tech_summary = f"RSI(14): {latest['RSI']:.2f}, MACD: {latest['MACD']:.2f}"
                    
                    signal_prompt = f"""你是一位资深的华尔街量化投资经理与风险控制专家。请基于以下多维财务与技术数据，对 {primary_ticker} 进行严谨的专业量化评估：

- 核心技术面 (近1个月): {tech_summary}
- 核心基本面: PE市盈率={pe_str}, PB市净率={pb_str}, 利润率={margin_str}, 营收增长={growth_str}

【排版绝对铁律】：
1. 严禁使用 Markdown 表格 (|...|)，必须使用结构化的段落和分点列表。
2. 保持排版清晰整洁，严禁换行错乱。

请遵循以下专业分析步骤：
1. 【多头逻辑】：结合上述数据，寻找支撑该股票的正面逻辑。
2. 【空头风险】：结合上述数据，寻找潜在的下行风险或估值泡沫。
3. 【综合裁决】：综合多空力量，给出客观评级。

请严格按照以下格式输出：
【操作评级】强烈买入 / 买入 / 持有观望 / 减持 / 卖出 (五选一)
【置信度评分】(1-10分)
【多空博弈核心逻辑】(60字以内)
【关键支撑与风控点】(各一句话)
"""
                    signal_response = client.chat.completions.create(
                        model=auto_model,
                        messages=[{"role": "user", "content": signal_prompt}]
                    )
                    ai_signal_text = signal_response.choices[0].message.content
                    
                    st.markdown(f"""
                    <div style="background-color: #1a1a1a; padding: 18px; border-radius: 10px; border: 1px solid #333333; color: #f0f0f0; font-size: 15px; line-height: 1.7; box-shadow: 0 4px 6px rgba(0,0,0,0.3);">
                        {ai_signal_text.replace('\n', '<br>')}
                    </div>
                    """, unsafe_allow_html=True)
                    
                except Exception as ai_err:
                    show_custom_alert(f"AI 智能决策请求失败: {ai_err}", "error")

            st.markdown("---")
            st.subheader(f"📰 News Sentiment & Analysis: {primary_ticker}")
            news_titles = get_stock_news(primary_ticker)
            if news_titles:
                st.write("**最新相关新闻标题：**")
                for title in news_titles:
                    st.markdown(f"- {title}")
                
                if api_key and api_key != "你的API_KEY填在这里":
                    try:
                        news_prompt = f"""请基于以下关于股票 {primary_ticker} 的最新新闻标题，进行专业的情感分析与舆情评估：
新闻列表：
{chr(10).join([f'- {t}' for t in news_titles])}

【排版要求】：严禁使用 Markdown 表格，使用清晰分点。
请严格按以下格式输出：
【舆情情感倾向】正面 / 中性 / 负面 (三选一)
【舆情综合得分】(0-100分)
【核心事件与市场影响总结】(80字以内)
"""
                        news_response = client.chat.completions.create(
                            model=auto_model,
                            messages=[{"role": "user", "content": news_prompt}]
                        )
                        st.markdown(f"""
                        <div style="background-color: #1a1a1a; padding: 16px; border-radius: 8px; border: 1px solid #333333; color: #f0f0f0; font-size: 14px; line-height: 1.6;">
                            {news_response.choices[0].message.content.replace('\n', '<br>')}
                        </div>
                        """, unsafe_allow_html=True)
                    except Exception as e:
                        show_custom_alert(f"新闻舆情 AI 分析失败: {e}", "warning")
                else:
                    show_custom_alert("请配置 API Key 以启用 AI 新闻舆情情感打分功能。", "warning")
            else:
                show_custom_alert("暂未获取到该股票的最新新闻数据。", "info")

            tab1, tab2, tab3 = st.tabs(["🏢 Fundamentals", "📊 Technical Indicators", "📋 Raw Data"])

            with tab1:
                st.subheader(f"Fundamentals Analysis: {primary_ticker}")
                col1, col2, col3 = st.columns(3)
                col1.metric("市值 (Market Cap)", market_cap_str)
                col2.metric("市盈率 (P/E)", pe_str)
                col3.metric("市净率 (P/B)", pb_str)
                
                col4, col5 = st.columns(2)
                col4.metric("利润率 (Profit Margin)", margin_str)
                col5.metric("营收增长率 (Revenue Growth)", growth_str)
                
                st.markdown("---")
                st.write("**🤖 AI Fundamental Evaluation:**")
                if api_key and api_key != "你的API_KEY填在这里":
                    try:
                        fund_prompt = f"基于 {primary_ticker} 的硬性数据（PE: {pe_str}, PB: {pb_str}, 利润率: {margin_str}, 营收增长: {growth_str}），请用数据推导列出5项核心基本面评价。"
                        fund_response = client.chat.completions.create(
                            model=auto_model,
                            messages=[{"role": "user", "content": fund_prompt}]
                        )
                        st.write(fund_response.choices[0].message.content)
                    except:
                        show_custom_alert("基本面 AI 评估加载失败。", "error")
                else:
                    show_custom_alert("请先配置 API Key 以查看 AI 评估。", "warning")
                    
            with tab2:
                st.subheader(f"技术指标 : {primary_ticker}")
                st.line_chart(df_primary[['RSI']])
                st.line_chart(df_primary[['MACD', 'Signal']])
                
                df_candle = get_stock_data(primary_ticker, period)
                
                if not df_candle.empty:
                    fig_candle = go.Figure(data=[go.Candlestick(
                        x=df_candle.index,
                        open=df_candle['Open'],
                        high=df_candle['High'],
                        low=df_candle['Low'],
                        close=df_candle['Close'],
                        name='Market Data'
                    )])

                    fig_candle.update_layout(
                        template="plotly_dark",
                        xaxis_rangeslider_visible=False,
                        title=f"{primary_ticker} Candlestick Analysis",
                        yaxis_title="Price",
                        height=500
                    )
                    
                    st.plotly_chart(fig_candle, use_container_width=True)
                    
                    df_candle['SMA_20'] = df_candle['Close'].rolling(window=20).mean()
                    st.line_chart(df_candle[['Close', 'SMA_20']])
                else:
                    st.warning("No technical data available.")

            with tab3:
                st.subheader(f"{primary_ticker} 原始数据预览")
                st.dataframe(df_primary.tail(10))

        except Exception as e:
            show_custom_alert(f"程序运行出错: {e}", "error")

elif app_mode == "🪙 Trading System":
    st.subheader("🪙 Trading")
    
    col_tinput, col_tinfo = st.columns([2, 3])
    with col_tinput:
        trade_query = st.text_input("Enter the stock code/name:", "AAPL", key="independent_trade_ticker")
        resolved_trade_ticker = get_ticker_from_name(trade_query)
    
    trade_price = 0.0
    trade_returns = pd.Series(dtype=float)
    if resolved_trade_ticker:
        try:
            trade_df = get_stock_data(resolved_trade_ticker, "1y")
            if not trade_df.empty and 'Close' in trade_df.columns:
                valid_closes = trade_df['Close'].dropna()
                if not valid_closes.empty:
                    trade_price = float(valid_closes.iloc[-1])
            
            if pd.isna(trade_price) or trade_price == 0.0:
                try:
                    inf = get_stock_info(resolved_trade_ticker)
                    trade_price = float(inf.get('currentPrice') or 0.0)
                except:
                    pass

            if not trade_df.empty:
                trade_returns = trade_df['Close'].pct_change().dropna()

            with col_tinfo:
                price_display = f"${trade_price:.2f}" if not pd.isna(trade_price) and trade_price > 0 else "N/A"
                st.markdown(f"""
                <div style="background-color: #1a1a1a; padding: 10px 15px; border-radius: 6px; border: 1px solid #333333; color: #f0f0f0; margin-top: 24px;">
                    <b>{resolved_trade_ticker}</b> | Latest Prices: <b style="color: #4CAF50;">{price_display}</b>
                </div>
                """, unsafe_allow_html=True)
            if trade_df.empty:
                show_custom_alert("未找到该股票的行情数据，请检查输入。", "warning")
        except Exception as e:
            show_custom_alert(f"获取行情失败: {e}", "warning")

    st.markdown("---")

    total_stock_value = 0.0
    portfolio_details = []
    
    for t, data in st.session_state.portfolio.items():
        shares = data["shares"]
        avg_price = data["avg_price"]
        latest_df = get_stock_data(t, "1D")
        cur_p = float(latest_df['Close'].iloc[-1]) if not latest_df.empty else avg_price
        market_val = shares * cur_p
        pnl = market_val - (shares * avg_price)
        pnl_pct = (pnl / (shares * avg_price)) * 100 if (shares * avg_price) > 0 else 0
        total_stock_value += market_val
        
        portfolio_details.append({
            "股票代码": t,
            "持仓数量": shares,
            "平均成本": f"${avg_price:.2f}",
            "当前价格": f"${cur_p:.2f}",
            "市值": f"${market_val:.2f}",
            "浮动盈亏": f"${pnl:.2f} ({pnl_pct:.2f}%)"
        })

    total_assets = st.session_state.cash + total_stock_value
    total_profit = total_assets - 100000.0
    total_profit_pct = (total_profit / 100000.0) * 100

    mcol1, mcol2, mcol3, mcol4, mcol5, mcol6 = st.columns(6)
    mcol1.metric("账户总资产", f"${total_assets:,.2f}", f"{total_profit_pct:+.2f}%")
    mcol2.metric("可用现金", f"${st.session_state.cash:,.2f}")
    mcol3.metric("持仓市值", f"${total_stock_value:,.2f}")
    mcol4.metric("累计盈亏", f"${total_profit:+,.2f}")
    st.markdown("---")
    
    col_buy, col_sell = st.columns(2)
    
    with col_buy:
        st.markdown(f"#### 🟢 Buy: `{resolved_trade_ticker}`")
        buy_shares = st.number_input("买入股数", min_value=1, value=10, step=1, key="ind_buy_shares")
        total_cost = buy_shares * trade_price if trade_price > 0 else 0
        st.write(f"预计总花费: **${total_cost:,.2f}**")
        if st.button("Confirm Buy", key="btn_ind_buy"):
            if trade_price <= 0:
                show_custom_alert("无效的股票价格！", "error")
            elif st.session_state.cash >= total_cost:
                st.session_state.cash -= total_cost
                if resolved_trade_ticker in st.session_state.portfolio:
                    old_shares = st.session_state.portfolio[resolved_trade_ticker]["shares"]
                    old_avg = st.session_state.portfolio[resolved_trade_ticker]["avg_price"]
                    new_shares = old_shares + buy_shares
                    new_avg = ((old_shares * old_avg) + total_cost) / new_shares
                    st.session_state.portfolio[resolved_trade_ticker] = {"shares": new_shares, "avg_price": new_avg}
                else:
                    st.session_state.portfolio[resolved_trade_ticker] = {"shares": buy_shares, "avg_price": trade_price}
                
                save_data()
                show_custom_alert(f"成功买入 {buy_shares} 股 {resolved_trade_ticker}！", "success")
                st.rerun()
            else:
                show_custom_alert("可用现金不足，无法买入！", "error")

    with col_sell:
        st.markdown(f"#### 🔴 Sell: `{resolved_trade_ticker}`")
        owned_shares = st.session_state.portfolio.get(resolved_trade_ticker, {}).get("shares", 0)
        st.write(f"当前持有该股票数量: **{owned_shares} 股**")
        
        if owned_shares > 0:
            sell_shares = st.number_input("卖出股数", min_value=1, max_value=owned_shares, value=1, step=1, key="ind_sell_shares")
        else:
            sell_shares = st.number_input("卖出股数", min_value=0, max_value=0, value=0, step=1, disabled=True, key="ind_sell_shares_disabled")
        
        if st.button("Confirm Sell", key="btn_ind_sell"):
            if owned_shares >= sell_shares > 0 and trade_price > 0:
                earned_cash = sell_shares * trade_price
                st.session_state.cash += earned_cash
                if owned_shares == sell_shares:
                    del st.session_state.portfolio[resolved_trade_ticker]
                else:
                    st.session_state.portfolio[resolved_trade_ticker]["shares"] -= sell_shares
                
                save_data()
                show_custom_alert(f"成功卖出 {sell_shares} 股 {resolved_trade_ticker}，获得现金 ${earned_cash:,.2f}！", "success")
                st.rerun()
            else:
                show_custom_alert("Insufficient holdings or no position to sell!", "error")
                
    st.markdown("---")
    st.subheader("📦 Current Holdings Details")
    if portfolio_details:
        st.dataframe(pd.DataFrame(portfolio_details), use_container_width=True)
        
        st.markdown("---")
        st.subheader("📊 Portfolio Risk & Distribution Analysis")
        
        col_pie, col_heat = st.columns(2)
        
        with col_pie:
            st.markdown("#### 行业板块分布 (Sector Allocation)")
            sector_allocation = {}
            for t, data in st.session_state.portfolio.items():
                shares = data["shares"]
                latest_df = get_stock_data(t, "1D")
                cur_p = float(latest_df['Close'].iloc[-1]) if not latest_df.empty else data["avg_price"]
                market_val = shares * cur_p
                try:
                    sector = get_stock_info(t).get('sector', 'Others')
                except:
                    sector = 'Others'
                sector_allocation[sector] = sector_allocation.get(sector, 0.0) + market_val
            
            if sector_allocation:
                sec_df = pd.DataFrame(list(sector_allocation.items()), columns=["Sector", "Value"])
                fig_pie = go.Figure(data=[go.Pie(labels=sec_df["Sector"], values=sec_df["Value"], hole=.3)])
                fig_pie.update_layout(template="plotly_dark", margin=dict(t=20, b=20, l=20, r=20))
                st.plotly_chart(fig_pie, use_container_width=True)
            else:
                show_custom_alert("暂无行业数据", "info")

elif app_mode == "⚔️ Companies Comparison":
    st.subheader("⚔️Stock Comparison")
    
    col_pk1, col_pk2 = st.columns(2)
    with col_pk1:
        query_a = st.text_input("Enter Company A:", "Apple", key="pk_comp_a")
        resolved_a = get_ticker_from_name(query_a)
    with col_pk2:
        query_b = st.text_input("Enter Company B:", "Microsoft", key="pk_comp_b")
        resolved_b = get_ticker_from_name(query_b)

    if st.button("Start", key="btn_run_pk"):
        if not resolved_a or not resolved_b:
            show_custom_alert("请输入两家有效的公司名称或代码", "error")
        else:
            with st.spinner("正在获取双方财务数据与基本面信息并进行 AI 深度对比..."):
                try:
                    info_a = get_stock_info(resolved_a)
                    info_b = get_stock_info(resolved_b)
                    
                    data_a = {
                        "Ticker": resolved_a,
                        "Name": info_a.get('shortName', resolved_a),
                        "MarketCap": f"{info_a.get('marketCap', 0):,}" if isinstance(info_a.get('marketCap'), (int, float)) else 'N/A',
                        "PE": f"{info_a.get('trailingPE', 'N/A'):.2f}" if isinstance(info_a.get('trailingPE'), (int, float)) else 'N/A',
                        "PB": f"{info_a.get('priceToBook', 'N/A'):.2f}" if isinstance(info_a.get('priceToBook'), (int, float)) else 'N/A',
                        "Margin": f"{info_a.get('profitMargins', 0) * 100:.2f}%" if isinstance(info_a.get('profitMargins'), (int, float)) else 'N/A',
                        "Growth": f"{info_a.get('revenueGrowth', 0) * 100:.2f}%" if isinstance(info_a.get('revenueGrowth'), (int, float)) else 'N/A'
                    }
                    data_b = {
                        "Ticker": resolved_b,
                        "Name": info_b.get('shortName', resolved_b),
                        "MarketCap": f"{info_b.get('marketCap', 0):,}" if isinstance(info_b.get('marketCap'), (int, float)) else 'N/A',
                        "PE": f"{info_b.get('trailingPE', 'N/A'):.2f}" if isinstance(info_b.get('trailingPE'), (int, float)) else 'N/A',
                        "PB": f"{info_b.get('priceToBook', 'N/A'):.2f}" if isinstance(info_b.get('priceToBook'), (int, float)) else 'N/A',
                        "Margin": f"{info_b.get('profitMargins', 0) * 100:.2f}%" if isinstance(info_b.get('profitMargins'), (int, float)) else 'N/A',
                        "Growth": f"{info_b.get('revenueGrowth', 0) * 100:.2f}%" if isinstance(info_b.get('revenueGrowth'), (int, float)) else 'N/A'
                    }
                    
                    client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
                    pk_prompt = f"""你是一位顶级华尔街基金经理与行业研究专家。请对以下两家公司进行全方位的深度 PK 对比评测：

公司 A: {data_a['Name']} ({data_a['Ticker']})
- 市值: {data_a['MarketCap']}
- 市盈率 (PE): {data_a['PE']}
- 市净率 (PB): {data_a['PB']}
- 利润率: {data_a['Margin']}
- 营收增长: {data_a['Growth']}

公司 B: {data_b['Name']} ({data_b['Ticker']})
- 市值: {data_b['MarketCap']}
- 市盈率 (PE): {data_b['PE']}
- 市净率 (PB): {data_b['PB']}
- 利润率: {data_b['Margin']}
- 营收增长: {data_b['Growth']}

【排版绝对铁律】：
1. 严禁使用任何 Markdown 表格 (|...|)，必须使用纯文本的标题与分点列表。
2. 确保排版整洁、层级分明、绝不出现换行混乱。

请从以下几个维度进行深度剖析：
1. 【商业模式与护城河对比】：谁的护城河更深？核心壁垒是什么？
2. 【财务健康与估值优劣】：结合 PE, PB, 利润率与增长率，谁的性价比更高？
3. 【增长潜力与未来催化剂】：谁在未来更有爆发力或更稳健？
4. 【最终裁决 (Winner)】: 明确给出更推荐哪一家，并给出核心理由。
"""
                    pk_response = client.chat.completions.create(
                        model="openai/gpt-oss-120b",
                        messages=[{"role": "user", "content": pk_prompt}]
                    )
                    st.markdown(f"""
                    <div style="background-color: #1a1a1a; padding: 20px; border-radius: 10px; border: 1px solid #333333; color: #f0f0f0; font-size: 15px; line-height: 1.7;">
                        {pk_response.choices[0].message.content.replace('\n', '<br>')}
                    </div>
                    """, unsafe_allow_html=True)
                except Exception as e:
                    show_custom_alert(f"AI PK 评测失败: {e}", "error")

elif app_mode == "🏆 Top 50 Companies":
    st.subheader("🏆 Market Leaders Ranking")
    
    market_option = st.radio("Select Market:", ["Global (USA)", "Malaysia (Bursa)"], horizontal=True)
    
    global_companies = [
        ("AAPL", "Apple Inc."), ("MSFT", "Microsoft Corporation"), ("NVDA", "NVIDIA Corporation"),
        ("GOOGL", "Alphabet Inc."), ("AMZN", "Amazon.com, Inc."), ("META", "Meta Platforms, Inc."),
        ("BRK-B", "Berkshire Hathaway"), ("TSLA", "Tesla, Inc."), ("LLY", "Eli Lilly and Company"),
        ("AVGO", "Broadcom Inc."), ("JPM", "JPMorgan Chase & Co."), ("WMT", "Walmart Inc."),
        ("V", "Visa Inc."), ("XOM", "Exxon Mobil Corporation"), ("MA", "Mastercard Incorporated"),
        ("UNH", "UnitedHealth Group"), ("COST", "Costco Wholesale"), ("JNJ", "Johnson & Johnson"),
        ("HD", "The Home Depot"), ("PG", "Procter & Gamble"), ("NFLX", "Netflix, Inc."),
        ("ABBV", "AbbVie Inc."), ("BAC", "Bank of America"), ("CRM", "Salesforce, Inc."),
        ("AMD", "Advanced Micro Devices"), ("ADBE", "Adobe Inc."), ("CVX", "Chevron Corporation"),
        ("WFC", "Wells Fargo & Company"), ("MRK", "Merck & Co., Inc."), ("TMO", "Thermo Fisher Scientific"),
        ("LIN", "Linde plc"), ("ABT", "Abbott Laboratories"), ("DIS", "The Walt Disney Company"),
        ("PM", "Philip Morris International"), ("IBM", "International Business Machines"),
        ("QCOM", "QUALCOMM Incorporated"), ("GE", "General Electric Company"), ("CAT", "Caterpillar Inc."),
        ("AMAT", "Applied Materials"), ("INTU", "Intuit Inc."), ("BKNG", "Booking Holdings Inc."),
        ("NOW", "ServiceNow, Inc."), ("ISRG", "Intuitive Surgical"), ("SPGI", "S&P Global Inc."),
        ("VZ", "Verizon Communications"), ("T", "AT&T Inc."), ("PFE", "Pfizer Inc."),
        ("UBER", "Uber Technologies"), ("NKE", "NIKE, Inc."), ("PYPL", "PayPal Holdings")
    ]

    malaysia_companies = [
        ("1155.KL", "Malayan Banking Bhd (Maybank)"), ("1295.KL", "Public Bank Bhd"),
        ("1023.KL", "CIMB Group Holdings"), ("5347.KL", "Tenaga Nasional Bhd"),
        ("5183.KL", "Petronas Chemicals"), ("5225.KL", "IHH Healthcare"),
        ("5819.KL", "Hong Leong Bank"), ("8869.KL", "Press Metal Aluminium"),
        ("6012.KL", "Maxis Bhd"), ("6947.KL", "CelcomDigi Bhd"),
        ("1961.KL", "IOI Corporation"), ("6742.KL", "YTL Power International"),
        ("4863.KL", "Telekom Malaysia"), ("2445.KL", "Kuala Lumpur Kepong (KLK)"),
        ("5326.KL", "99 Speed Mart"), ("4456.KL", "Gamuda Bhd"),
        ("6718.KL", "YTL Corporation"), ("5285.KL", "SD Guthrie (Sime Darby Plant.)"),
        ("1066.KL", "RHB Bank"), ("6033.KL", "Petronas Gas"),
        ("3816.KL", "MISC Bhd"), ("5211.KL", "Sunway Bhd"),
        ("5246.KL", "Westports Holdings"), ("4707.KL", "Nestle (Malaysia)"),
        ("1015.KL", "AMMB Holdings"), ("5878.KL", "Dialog Group"),
        ("4197.KL", "Sime Darby Bhd"), ("6888.KL", "Axiata Group"),
        ("5657.KL", "Petronas Dagangan"), ("1083.KL", "Hong Leong Financial")
    ]

    target_list = global_companies if "Global" in market_option else malaysia_companies
    currency_symbol = "$" if "Global" in market_option else "RM"

    @st.cache_data(ttl=600)
    def fetch_market_data(companies_list, currency_sym):
        def get_single_stock_info(item):
            ticker, name = item
            try:
                inf = get_stock_info(ticker)
                price = inf.get('currentPrice') if isinstance(inf.get('currentPrice'), (int, float)) else 0
                mcap = inf.get('marketCap') if isinstance(inf.get('marketCap'), (int, float)) else 0
                return {
                    "Ticker": ticker,
                    "Company": name,
                    "Price_Display": f"{currency_sym}{price:,.2f}" if price else "N/A",
                    "Market Cap": f"{mcap:,.0f}" if mcap else "N/A",
                    "MarketCap_Raw": mcap
                }
            except:
                return {
                    "Ticker": ticker, "Company": name, 
                    "Price_Display": "N/A", "Market Cap": "N/A", "MarketCap_Raw": 0
                }

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            data_rows = list(executor.map(get_single_stock_info, companies_list))
        return pd.DataFrame(data_rows)

    with st.spinner(f"Fetching {market_option} data..."):
        df_top = fetch_market_data(target_list, currency_symbol)
    
    if not df_top.empty and "MarketCap_Raw" in df_top.columns:
        df_top = df_top.sort_values(by="MarketCap_Raw", ascending=False).reset_index(drop=True)
        df_top.index = df_top.index + 1
        df_display = df_top.drop(columns=["MarketCap_Raw"])
        df_display.columns = ["Ticker", "Company", "Latest Price", "Market Cap"]
        st.dataframe(df_display, use_container_width=True)
    else:
        show_custom_alert("Failed to load data, please check your internet connection.", "error")
