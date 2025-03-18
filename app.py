import streamlit as st
import threading
import time
import sys
import os

# Add the lib directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import the TikTok live scraper
from lib.scrapping.tiktok_live import (
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
    stop_comment_sender,
    disconnect_client,
    run_client_in_thread
)

# Set page config
st.set_page_config(
    page_title="TikTok Live Scraper",
    page_icon="🎬",
    layout="wide",
)

# Initialize session state
if 'running' not in st.session_state:
    st.session_state.running = False
if 'comment_count' not in st.session_state:
    st.session_state.comment_count = 0
if 'users' not in st.session_state:
    st.session_state.users = set()
if 'comments_data' not in st.session_state:
    st.session_state.comments_data = {
        "Username": [],
        "Comment": [],
        "Timestamp": []
    }

# Global variables for the app
client = None
stop_flag = False
ui_thread = None
client_thread = None

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

if st.session_state.running:
    status.success("Connected and scraping")
else:
    status.info("Ready to connect")

# Main content area
col1, col2 = st.columns([2, 1])

# Comment display area
with col1:
    st.subheader("Live Comments")
    comments_placeholder = st.empty()
    
    # Display current comments
    if st.session_state.comments_data["Username"]:
        comments_placeholder.dataframe(st.session_state.comments_data, use_container_width=True)
    else:
        comments_placeholder.info("No comments yet. Start scraping to collect comments.")

# Stats area
with col2:
    st.subheader("Statistics")
    stats_container = st.container()
    
    # Display current stats
    stats_container.metric("Total Comments", st.session_state.comment_count)
    stats_container.metric("Unique Users", len(st.session_state.users))

# Function to update the UI with comments
def update_ui():
    global stop_flag, collected_comments
    
    while not stop_flag:
        # Create a copy of the current comments for display
        with comments_lock:
            comments_to_display = collected_comments.copy()
            collected_comments = []
        
        # Update stats and comments
        if comments_to_display:
            for comment in comments_to_display:
                # Update session state in the main thread
                st.session_state.comment_count += 1
                st.session_state.users.add(comment["username"])
                
                # Add comment to the display data
                st.session_state.comments_data["Username"].append(comment["username"])
                st.session_state.comments_data["Comment"].append(comment["comment"])
                st.session_state.comments_data["Timestamp"].append(comment["timestamp"])
        
        # Sleep for a short time
        time.sleep(1)

# Start button
if st.sidebar.button("Start Scraping", key="start_button"):
    if not st.session_state.running:
        # Reset stats for a new session
        st.session_state.comment_count = 0
        st.session_state.users = set()
        st.session_state.comments_data = {
            "Username": [],
            "Comment": [],
            "Timestamp": []
        }
        
        # Set up the client
        client = setup_client(tiktok_username)
        stop_flag = False
        
        # Mark as running
        st.session_state.running = True
        
        # Start UI update thread
        ui_thread = threading.Thread(target=update_ui)
        ui_thread.daemon = True
        ui_thread.start()
        
        # Start client in a separate thread using our improved function
        client_thread = threading.Thread(target=run_client_in_thread, args=(client,))
        client_thread.daemon = True
        client_thread.start()
        
        # Force a rerun to update the UI
        st.rerun()

# Stop button
if st.sidebar.button("Stop Scraping", key="stop_button"):
    if st.session_state.running:
        # Set the stop flag for the UI thread
        stop_flag = True
        
        # Disconnect the client and stop comment sender
        disconnect_client()
        
        # Mark as not running
        st.session_state.running = False
        
        # Force a rerun to update the UI
        st.rerun()

# Footer
st.sidebar.markdown("---")
st.sidebar.markdown("### About")
st.sidebar.info(
    """
    This app scrapes comments from TikTok Live streams and sends them to a webhook URL.
    
    The comments are collected in batches and sent at regular intervals.
    """
)
