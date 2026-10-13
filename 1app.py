import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from openai import OpenAI
import pandas as pd
import numpy as np
import requests
import json
import os
import urllib.parse
import concurrent.futures

st.set_page_config(page_title="TradeView", layout="wide")

DATA_FILE = "tradeview_data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_data():
    data = {
        "users": st.session_state.get("users", {"admin": "888888"}),
        "logged_in": st.session_state.get("logged_in", False),
        "current_user": st.session_state.get("current_user", ""),
        "cash": st.session_state.get("cash", 100000.0),
        "portfolio": st.session_state.get("portfolio", {}),
        "auto_rules": st.session_state.get("auto_rules", [])
    }
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# Load data from disk on startup
saved_data = load_data()

if "users" not in st.session_state:
    st.session_state["users"] = saved_data.get("users", {"admin": "888888"})

if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = saved_data.get("logged_in", False)

if "current_user" not in st.session_state:
    st.session_state["current_user"] = saved_data.get("current_user", "")

if "cash" not in st.session_state:
    st.session_state["cash"] = saved_data.get("cash", 100000.0)

if "portfolio" not in st.session_state:
    st.session_state["portfolio"] = saved_data.get("portfolio", {})

if "auto_rules" not in st.session_state:
    st.session_state["auto_rules"] = saved_data.get("auto_rules", [])

# If not logged in, show login/signup interface
if not st.session_state["logged_in"]:
    st.markdown("<h2 style='text-align: center;'> TradeView</h2>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        auth_mode = st.radio("Select Action", ["Log In", "Sign Up"], horizontal=True)
        
        if auth_mode == "Log In":
            username = st.text_input("Username", key="login_user")
            password = st.text_input("Password", type="password", key="login_pass")
            
            if st.button("Log In", use_container_width=True):
                if username in st.session_state["users"] and st.session_state["users"][username] == password:
                    st.session_state["logged_in"] = True
                    st.session_state["current_user"] = username
                    save_data()
                    st.success("Login successful!")
                    st.rerun()
                else:
                    st.error("Invalid username or password, please try again.")
                    
        else:  # Sign Up mode
            new_user = st.text_input("Choose a Username", key="signup_user")
            new_pass = st.text_input("Choose a Password", type="password", key="signup_pass")
            confirm_pass = st.text_input("Confirm Password", type="password", key="signup_confirm")
            
            if st.button("Sign Up & Enter", use_container_width=True):
                if not new_user or not new_pass:
                    st.error("Username and password cannot be empty!")
                elif new_user in st.session_state["users"]:
                    st.error("Username already exists, please log in directly!")
                elif new_pass != confirm_pass:
                    st.error("Passwords do not match!")
                else:
                    st.session_state["users"][new_user] = new_pass
                    st.session_state["logged_in"] = True
                    st.session_state["current_user"] = new_user
