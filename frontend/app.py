import streamlit as st
import requests

st.title("💬 Legal RAG Assistant")

user_input = st.chat_input("Scrivi la tua domanda legale...")
if user_input:
    with st.spinner("Sto ragionando..."):
        res = requests.post("http://localhost:8000/chat/", json={"prompt": user_input})
        st.markdown(res.json()["answer"])