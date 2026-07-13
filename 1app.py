import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from openai import OpenAI

# 缓存函数：只返回纯数据 DataFrame
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

# [升级] 改为自由输入框
tickers_raw = st.sidebar.text_input("Stocks:", "AAPL, MSFT")
period = st.sidebar.selectbox("Times:", ["7D, "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y"])

if st.sidebar.button("Analyse"):
    # 将输入的字符串转换为列表，并去除空格转为大写
    tickers_input = [t.strip().upper() for t in tickers_raw.split(',') if t.strip()]
    
    if not api_key:
        st.error("请输入 API Key")
    elif not tickers_input:
        st.error("请至少输入一个股票代码")
    else:
        try:
            fig = go.Figure()
            
            # 遍历解析出的列表
            for t in tickers_input:
                df = get_stock_data(t, period)
                
                if df.empty:
                    st.warning(f"无法获取代码 '{t}' 的数据，请检查代码拼写。")
                    continue
                
                # 绘制折线图
                fig.add_trace(go.Scatter(x=df.index, y=df['Close'], mode='lines', name=t))

            # 更新图表布局
            fig.update_layout(
                template="plotly_dark", 
                title="股票表现对比",
                xaxis_title="日期",
                yaxis_title="收盘价 (USD)"
            )
            st.plotly_chart(fig, use_container_width=True)

            # AI 分析（依然锁定第一只股票作为分析主标的）
            st.write("---")
            primary_ticker = tickers_input[0]
            st.subheader(f"深度 AI 分析: {primary_ticker}")
            
            df_primary = get_stock_data(primary_ticker, period)
            stock_primary = yf.Ticker(primary_ticker)
            info = stock_primary.info
            
            # 展示基本面
            with st.expander("📊 查看公司基本面信息"):
                st.write(f"**公司**: {info.get('longName', 'N/A')}")
                st.write(f"**行业**: {info.get('industry', 'N/A')}")
                st.write(f"**市值**: {info.get('marketCap', 0):,}")

            # 准备 AI 数据
            df_primary['Daily %'] = df_primary['Close'].pct_change() * 100
            df_primary['SMA_50'] = df_primary['Close'].rolling(window=50).mean()
            data_for_ai = df_primary[['Close', 'Daily %', 'SMA_50']].tail(10).to_string()
            
            client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
            
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "你是一位专业金融分析师。请分析给定数据，判断趋势并给出投资逻辑。"},
                    {"role": "user", "content": f"分析对象: {info.get('longName', 'N/A')}\n最近10天数据:\n{data_for_ai}"}
                ]
            )
            st.info(response.choices[0].message.content)

        except Exception as e:
            st.error(f"程序出错: {e}")
