import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from openai import OpenAI
import pandas as pd
import requests

# ==================== 在这里直接内置你的 API Key ====================
BUILTIN_API_KEY = "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" 
# ==================================================================

# 初始化模拟炒股账户资产 (Session State)
if 'cash' not in st.session_state:
    st.session_state.cash = 100000.0  # 初始虚拟资金 10万美元
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = {}  # 格式: {ticker: {"shares": 数量, "avg_price": 均价}}

# 统一的暗黑主题提示框函数
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

# 智能公司名称/代码转换函数（支持中文名搜索）
def get_ticker_from_name(query):
    query = query.strip()
    if not query:
        return ""
    url = f"https://query2.finance.yahoo.com/v1/finance/search?q={query}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    try:
        r = requests.get(url, headers=headers, timeout=5)
        data = r.json()
        if 'quotes' in data and len(data['quotes']) > 0:
            return data['quotes'][0]['symbol']
    except Exception:
        pass
    return query.upper()

@st.cache_data
def get_stock_data(ticker, period):
    stock = yf.Ticker(ticker)
    df = stock.history(period=period)
    return df

st.set_page_config(page_title="Financial Terminal", layout="wide")
st.title("📈 AI Financial Terminal ")

# 优先从 secrets 读取，若无则使用上方定义的 BUILTIN_API_KEY
try:
    api_key = st.secrets["GROQ_API_KEY"]
except:
    api_key = BUILTIN_API_KEY

# 侧边栏：独立的功能模块切换器
st.sidebar.header("功能导航")
app_mode = st.sidebar.radio("选择操作模式", ["📊 机构研报与数据分析", "🪙 模拟交易系统"])

if app_mode == "📊 机构研报与数据分析":
    st.sidebar.header("研报参数配置")
    tickers_raw = st.sidebar.text_input("Enter Company Name:", "Apple")
    period = st.sidebar.selectbox("Time:", ["1D", "10D", "1mo", "3mo", "6mo", "1y", "10y", "20y"], index=2)
    normalize = st.sidebar.checkbox("Normalize Comparison (Start from 0%)", value=True)

    raw_inputs = [t.strip() for t in tickers_raw.split(',') if t.strip()]
    
    if not raw_inputs:
        show_custom_alert("请输入公司名称或股票代码", "error")
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
                
            stock_primary = yf.Ticker(primary_ticker)
            info = stock_primary.info
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
                show_custom_alert("检测到未正确配置 API Key，请修改代码中的 BUILTIN_API_KEY。", "warning")
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

请遵循以下专业分析步骤（Chain of Thought）：
1. 【多头逻辑】：结合上述数据，寻找支撑该股票的正面逻辑（如成长性、估值优势或技术面动能）。
2. 【空头风险】：结合上述数据，寻找潜在的下行风险或估值泡沫。
3. 【综合裁决】：综合多空力量，给出客观评级。

请严格按照以下格式输出：
【操作评级】强烈买入 / 买入 / 持有观望 / 减持 / 卖出 (五选一)
【置信度评分】(1-10分，评估你对该判断的确信程度)
【多空博弈核心逻辑】(60字以内，必须结合具体数字说明)
【关键支撑与风控点】(各一句话，严格对应指标数据)
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

            tab1, tab2, tab3 = st.tabs(["🏢 基本面分析", "📊 技术指标", "📋 数据预览"])

            with tab1:
                st.subheader(f"基本盘分析: {primary_ticker}")
                col1, col2, col3 = st.columns(3)
                col1.metric("市值 (Market Cap)", market_cap_str)
                col2.metric("市盈率 (P/E)", pe_str)
                col3.metric("市净率 (P/B)", pb_str)
                
                col4, col5 = st.columns(2)
                col4.metric("利润率 (Profit Margin)", margin_str)
                col5.metric("营收增长率 (Revenue Growth)", growth_str)
                
                st.markdown("---")
                st.write("**🤖 AI 基本盘深度评估:**")
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

            with tab3:
                st.subheader(f"{primary_ticker} 原始数据预览")
                st.dataframe(df_primary.tail(10))

        except Exception as e:
            show_custom_alert(f"程序运行出错: {e}", "error")

