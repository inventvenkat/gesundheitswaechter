import os
import time
import threading
import logging
import requests
from flask import Flask, jsonify
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)

# Configuration from environment variables
HEALTH_CHECK_URLS_STR = os.environ.get('HEALTH_CHECK_URLS', '')
HEALTH_CHECK_INTERVAL_SECONDS = int(os.environ.get('HEALTH_CHECK_INTERVAL_SECONDS', 5))
HEALTH_CHECK_TIMEOUT_SECONDS = int(os.environ.get('HEALTH_CHECK_TIMEOUT_SECONDS', 2))

# Parse URLs and assign priorities
URLS_WITH_PRIORITY = []
if HEALTH_CHECK_URLS_STR:
    for i, url in enumerate(HEALTH_CHECK_URLS_STR.split(',')):
        URLS_WITH_PRIORITY.append({'url': url.strip(), 'priority': i + 1, 'healthy': False, 'last_checked': None})

if not URLS_WITH_PRIORITY:
    logging.error("No URLs provided in HEALTH_CHECK_URLS environment variable. Exiting.")
    # In a real scenario, you might want to exit or handle this more gracefully
    # For this example, we'll let it run but it won't do much.

# Log startup configuration
logging.info(f"Gesundheitswächter (Health Guardian) 🛡️ starting up...")
logging.info(f"Health Check Interval: {HEALTH_CHECK_INTERVAL_SECONDS} seconds")
logging.info(f"Health Check Timeout: {HEALTH_CHECK_TIMEOUT_SECONDS} seconds")
if URLS_WITH_PRIORITY:
    logging.info("Monitoring the following URLs (Priority: URL):")
    for item in URLS_WITH_PRIORITY:
        logging.info(f"  P{item['priority']}: {item['url']}")
else:
    logging.info("No URLs configured for monitoring.")

# Global state for the highest priority healthy URL
current_healthy_url_info = {"url": None, "priority": float('inf')}
health_status_lock = threading.Lock()

def check_url_health(url_info):
    """Checks the health of a single URL."""
    url = url_info['url']
    is_currently_healthy = False
    status_code = None
    error_message = None

    try:
        response = requests.get(url, timeout=HEALTH_CHECK_TIMEOUT_SECONDS)
        status_code = response.status_code
        if 200 <= status_code < 300:
            is_currently_healthy = True
        else:
            error_message = f"HTTP {status_code}"
    except requests.exceptions.Timeout:
        error_message = "Timeout"
    except requests.exceptions.RequestException as e:
        error_message = f"RequestException: {str(e)}"
    except Exception as e:
        error_message = f"Unexpected error: {str(e)}"

    url_info['last_checked'] = datetime.utcnow().isoformat()

    if is_currently_healthy:
        logging.info(f"Health check SUCCESS for {url} (P{url_info['priority']}): HTTP {status_code}")
        return True
    else:
        logging.warning(f"Health check FAILED for {url} (P{url_info['priority']}): {error_message if error_message else 'Unknown reason'}")
        return False

def update_overall_health_status():
    """
    Updates the global health status based on individual URL checks.
    This function should be called after health_info_list is updated.
    """
    global current_healthy_url_info
    
    new_highest_priority_healthy_url = None
    highest_priority_so_far = float('inf')

    with health_status_lock:
        # Sort by priority to check in order
        sorted_urls = sorted(URLS_WITH_PRIORITY, key=lambda x: x['priority'])
        
        for url_info in sorted_urls:
            if url_info['healthy']:
                if url_info['priority'] < highest_priority_so_far:
                    highest_priority_so_far = url_info['priority']
                    new_highest_priority_healthy_url = url_info['url']
        
        old_healthy_url = current_healthy_url_info['url']
        
        if new_highest_priority_healthy_url:
            current_healthy_url_info['url'] = new_highest_priority_healthy_url
            current_healthy_url_info['priority'] = highest_priority_so_far
            if old_healthy_url != new_highest_priority_healthy_url:
                logging.info(f"Primary healthy endpoint changed. New primary: {new_highest_priority_healthy_url} (P{highest_priority_so_far})")
        else:
            current_healthy_url_info['url'] = None
            current_healthy_url_info['priority'] = float('inf')
            if old_healthy_url is not None:
                logging.warning("All endpoints are down. No healthy URL available.")


def perform_health_checks():
    """Periodically checks the health of all configured URLs."""
    if not URLS_WITH_PRIORITY:
        logging.info("Health check thread started, but no URLs to monitor.")
        return

    logging.info("Health check monitoring thread started.")
    while True:
        for url_info in URLS_WITH_PRIORITY:
            is_healthy = check_url_health(url_info)
            with health_status_lock:
                url_info['healthy'] = is_healthy
        
        update_overall_health_status()
        time.sleep(HEALTH_CHECK_INTERVAL_SECONDS)

@app.route('/healthy-endpoint', methods=['GET'])
@app.route('/status', methods=['GET'])
def get_healthy_endpoint():
    """API endpoint to get the highest priority healthy URL."""
    with health_status_lock:
        if current_healthy_url_info['url']:
            return jsonify({"healthy_url": current_healthy_url_info['url']}), 200
        else:
            return jsonify({"status": "all_endpoints_down", "message": "No healthy endpoints available."}), 503

if __name__ == '__main__':
    if not URLS_WITH_PRIORITY:
        logging.warning("Application starting without any URLs configured. The /healthy-endpoint will report no healthy URLs.")
    
    # Start the health checking thread
    health_check_thread = threading.Thread(target=perform_health_checks, daemon=True)
    health_check_thread.start()
    
    # Run Flask app
    # Use 0.0.0.0 to make it accessible from outside the container
    app.run(host='0.0.0.0', port=5000)
