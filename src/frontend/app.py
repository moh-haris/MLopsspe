import streamlit as st
import requests
import os

# Get backend URL from the docker-compose environment
BACKEND_URL = os.getenv("BACKEND_URL", "http://backend-service:8000")

st.set_page_config(page_title="SecureNOC Assistant", page_icon="📡")
st.title("📡 SecureNOC: Telecom SOP Assistant")

if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# User input
if prompt := st.chat_input("E.g., How do I fix a BGP flap on a Cisco ASR?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Querying SecureNOC API..."):
            try:
                response = requests.post(f"{BACKEND_URL}/ask", json={"question": prompt})
                if response.status_code == 200:
                    data = response.json()
                    answer = data["answer"]
                    sources = data.get("sources", [])
                    
                    st.markdown(answer)
                    if sources:
                        st.caption(f"**Sources utilized:** {', '.join(sources)}")
                        
                    st.session_state.messages.append({"role": "assistant", "content": answer})
                else:
                    st.error(f"API Error: {response.status_code} - {response.text}")
            except requests.exceptions.ConnectionError:
                st.error("🚨 Critical: Could not connect to the Backend API. Is the container running?")