elif app_mode == "🪙 模拟交易系统":
    st.subheader("🪙 模拟交易与资产管理系统")
    st.write("此模块与左侧研报数据**完全独立**。你可以随时输入任意股票代码进行虚拟买入和卖出，随时追踪资产盈亏。")
    
    col_tinput, col_tinfo = st.columns([2, 3])
    with col_tinput:
        trade_query = st.text_input("输入要交易的股票代码/名称:", "AAPL", key="independent_trade_ticker")
        resolved_trade_ticker = get_ticker_from_name(trade_query)
    
    trade_price = 0.0
    if resolved_trade_ticker:
        try:
            trade_df = get_stock_data(resolved_trade_ticker, "1D")
            if not trade_df.empty:
                trade_price = float(trade_df['Close'].iloc[-1])
                with col_tinfo:
                    st.markdown(f"""
                    <div style="background-color: #1a1a1a; padding: 10px 15px; border-radius: 6px; border: 1px solid #333333; color: #f0f0f0; margin-top: 24px;">
                        🎯 目标标的: <b>{resolved_trade_ticker}</b> | 最新价格: <b style="color: #4CAF50;">${trade_price:.2f}</b>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                show_custom_alert("未找到该股票的行情数据，请检查输入。", "warning")
        except:
            show_custom_alert("获取行情失败。", "warning")

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

    mcol1, mcol2, mcol3, mcol4 = st.columns(4)
    mcol1.metric("账户总资产", f"${total_assets:,.2f}", f"{total_profit_pct:+.2f}%")
    mcol2.metric("可用现金 (Cash)", f"${st.session_state.cash:,.2f}")
    mcol3.metric("持仓市值", f"${total_stock_value:,.2f}")
    mcol4.metric("累计盈亏", f"${total_profit:+,.2f}")

    st.markdown("---")
    
    col_buy, col_sell = st.columns(2)
    
    with col_buy:
        st.markdown(f"#### 🟢 买入: `{resolved_trade_ticker}`")
        buy_shares = st.number_input("买入股数", min_value=1, value=10, step=1, key="ind_buy_shares")
        total_cost = buy_shares * trade_price if trade_price > 0 else 0
        st.write(f"预计总花费: **${total_cost:,.2f}**")
        if st.button("确认买入此标的", key="btn_ind_buy"):
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
                show_custom_alert(f"成功买入 {buy_shares} 股 {resolved_trade_ticker}！", "success")
                st.rerun()
            else:
                show_custom_alert("可用现金不足，无法买入！", "error")

    with col_sell:
        st.markdown(f"#### 🔴 卖出: `{resolved_trade_ticker}`")
        owned_shares = st.session_state.portfolio.get(resolved_trade_ticker, {}).get("shares", 0)
        st.write(f"当前持有该股票数量: **{owned_shares} 股**")
        
        if owned_shares > 0:
            sell_shares = st.number_input("卖出股数", min_value=1, max_value=owned_shares, value=1, step=1, key="ind_sell_shares")
        else:
            sell_shares = st.number_input("卖出股数", min_value=0, max_value=0, value=0, step=1, disabled=True, key="ind_sell_shares_disabled")
        
        if st.button("确认卖出此标的", key="btn_ind_sell"):
            if owned_shares >= sell_shares > 0 and trade_price > 0:
                earned_cash = sell_shares * trade_price
                st.session_state.cash += earned_cash
                if owned_shares == sell_shares:
                    del st.session_state.portfolio[resolved_trade_ticker]
                else:
                    st.session_state.portfolio[resolved_trade_ticker]["shares"] -= sell_shares
                show_custom_alert(f"成功卖出 {sell_shares} 股 {resolved_trade_ticker}，获得现金 ${earned_cash:,.2f}！", "success")
                st.rerun()
            else:
                show_custom_alert("Insufficient holdings or no position to sell!", "error")
    st.markdown("---")
    st.subheader("📦 当前所有持仓明细")
    if portfolio_details:
        st.dataframe(pd.DataFrame(portfolio_details), use_container_width=True)
    else:
       show_custom_alert("📦 No current holdings. Enter a ticker above to start paper trading!", "info")
