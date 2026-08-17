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

st.set_page_config(page_title="Financial Terminal", layout="wide")
st.title("📈 AI Financial Terminal")

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
            
            # 获取基本面核心指标并做美化处理
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
            
            # 计算技术指标
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
            client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")

            # --- AI 智能信号看板 (顶层直接给出买入/观望/卖出评级与精简理由) ---
            tech_summary = f"Ticker: {primary_ticker}, RSI: {latest['RSI']:.2f}, MACD: {latest['MACD']:.2f}, Signal: {latest['Signal']:.2f}"
            signal_prompt = f"""请根据以下数据对 {primary_ticker} 进行极简的投资决策分析：
- 技术面: {tech_summary}
- 基本面: PE={pe_str}, PB={pb_str}, 利润率={margin_str}, 营收增长={growth_str}

请严格按以下格式输出，字数精炼：
【操作评级】买入 / 观望 / 卖出 (三选一)
【核心理由】(控制在40字以内)
【关键支撑与风险】(各一句话)
"""
            signal_response = client.chat.completions.create(
                model="llama-3.1-70b-versatile",
                messages=[{"role": "user", "content": signal_prompt}]
            )
            ai_signal_text = signal_response.choices[0].message.content
            st.session_state['analysis_result'] = ai_signal_text

            st.subheader(f"🤖 AI 智能决策看板: {primary_ticker}")
            st.info(ai_signal_text)

            # 2. Tabs 分页
            tab1, tab2, tab3, tab4, tab5 = st.tabs(["🏢 基本面分析", "📊 技术指标", "📰 情绪分析", "📝 生成报告", "📋 数据预览"])

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
                
                fund_prompt = f"""请对 {primary_ticker} 进行基本面分析评估。核心财务指标：
- 市值: {market_cap_str}, PE: {pe_str}, PB: {pb_str}, 利润率: {margin_str}, 营收增长: {growth_str}

请使用带序号和缩进的清爽排版：
1. 市值: {market_cap_str}
   - 分析其规模与市场地位
2. 市盈率 (P/E): {pe_str}
   - 分析估值水平与性价比
3. 市净率 (P/B): {pb_str}
   - 分析资产状况与风险
4. 利润率: {margin_str}
   - 分析盈利与成本控制
5. 营收增长率: {growth_str}
   - 分析成长潜力
"""
                fund_response = client.chat.completions.create(
                    model="llama-3.1-70b-versatile",
                    messages=[{"role": "user", "content": fund_prompt}]
                )
                st.write(fund_response.choices[0].message.content)

            with tab2:
                st.subheader(f"技术指标: {primary_ticker}")
                st.line_chart(df_primary[['RSI']])
                st.line_chart(df_primary[['MACD', 'Signal']])

            with tab3:
                st.subheader("新闻情绪分析")
                news = stock_primary.news
                if news and isinstance(news, list):
                    headlines = [n.get('title', '无标题新闻') for n in news[:5]]
                    for h in headlines: st.write(f"- {h}")
                    
                    if headlines:
                        sentiment_prompt = f"分析关于 {primary_ticker} 的新闻标题，判断市场情绪（精炼）：\n{', '.join(headlines)}"
                        sentiment_response = client.chat.completions.create(
                            model="llama-3.1-70b-versatile",
                            messages=[{"role": "user", "content": sentiment_prompt}]
                        )
                        st.info(sentiment_response.choices[0].message.content)

            with tab4:
                st.subheader("一键导出报告")
                if 'analysis_result' in st.session_state:
                    st.download_button("下载分析报告", data=st.session_state['analysis_result'], file_name=f"{primary_ticker}_analysis.txt")
            
            with tab5:
                st.subheader(f"{primary_ticker} 原始数据预览")
                st.dataframe(df_primary.tail(10))

        except Exception as e:
            st.error(f"程序出错: {e}")
