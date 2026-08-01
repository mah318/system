import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from openai import OpenAI
import pandas as pd

@st.cache_data
def get_stock_data(ticker, period):
    stock = yf.Ticker(ticker)
    df = stock.history(period=period)
    return df

st.set_page_config(page_title="Pro Financial Terminal", layout="wide")
st.title("📈 AI Financial Terminal (Pro 深度版)")

# 侧边栏配置
st.sidebar.header("配置")
api_key = st.sidebar.text_input("API Key:", type="password")
tickers_raw = st.sidebar.text_input("Enter Stock:", "AAPL")
period = st.sidebar.selectbox("Time:", ["1D", "10D", "1mo", "3mo", "6mo", "1y", "10y", "20y"])
normalize = st.sidebar.checkbox("开启归一化对比 (从0%起步)", value=True)

if st.sidebar.button("Analyse"):
    tickers_input = [t.strip().upper() for t in tickers_raw.split(',') if t.strip()]
    
    if not api_key or not tickers_input:
        st.error("请输入 API Key 和股票代码")
    else:
        try:
            # 1. 绘图与对比
            fig = go.Figure()
            for t in tickers_input:
                df = get_stock_data(t, period)
                if df.empty: continue
                y_data = (df['Close'] / df['Close'].iloc[0] - 1) * 100 if normalize else df['Close']
                fig.add_trace(go.Scatter(x=df.index, y=y_data, mode='lines', name=t))

            fig.update_layout(template="plotly_dark", title="收益率对比" if normalize else "价格对比")
            st.plotly_chart(fig, use_container_width=True)

            # 准备主分析对象的数据
            primary_ticker = tickers_input[0]
            df_primary = get_stock_data(primary_ticker, period)
            stock_primary = yf.Ticker(primary_ticker)
            
            # --- 深度扩充：获取更丰富的基础面与市场数据 ---
            info = stock_primary.info
            fin_data = {
                "market_cap": info.get('marketCap', 'N/A'),
                "pe": info.get('trailingPE', 'N/A'),
                "forward_pe": info.get('forwardPE', 'N/A'),
                "pb": info.get('priceToBook', 'N/A'),
                "profit_margin": info.get('profitMargins', 'N/A'),
                "revenue_growth": info.get('revenueGrowth', 'N/A'),
                "roe": info.get('returnOnEquity', 'N/A'),
                "debt_to_equity": info.get('debtToEquity', 'N/A'),
                "beta": info.get('beta', 'N/A'),
                "dividend_yield": info.get('dividendYield', 'N/A'),
                "52w_high": info.get('fiftyTwoWeekHigh', 'N/A'),
                "52w_low": info.get('fiftyTwoWeekLow', 'N/A'),
                "target_price": info.get('targetMeanPrice', 'N/A'),
                "recommendation": info.get('recommendationKey', 'N/A')
            }
            
            # 格式化展示字符串
            market_cap_str = f"{fin_data['market_cap']:,}" if isinstance(fin_data['market_cap'], (int, float)) else str(fin_data['market_cap'])
            
            # 计算技术指标
            current_price = df_primary['Close'].iloc[-1]
            start_price = df_primary['Close'].iloc[0]
            period_return = ((current_price - start_price) / start_price) * 100
            
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

            # 获取更多新闻（最多 10 条）
            news = stock_primary.news
            headlines = []
            if news and isinstance(news, list):
                headlines = [n.get('title', '无标题新闻') for n in news[:10]]

            # --- AI 深度全景诊断 (主页顶部) ---
            with st.expander("🤖 AI 深度全景综合投研诊断", expanded=True):
                client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
                
                comprehensive_prompt = f"""你是一位华尔街资深量化投研专家。请结合以下多维度的详尽数据，对股票 {primary_ticker} 进行一份严谨、深度、结构化的全景投研分析。

【1. 价格与技术面数据】
- 当前价格: {current_price:.2f}
- 选定周期累计涨跌幅: {period_return:.2f}%
- RSI (14): {latest['RSI']:.2f}
- MACD: {latest['MACD']:.2f}, Signal: {latest['Signal']:.2f}

【2. 基本面与估值数据】
- 市值: {market_cap_str}
- 市盈率 (PE): {fin_data['pe']} (前瞻PE: {fin_data['forward_pe']})
- 市净率 (PB): {fin_data['pb']}
- 净资产收益率 (ROE): {fin_data['roe']}
- 利润率: {fin_data['profit_margin']}
- 营收增长率: {fin_data['revenue_growth']}
- 债务权益比 (Debt/Equity): {fin_data['debt_to_equity']}
- 贝塔系数 (Beta): {fin_data['beta']}
- 52周最高/最低: {fin_data['52w_high']} / {fin_data['52w_low']}
- 分析师目标均价: {fin_data['target_price']} (整体评级倾向: {fin_data['recommendation']})

【3. 近期市场热点/新闻标题】
{chr(10).join([f"- {h}" for h in headlines]) if headlines else "- 暂无近期新闻"}

请输出包含以下模块的专业深度分析：
1. **核心估值与基本盘评估**（结合PE、PB、ROE及成长性评价其财务健康度与安全边际）
2. **技术面动量与趋势分析**（结合RSI、MACD与近期涨跌幅判断当前买卖点）
3. **市场情绪与新闻解读**（结合新闻标题和分析师目标价分析市场共识）
4. **综合投资建议与风险提示**（给出明确的中短期操作倾向及潜在风险点）

排版请保持清晰、严谨，多使用序号和关键指标点缀。
"""
                response = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": comprehensive_prompt}]
                )
                analysis_text = response.choices[0].message.content
                st.write(analysis_text)
                st.session_state['analysis_result'] = analysis_text

            # 2. Tabs 分页
            tab1, tab2, tab3, tab4, tab5 = st.tabs(["🏢 基本面分析", "📊 技术指标", "📰 情绪分析", "📝 生成报告", "📋 数据预览"])

            with tab1:
                st.subheader(f"基本盘深度指标: {primary_ticker}")
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("市值", market_cap_str)
                col2.metric("市盈率 (PE)", str(fin_data['pe']))
                col3.metric("前瞻PE", str(fin_data['forward_pe']))
                col4.metric("市净率 (PB)", str(fin_data['pb']))
                
                col5, col6, col7, col8 = st.columns(4)
                col5.metric("ROE", str(fin_data['roe']))
                col6.metric("利润率", str(fin_data['profit_margin']))
                col7.metric("营收增长", str(fin_data['revenue_growth']))
                col8.metric("贝塔 Beta", str(fin_data['beta']))

                st.markdown("---")
                st.write(f"**分析师共识评级:** {fin_data['recommendation']} | **目标均价:** {fin_data['target_price']}")

            with tab2:
                st.subheader(f"技术指标: {primary_ticker}")
                st.line_chart(df_primary[['RSI']])
                st.line_chart(df_primary[['MACD', 'Signal']])

            with tab3:
                st.subheader("新闻情绪分析 (Top 10)")
                if headlines:
                    for h in headlines: 
                        st.write(- {h})
                else:
                    st.warning("暂无新闻数据。")

            with tab4:
                st.subheader("一键导出深度投研报告")
                if 'analysis_result' in st.session_state:
                    st.download_button(
                        label="下载完整投研报告 (TXT)",
                        data=st.session_state['analysis_result'],
                        file_name=f"{primary_ticker}_deep_analysis.txt",
                        mime="text/plain"
                    )
            
            with tab5:
                st.subheader(f"{primary_ticker} 原始数据预览")
                st.dataframe(df_primary.tail(10))

        except Exception as e:
            st.error(f"程序出错: {e}")
