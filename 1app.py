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
st.title("📈 AI Financial Terminal (精简投研版)")

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
            
            # 获取基本面与市场数据
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
                "target_price": info.get('targetMeanPrice', 'N/A'),
                "recommendation": info.get('recommendationKey', 'N/A')
            }
            
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

            news = stock_primary.news
            headlines = []
            if news and isinstance(news, list):
                headlines = [n.get('title', '无标题新闻') for n in news[:8]]

            # --- AI 核心决策与精简诊断 ---
            client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
            
            summary_prompt = f"""你是一位华尔街资深量化分析师。请根据以下数据对 {primary_ticker} 进行极简、高效的评级。
【数据】
- 当前价格: {current_price:.2f} (区间涨跌: {period_return:.2f}%)
- RSI: {latest['RSI']:.2f}, MACD: {latest['MACD']:.2f}
- PE: {fin_data['pe']}, PB: {fin_data['pb']}, ROE: {fin_data['roe']}
- 分析师评级倾向: {fin_data['recommendation']} (目标价: {fin_data['target_price']})
- 近期新闻: {', '.join(headlines[:3])}

请严格按以下格式输出，字数精炼：
【操作评级】买入 / 观望 / 卖出 (三选一，必须明确)
【一句话核心理由】(控制在30字以内)
【关键支撑与风险】(分两点，每点一句话)
"""
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": summary_prompt}]
            )
            ai_output = response.choices[0].message.content
            st.session_state['analysis_result'] = ai_output

            # 顶层醒目展示 AI 信号
            st.subheader(f"🤖 AI 智能决策看板: {primary_ticker}")
            st.info(ai_output)

            # 2. Tabs 分页
            tab1, tab2, tab3, tab4, tab5 = st.tabs(["🏢 基本面分析", "📊 技术指标", "📰 情绪分析", "📝 生成报告", "📋 数据预览"])

            with tab1:
                st.subheader("核心基本面指标")
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("市值", market_cap_str)
                col2.metric("市盈率 (PE)", str(fin_data['pe']))
                col3.metric("市净率 (PB)", str(fin_data['pb']))
                col4.metric("ROE", str(fin_data['roe']))
                
                col5, col6, col7, col8 = st.columns(4)
                col5.metric("利润率", str(fin_data['profit_margin']))
                col6.metric("营收增长", str(fin_data['revenue_growth']))
                col7.metric("贝塔 Beta", str(fin_data['beta']))
                col8.metric("分析师目标价", str(fin_data['target_price']))

            with tab2:
                st.subheader(f"技术指标: {primary_ticker}")
                st.line_chart(df_primary[['RSI']])
                st.line_chart(df_primary[['MACD', 'Signal']])

            with tab3:
                st.subheader("精选市场新闻")
                if headlines:
                    for h in headlines: 
                        st.write(f"- {h}")
                else:
                    st.warning("暂无新闻数据。")

            with tab4:
                st.subheader("一键导出报告")
                if 'analysis_result' in st.session_state:
                    st.download_button(
                        label="下载投研摘要 (TXT)",
                        data=st.session_state['analysis_result'],
                        file_name=f"{primary_ticker}_signal_report.txt",
                        mime="text/plain"
                    )
            
            with tab5:
                st.subheader(f"{primary_ticker} 原始数据预览")
                st.dataframe(df_primary.tail(10))

        except Exception as e:
            st.error(f"程序出错: {e}")
