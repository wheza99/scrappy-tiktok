import streamlit as st
import threading
import time
import sys
import os

# Add the lib directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import the TikTok live scraper
from tiktok_live import (
    TikTokLiveClient,
    ConnectEvent,
    CommentEvent,
    WEBHOOK_URL,
    BATCH_INTERVAL_SECONDS,
    collected_comments,
    comments_lock,
    setup_client,
    on_comment,
    send_collected_comments,
    start_comment_sender,
    stop_comment_sender
)

# Set page config
st.set_page_config(
    page_title="TikTok Live Scraper",
    page_icon="🎬",
    layout="wide",
)

# Main title
st.title("🎬 TikTok Live Comment Scraper")

# Sidebar for configuration
st.sidebar.header("Configuration")

# Username input
tiktok_username = st.sidebar.text_input("TikTok Username", value="@coach.qiu")

# Batch interval slider
batch_interval = st.sidebar.slider(
    "Batch Interval (seconds)",
    min_value=5,
    max_value=60,
    value=int(BATCH_INTERVAL_SECONDS),
    step=5,
)

# Webhook URL input
webhook_url = st.sidebar.text_input("Webhook URL", value=WEBHOOK_URL)

# Status indicators
status_container = st.sidebar.container()
status = status_container.empty()
status.info("Ready to connect")

# Main content area
col1, col2 = st.columns([2, 1])

# Comment display area
with col1:
    st.subheader("Live Comments")
    comments_placeholder = st.empty()

# Stats area
with col2:
    st.subheader("Statistics")
    stats_placeholder = st.empty()
    
    # Initialize stats
    stats_container = stats_placeholder.container()
    total_comments = stats_container.empty()
    unique_users = stats_container.empty()
    total_comments.metric("Total Comments", 0)
    unique_users.metric("Unique Users", 0)

# Global variables for the app
client = None
stop_event = threading.Event()
is_running = False

# Function to update the UI with comments
def update_ui():
    comment_count = 0
    users_set = set()
    
    while not stop_event.is_set():
        # Create a copy of the current comments for display
        with comments_lock:
            comments_to_display = collected_comments.copy()
            comment_count += len(comments_to_display)
            for comment in comments_to_display:
                users_set.add(comment["username"])
        
        # Update the comments display
        if comments_to_display:
            comments_df = {
                "Username": [],
                "Comment": [],
                "Timestamp": []
            }
            
            for comment in comments_to_display:
                comments_df["Username"].append(comment["username"])
                comments_df["Comment"].append(comment["comment"])
                comments_df["Timestamp"].append(comment["timestamp"])
            
            comments_placeholder.dataframe(comments_df, use_container_width=True)
        else:
            comments_placeholder.info("Waiting for comments...")
        
        # Update stats
        total_comments.metric("Total Comments", comment_count)
        unique_users.metric("Unique Users", len(users_set))
        
        time.sleep(1)

# Start button
if st.sidebar.button("Start Scraping"):
    if not is_running:
        is_running = True
        stop_event.clear()
        status.success("Connected and scraping")
        
        # Create a new client with the provided username
        client = setup_client(tiktok_username)
        
        # Start UI update thread
        ui_thread = threading.Thread(target=update_ui)
        ui_thread.daemon = True
        ui_thread.start()
        
        # Start client in a separate thread
        def run_client():
            try:
                client.run()
            except Exception as e:
                st.error(f"Error: {e}")
                status.error(f"Error: {e}")
        
        client_thread = threading.Thread(target=run_client)
        client_thread.daemon = True
        client_thread.start()

# Stop button
if st.sidebar.button("Stop Scraping"):
    if is_running:
        is_running = False
        stop_event.set()
        stop_comment_sender()
        
        if client:
            client.disconnect()
            client = None
        
        status.info("Disconnected")

# Footer
st.sidebar.markdown("---")
st.sidebar.markdown("### About")
st.sidebar.info(
    """
    This app scrapes comments from TikTok Live streams and sends them to a webhook URL.
    
    The comments are collected in batches and sent at regular intervals.
    """
)
