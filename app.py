!pip install openai yfinance streamlit pyngrok plotly -q

app_code = r"""
import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from openai import OpenAI

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
            df = stock.history(period=period)

            if df.empty:
                st.error(f"找不到代码 '{clean_ticker}'。请确认输入是否正确（美股请直接输入代码）。")
            else:
                st.write(f"### {clean_ticker} Preview")
                st.dataframe(df.tail())

                # 画图
                fig = go.Figure(data=[go.Candlestick(x=df.index,
                                open=df['Open'], high=df['High'],
                                low=df['Low'], close=df['Close'])])
                fig.update_layout(template="plotly_dark", title=f"{clean_ticker} Performance")
                st.plotly_chart(fig, use_container_width=True)

                # AI 分析
                client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
                data_str = df.tail(3).to_string()

                response = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {"role": "system", "content": "你是一位金融分析师。"},
                        {"role": "user", "content": f"分析 {clean_ticker} 的走势，提供建议。数据：\n{data_str}"}
                    ]
                )
                st.info(response.choices[0].message.content)
        except Exception as e:
            st.error(f"程序出错: {e}")
"""

# 将代码写入 app.py
with open("app.py", "w") as f:
    f.write(app_code)

# 3. 启动应用
from pyngrok import ngrok
import os

# ⚠️ 确保你的 Authtoken 已填入
ngrok.set_auth_token("3FUfC954pBLwRkShk8ILCDECiuP_2AtWyeMFAQVyh89fiUhUz")
ngrok.kill()
os.system("streamlit run app.py --server.port 8501 &")

# 获取并打印链接
public_url = ngrok.connect(8501, "http")
print(f"\n✅ 部署成功！点击下方链接使用：")
print(public_url.public_url)

# 将此代码块完全复制并运行，覆盖旧的 app.py
app_code = r"""
import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from openai import OpenAI

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
            df = stock.history(period=period)

            if df.empty:
                st.error(f"找不到代码 '{clean_ticker}'。")
            else:
                # --- 新增：计算百分比变化 ---
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

                # AI 分析 (加入百分比数据)
                client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
                # 将包含百分比的最后3行数据传给 AI
                data_str = df[['Close', 'Daily %']].tail(3).to_string()

                response = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {"role": "system", "content": "你是一位金融分析师，擅长解读百分比波动。"},
                        {"role": "user", "content": f"分析 {clean_ticker} 的走势，数据包含收盘价和日涨跌幅%。数据：\n{data_str}"}
                    ]
                )
                st.info(response.choices[0].message.content)
        except Exception as e:
            st.error(f"程序出错: {e}")
"""

# 将代码写入 app.py
with open("app.py", "w") as f:
    f.write(app_code)

print("✅ 代码更新成功！请重新运行你的启动脚本。")