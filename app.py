# Copyright 2025 Venkatesh Sumathi Devendran
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

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
WEBHOOK_URL = os.environ.get('WEBHOOK_URL', None) # New environment variable for webhook

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
if WEBHOOK_URL:
    logging.info(f"Webhook URL configured: {WEBHOOK_URL}")
else:
    logging.info("No Webhook URL configured.")
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

    url_info['last_checked'] = datetime.utcnow().isoformat() # Store as ISO format string

    if is_currently_healthy:
        logging.info(f"Health check SUCCESS for {url} (P{url_info['priority']}): HTTP {status_code}")
        return True
    else:
        logging.warning(f"Health check FAILED for {url} (P{url_info['priority']}): {error_message if error_message else 'Unknown reason'}")
        return False

def update_overall_health_status():
    """
    Updates the global health status based on individual URL checks.
    Triggers a webhook if the primary healthy URL changes and a webhook URL is configured.
    """
    global current_healthy_url_info
    
    previous_healthy_url = current_healthy_url_info['url'] # Store previous state for comparison
    new_highest_priority_healthy_url = None
    highest_priority_so_far = float('inf')

    with health_status_lock:
        # Log current health states of all monitored URLs for diagnostics
        if URLS_WITH_PRIORITY: # Ensure list is not empty before creating summary
            current_statuses_summary = [(item['url'], item['healthy'], item['priority']) for item in URLS_WITH_PRIORITY]
            logging.info(f"update_overall_health_status: Evaluating current statuses: {current_statuses_summary}")
        else:
            logging.info("update_overall_health_status: No URLs configured to evaluate.")

        # Sort by priority to check in order
        sorted_urls = sorted(URLS_WITH_PRIORITY, key=lambda x: x['priority'])
        
        for url_info in sorted_urls:
            if url_info['healthy']:
                # Since the list is sorted by priority (ascending),
                # the first healthy URL found is the one with the highest priority.
                if url_info['priority'] < highest_priority_so_far: # This check ensures we take the one with the numerically lowest priority
                    highest_priority_so_far = url_info['priority']
                    new_highest_priority_healthy_url = url_info['url']
                    break  # Optimization: Found the highest priority healthy URL, no need to check further
        
        old_healthy_url = current_healthy_url_info['url']
        
        if new_highest_priority_healthy_url:
            current_healthy_url_info['url'] = new_highest_priority_healthy_url
            current_healthy_url_info['priority'] = highest_priority_so_far
            if old_healthy_url != new_highest_priority_healthy_url:
                logging.info(f"Primary healthy endpoint changed. New primary: {new_highest_priority_healthy_url} (P{highest_priority_so_far})")
                if WEBHOOK_URL:
                    send_webhook_notification(old_healthy_url, new_highest_priority_healthy_url, highest_priority_so_far)
            else:
                logging.info(f"Primary healthy endpoint remains: {new_highest_priority_healthy_url} (P{highest_priority_so_far})")
        else: # No healthy URL found
            current_healthy_url_info['url'] = None
            current_healthy_url_info['priority'] = float('inf')
            if old_healthy_url is not None: # It means we just lost all healthy URLs
                logging.warning("All endpoints are down. No healthy URL available.")
                if WEBHOOK_URL:
                    send_webhook_notification(old_healthy_url, None, None) # Notify that no URL is healthy
            else:
                logging.info("No healthy URL available (was already None or no URLs configured).")

def send_webhook_notification(old_url, new_url, new_priority):
    """Sends a notification to the configured webhook URL about the change in the healthy endpoint."""
    if not WEBHOOK_URL:
        logging.info("Webhook notification skipped: No WEBHOOK_URL configured.")
        return

    payload = {
        "timestamp": datetime.utcnow().isoformat(),
        "event_type": "healthy_url_changed",
        "previous_healthy_url": old_url,
        "current_healthy_url": new_url,
        "current_healthy_url_priority": new_priority,
        "message": ""
    }

    if new_url:
        payload["message"] = f"Healthy URL changed from '{old_url if old_url else 'None'}' to '{new_url}' (Priority: {new_priority})."
    else:
        payload["message"] = f"All monitored URLs are now unhealthy. Previous healthy URL was '{old_url if old_url else 'None'}'."


    try:
        logging.info(f"Sending webhook notification to {WEBHOOK_URL} with payload: {payload}")
        response = requests.post(WEBHOOK_URL, json=payload, timeout=5) # 5 second timeout for webhook
        response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
        logging.info(f"Webhook notification sent successfully to {WEBHOOK_URL}. Status: {response.status_code}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to send webhook notification to {WEBHOOK_URL}: {e}")
    except Exception as e:
        logging.error(f"An unexpected error occurred while sending webhook to {WEBHOOK_URL}: {e}")


def perform_health_checks():
    """Periodically checks the health of all configured URLs."""
    if not URLS_WITH_PRIORITY:
        logging.info("Health check thread started, but no URLs to monitor.")
        return

    logging.info("Health check monitoring thread started.")
    loop_count = 0
    while True:
        loop_count += 1
        logging.info(f"perform_health_checks: Starting loop iteration {loop_count}.")
        try:
            if not URLS_WITH_PRIORITY: # Re-check in case it became empty, though unlikely with current logic
                logging.warning("perform_health_checks: URLS_WITH_PRIORITY is empty, cannot perform checks. Sleeping.")
                time.sleep(HEALTH_CHECK_INTERVAL_SECONDS)
                continue

            logging.info(f"perform_health_checks: Iterating through {len(URLS_WITH_PRIORITY)} URLs for health checks.")
            for url_info in URLS_WITH_PRIORITY:
                is_healthy = check_url_health(url_info)
                with health_status_lock:
                    url_info['healthy'] = is_healthy
            logging.info("perform_health_checks: Finished iterating through URLs.")
            
            update_overall_health_status()
            
            logging.info(f"perform_health_checks: Sleeping for {HEALTH_CHECK_INTERVAL_SECONDS} seconds before next iteration.")
            time.sleep(HEALTH_CHECK_INTERVAL_SECONDS)
            logging.info("perform_health_checks: Woke up from sleep.")

        except Exception as e:
            logging.error(f"perform_health_checks: Unhandled exception in health check loop: {e}", exc_info=True)
            # Depending on the error, you might want to sleep for a bit before retrying
            # to avoid tight loop of failures.
            logging.info(f"perform_health_checks: Sleeping for {HEALTH_CHECK_INTERVAL_SECONDS} seconds after exception before retrying.")
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
