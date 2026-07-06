import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import google.generativeai as genai

st.set_page_config(page_title="Financial Terminal", layout="wide")
st.title("📈 AI Financial Terminal")

# 侧边栏配置
st.sidebar.header("配置")

# 优先读取 Secrets，没有则显示输入框
if "GOOGLE_API_KEY" in st.secrets:
    api_key = st.secrets["GOOGLE_API_KEY"]
else:
    api_key = st.sidebar.text_input("Gemini API Key:", type="password")

ticker = st.sidebar.text_input("Enter Stock:", "AAPL")
period = st.sidebar.selectbox("Time:", ["1D", "10D", "1mo", "3mo", "6mo", "1y", "10y", "20y"])

if st.sidebar.button("Analyse"):
    if not api_key:
        st.error("请输入 API Key (或在 Streamlit Secrets 中配置 GOOGLE_API_KEY)")
    elif not ticker:
        st.error("请输入股票代码")
    else:
        try:
            # 清理输入
            clean_ticker = ticker.strip().upper()

            # 获取数据
            stock = yf.Ticker(clean_ticker)
            df = stock.history(period=period)

            if df.empty:
                st.error(f"找不到代码 '{clean_ticker}'。")
            else:
                # 计算百分比变化
                df['Daily %'] = df['Close'].pct_change() * 100
                
                st.write(f"### {clean_ticker} Preview")
                # 显示包含百分比的表格
                st.dataframe(df.tail().style.format({'Daily %': '{:.2f}%'}))

                # 画图
                fig = go.Figure(data=[go.Candlestick(x=df.index,
                                open=df['Open'], high=df['High'],
                                low=df['Low'], close=df['Close'])])
                fig.update_layout(template="plotly_dark", title=f"{clean_ticker} Performance")
                st.plotly_chart(fig, use_container_width=True)

                # AI 分析 (使用 Gemini)
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel('gemini-1.5-flash')
                
                # 准备传给 AI 的数据
                data_str = df[['Close', 'Daily %']].tail(3).to_string()
                prompt = f"你是一位金融分析师，擅长解读百分比波动。分析 {clean_ticker} 的走势。数据：\n{data_str}"
                
                response = model.generate_content(prompt)
                st.subheader("🤖 AI 专家建议")
                st.info(response.text)
                
        except Exception as e:
            st.error(f"程序出错: {e}")
