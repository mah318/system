import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from openai import OpenAI

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
ticker = st.sidebar.text_input("Enter Stock:", "AAPL")
period = st.sidebar.selectbox("Time:", ["1D", "10D", "1mo", "3mo", "6mo", "1y", "10y", "20y"])

if st.sidebar.button("Analyse"):
    if not api_key:
        st.error("请输入 API Key")
    elif not ticker:
        st.error("请输入股票代码")
    else:
        try:
            # 清理输入
            clean_ticker = ticker.strip().upper()

            # 获取数据
           stock = yf.Ticker(clean_ticker)
           df = get_stock_data(clean_ticker, period)
        
            if df.empty:
                st.error(f"找不到代码 '{clean_ticker}'。")
            else:
                # --- [新功能] 展示公司基本面信息 ---
                info = stock.info
                with st.expander("📊 查看公司基本面信息"):
                    col1, col2 = st.columns(2)
                    col1.write(f"**公司全称**: {info.get('longName', 'N/A')}")
                    col1.write(f"**所属行业**: {info.get('industry', 'N/A')}")
                    col2.write(f"**当前市值**: {info.get('marketCap', 0):,}")
                    col2.write(f"**市盈率 (PE)**: {info.get('trailingPE', 'N/A')}")
                    st.write(f"**公司简介**: {info.get('longBusinessSummary', '无详细介绍')}")

                # 计算百分比变化
                df['Daily %'] = df['Close'].pct_change() * 100
                
                # 计算 50日移动平均线 (SMA 50) ---
                df['SMA_50'] = df['Close'].rolling(window=50).mean()
                
                st.write(f"### {clean_ticker} Preview")
                # 显示包含百分比的表格
                st.dataframe(df.tail().style.format({'Daily %': '{:.2f}%'}))

                # 画图
                fig = go.Figure(data=[go.Candlestick(x=df.index,
                                open=df['Open'], high=df['High'],
                                low=df['Low'], close=df['Close'])])
                fig.add_trace(go.Scatter(
                    x=df.index, 
                    y=df['SMA_50'], 
                    name='50 SMA', 
                    line=dict(color='yellow', width=1.5)
                ))
                
                fig.update_layout(template="plotly_dark", title=f"{clean_ticker} Performance")
                st.plotly_chart(fig, use_container_width=True)
                
                # AI 分析
                client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
                # 将包含百分比的最后3行数据传给 AI
                data_str = df[['Close', 'Daily %']].tail(3).to_string()

                response = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {"role": "system", "content": "你是一位金融分析师，擅长解读百分比波动和技术趋势。"},
                        {"role": "user", "content": f"分析 {clean_ticker} 的走势，数据包含收盘价和日涨跌幅%。数据：\n{data_str}"}
                    ]
                )
                st.info(response.choices[0].message.content)
        except Exception as e:
            st.error(f"程序出错: {e}")
