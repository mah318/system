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
tickers_raw= st.sidebar.text_input("Enter Stock:", "AAPL")
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
                
                if df.empty:
                    st.warning(f"无法获取代码 '{t}' 的数据。")
                    continue
                
                y_data = (df['Close'] / df['Close'].iloc[0] - 1) * 100 if normalize else df['Close']
                fig.add_trace(go.Scatter(x=df.index, y=y_data, mode='lines', name=t))

            fig.update_layout(template="plotly_dark", title="收益率对比" if normalize else "价格对比")
            st.plotly_chart(fig, use_container_width=True)

            # 准备主分析对象的数据
            primary_ticker = tickers_input[0]
            df_primary = get_stock_data(primary_ticker, period)
            stock_primary = yf.Ticker(primary_ticker)
            
            # 计算指标 (无需 pandas-ta)
            df_primary['Daily %'] = df_primary['Close'].pct_change() * 100
            
            delta = df_primary['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df_primary['RSI'] = 100 - (100 / (1 + rs))
            
            ema12 = df_primary['Close'].ewm(span=12, adjust=False).mean()
            ema26 = df_primary['Close'].ewm(span=26, adjust=False).mean()
            df_primary['MACD'] = ema12 - ema26
            df_primary['Signal'] = df_primary['MACD'].ewm(span=9, adjust=False).mean()

            # 2. Tabs 分页
            tab1, tab2, tab3, tab4 = st.tabs(["📊 技术指标", "📰 情绪分析", "📝 生成报告", "📋 数据预览"])

            with tab1:
                st.subheader(f"技术指标: {primary_ticker}")
                st.write("RSI (14天)")
                st.line_chart(df_primary[['RSI']])
                st.write("MACD (12, 26, 9)")
                st.line_chart(df_primary[['MACD', 'Signal']])

            with tab2:
                st.subheader("新闻情绪分析")
                news = stock_primary.news
                if news and isinstance(news, list):
                    headlines = [n.get('title', '无标题新闻') for n in news[:5]]
                    st.write("**最新头条:**")
                    for h in headlines: 
                        st.write(f"- {h}")
                    
                    if headlines:
                        client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
                        sentiment_prompt = f"分析以下关于 {primary_ticker} 的新闻标题，判断市场情绪，并给出建议：\n{', '.join(headlines)}"
                        response = client.chat.completions.create(
                            model="llama-3.3-70b-versatile",
                            messages=[{"role": "user", "content": sentiment_prompt}]
                        )
                        analysis_text = response.choices[0].message.content
                        st.info(analysis_text)
                        st.session_state['analysis_result'] = analysis_text
                    else:
                        st.warning("暂无新闻标题。")
                else:
                    st.warning("无法获取新闻数据。")

            with tab3:
                st.subheader("一键导出报告")
                if 'analysis_result' in st.session_state:
                    st.download_button(
                        label="下载分析报告 (TXT)",
                        data=st.session_state['analysis_result'],
                        file_name=f"{primary_ticker}_analysis.txt",
                        mime="text/plain"
                    )
            
            with tab4:
                st.subheader(f"{primary_ticker} 原始数据预览")
                st.dataframe(df_primary.tail(10).style.format({'Daily %': '{:.2f}%'}))

        except Exception as e:
            st.error(f"程序出错: {e}")
