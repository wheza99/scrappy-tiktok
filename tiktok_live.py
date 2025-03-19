from TikTokLive import TikTokLiveClient
from TikTokLive.events import ConnectEvent, CommentEvent
import requests
import datetime
import threading
import asyncio
import signal
import sys

# Constants
# WEBHOOK_URL = "https://wheza.app.n8n.cloud/webhook-test/46d6bdb2-4b1a-4e08-af30-fe9274041a31" #test
WEBHOOK_URL = "https://wheza.app.n8n.cloud/webhook/46d6bdb2-4b1a-4e08-af30-fe9274041a31" #production
BATCH_INTERVAL_SECONDS = 30.0
TIKTOK_USERNAME = "@bnb.shop"

# Variable to store collected comments
collected_comments = []
# Lock for thread safety when modifying the collected_comments list
comments_lock = threading.Lock()

# Timer object to keep track of the current timer
comment_timer = None

# Create the client - Menggunakan username TikTok yang populer dan mungkin sedang live
client = None
client_running = False
client_thread = None

# Listen to an event dengan decorator
def setup_client(unique_id=TIKTOK_USERNAME):
    global client, client_running, client_thread
    
    # Clean up any existing client
    if client:
        try:
            # Force terminate the client
            client_running = False
            if client_thread and client_thread.is_alive():
                client_thread = None
        except:
            pass
    
    client_running = True
    client = TikTokLiveClient(unique_id=unique_id)
    
    @client.on(ConnectEvent)
    async def on_connect(event: ConnectEvent):
        print(f"Connected to @{event.unique_id} (Room ID: {client.room_id})")
        # Start the timer to send comments every interval seconds
        start_comment_sender()
    
    # Add comment listener
    client.add_listener(CommentEvent, on_comment)
    
    return client

# Dan juga bisa menambahkan listener secara manual
async def on_comment(event: CommentEvent) -> None:
    if not client_running:
        return
        
    username = event.user.nickname
    comment = event.comment
    timestamp = datetime.datetime.now().isoformat()
    print(f"{username} -> {comment}")
    
    # Collect the comment in our global variable
    with comments_lock:
        collected_comments.append({
            "username": username,
            "comment": comment,
            "timestamp": timestamp
        })

# Send collected comments to the webhook endpoint
def send_webhook(comments_batch, webhook_url=WEBHOOK_URL):
    if not comments_batch:
        return  # Don't send if there are no comments
        
    try:
        payload = {
            "username": TIKTOK_USERNAME,
            "comments": comments_batch
        }
        response = requests.post(webhook_url, json=payload)
        if response.status_code == 200:
            print(f"Webhook sent successfully: {len(comments_batch)} comments")
            print(f"Response content: {response.text}")
        else:
            print(f"Failed to send webhook: {response.status_code}")
            print(f"Response content: {response.text}")
    except Exception as e:
        print(f"Error sending webhook: {e}")

# Send all collected comments to the webhook and clear the collection
def send_collected_comments(interval=BATCH_INTERVAL_SECONDS, webhook_url=WEBHOOK_URL):
    global collected_comments, comment_timer
    
    # If client is not running anymore, don't schedule another timer
    if not client_running:
        return
        
    with comments_lock:
        comments_to_send = collected_comments.copy()
        collected_comments = []
    
    if comments_to_send:
        send_webhook(comments_to_send, webhook_url)
    
    # Schedule the next execution only if client is still running
    if client_running:
        comment_timer = threading.Timer(interval, lambda: send_collected_comments(interval, webhook_url))
        comment_timer.daemon = True
        comment_timer.start()

# Start the first timer
def start_comment_sender(interval=BATCH_INTERVAL_SECONDS, webhook_url=WEBHOOK_URL):
    global comment_timer
    if comment_timer:
        comment_timer.cancel()
    comment_timer = threading.Timer(interval, lambda: send_collected_comments(interval, webhook_url))
    comment_timer.daemon = True
    comment_timer.start()

# Stop the timer and clear resources
def stop_comment_sender():
    global comment_timer, client_running, collected_comments
    
    # Set client_running to False to prevent new timers from being scheduled
    client_running = False
    
    # Cancel the current timer if it exists
    if comment_timer:
        comment_timer.cancel()
        comment_timer = None
    
    # Clear collected comments
    with comments_lock:
        collected_comments = []
    
    print("Comment sender stopped and resources cleared")

# Disconnect the client and clean up resources
def disconnect_client():
    global client, client_running, client_thread
    
    # Stop the comment sender first
    stop_comment_sender()
    
    # Set client_running to False
    client_running = False
    
    # Force kill the client process
    if client:
        try:
            # Force terminate the client
            print("TikTok client disconnected")
            
            # Force Python to exit the client thread
            if client_thread and client_thread.is_alive():
                # We can't directly kill a thread in Python, but we can set a flag
                # that the thread should check and exit if set
                client_thread = None
            
            # Set client to None to allow garbage collection
            client = None
            
            # Force a garbage collection to clean up resources
            import gc
            gc.collect()
            
        except Exception as e:
            print(f"Error disconnecting client: {e}")
            client = None

# Run the client in a separate thread
def run_client_in_thread(client_to_run):
    global client_running, client_thread
    
    client_thread = threading.current_thread()
    
    try:
        client_to_run.run()
    except Exception as e:
        print(f"Error in client thread: {e}")
    finally:
        client_running = False
        print("Client thread exited")

if __name__ == '__main__':
    # Setup and run the client
    client = setup_client(TIKTOK_USERNAME)
    # Run the client and block the main thread
    # await client.start() to run non-blocking
    try:
        client_thread = threading.Thread(target=run_client_in_thread, args=(client,))
        client_thread.start()
        client_thread.join()
    except KeyboardInterrupt:
        disconnect_client()
        print("Application stopped by user")
