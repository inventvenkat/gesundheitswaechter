# Gesundheitswächter (Health Guardian) 🛡️

Gesundheitswächter is a lightweight, Dockerized component that continuously monitors a prioritized list of URLs. It identifies and returns the highest-priority healthy URL, designed to facilitate active-passive failover in multi-region setups.

## Core Features

-   **URL Input & Prioritization**: Accepts a comma-separated list of URLs via the `HEALTH_CHECK_URLS` environment variable. Priority is determined by the order in the list.
-   **Health Check Mechanism**: Periodically checks each URL for an HTTP 2xx status code. Interval and timeout are configurable.
-   **HTTP API Endpoint**: Exposes `/healthy-endpoint` (or `/status`) to return the current highest-priority healthy URL in JSON format.
-   **Logging**: Provides basic logging for startup, health checks, and status changes.
-   **Dockerized**: Easily buildable and runnable as a Docker container.

## Configuration

The component is configured using environment variables:

-   `HEALTH_CHECK_URLS` (required): A comma-separated string of URLs to monitor.
    -   Example: `"http://region1.example.com/health,http://region2.example.com/api/status,http://region3.backup.com/ping"`
    -   The first URL has the highest priority (P1), the second is P2, and so on.
-   `HEALTH_CHECK_INTERVAL_SECONDS` (optional): The interval in seconds between health checks for each URL.
    -   Default: `5`
-   `HEALTH_CHECK_TIMEOUT_SECONDS` (optional): The timeout in seconds for each HTTP health check request.
    -   Default: `2`
-   `FLASK_APP` (internal): Specifies the entry point for the Flask application.
    -   Default: `app.py` (should not need to be changed for normal operation)
-   `FLASK_RUN_HOST` (internal): Specifies the host the Flask app will listen on.
    -   Default: `0.0.0.0` (to be accessible from outside the container)
-   `FLASK_RUN_PORT` (optional): Specifies the port the Flask app will listen on.
    -   Default: `5000` (as defined by Flask's default and exposed in Dockerfile)

## Setup and Usage

### Prerequisites

-   Docker installed and running on your system.

### 1. Build the Docker Image

Navigate to the directory containing the `Dockerfile`, `app.py`, and `requirements.txt`. Run the following command:

```bash
docker build -t gesundheitswaechter .
```

This will build the Docker image and tag it as `gesundheitswaechter`.

### 2. Run the Docker Container

To run the container, you need to provide the `HEALTH_CHECK_URLS` environment variable. You can also override other optional environment variables.

**Example:**

```bash
docker run -d -p 5000:5000 \
  -e HEALTH_CHECK_URLS="http://mock-server-1:8080/health,http://mock-server-2:8081/status,http://nonexistent.example.com/ping" \
  -e HEALTH_CHECK_INTERVAL_SECONDS=10 \
  --name health-guardian \
  gesundheitswaechter
```

**Explanation of flags:**

-   `-d`: Run the container in detached mode (in the background).
-   `-p 5000:5000`: Map port 5000 on the host to port 5000 in the container (where the Flask app runs).
-   `-e HEALTH_CHECK_URLS=...`: Sets the URLs to monitor. **Replace with your actual URLs.**
-   `-e HEALTH_CHECK_INTERVAL_SECONDS=10`: (Optional) Sets the health check interval to 10 seconds.
-   `--name health-guardian`: (Optional) Assigns a name to the running container for easier management.
-   `gesundheitswaechter`: The name of the Docker image to use.

**Note on URLs:** If you are testing locally with other Docker containers (e.g., mock servers), ensure they are on the same Docker network or use appropriate hostnames/IPs accessible from the `gesundheitswaechter` container.

### 3. Access the Health Status Endpoint

Once the container is running, you can query its status endpoint:

```bash
curl http://localhost:5000/healthy-endpoint
```

Or, using a browser, navigate to `http://localhost:5000/healthy-endpoint` (or `http://localhost:5000/status`).

**Example Responses:**

-   If a healthy URL is found:
    ```json
    {
      "healthy_url": "http://mock-server-1:8080/health"
    }
    ```

-   If no URLs are healthy:
    ```json
    {
      "status": "all_endpoints_down",
      "message": "No healthy endpoints available."
    }
    ```
    (This will be returned with an HTTP 503 status code.)

### 4. View Logs

To view the logs from the running container:

```bash
docker logs health-guardian
```

(Replace `health-guardian` with your container name or ID if you didn't specify one or used a different name.)

## Development

1.  Clone the repository (if applicable) or ensure you have `app.py`, `requirements.txt`, and `Dockerfile`.
2.  Install dependencies locally (optional, for direct execution without Docker):
    ```bash
    pip install -r requirements.txt
    ```
3.  Run the Flask app directly (ensure environment variables are set in your shell):
    ```bash
    export HEALTH_CHECK_URLS="http://localhost:8000/health,http://localhost:8001/status"
    # export other variables as needed
    python app.py
    ```

This will start the Flask development server.

## Testing the Application

To thoroughly test Gesundheitswächter, you can set up simple mock HTTP servers that simulate your actual services.

### 1. Create Mock HTTP Servers (Example using Python)

You can create one or more simple Python Flask applications to act as mock servers. Save each in a separate file (e.g., `mock_server_1.py`, `mock_server_2.py`).

**Example `mock_server_1.py` (Healthy):**

```python
from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/health')
def health_check():
    return jsonify(status="ok"), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080) # Expose on port 8080
```

**Example `mock_server_2.py` (Initially Healthy, can be made unhealthy):**

```python
from flask import Flask, jsonify
import os

app = Flask(__name__)

# Simulate health status, can be changed by an env var or by modifying the file
# For simplicity, we'll make it always healthy here, but you can add logic
# to make it fail based on some condition for testing failover.
@app.route('/status')
def health_check():
    # To simulate failure, you could change this to return 500
    return jsonify(status="ready"), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8081) # Expose on port 8081
```

### 2. Run Mock Servers in Docker (Optional but Recommended)

For easier networking with the `gesundheitswaechter` container, run your mock servers in Docker as well.

**Dockerfile for mock servers (e.g., `Dockerfile.mock`):**
```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY . /app
RUN pip install Flask
# Adjust CMD based on which mock server you are building
# CMD ["python", "mock_server_1.py"]
# CMD ["python", "mock_server_2.py"]
```

Build and run each mock server:
```bash
# For mock_server_1.py (assuming it's in a directory 'mock1')
# Create Dockerfile.mock in 'mock1' with CMD ["python", "mock_server_1.py"]
# cd mock1
# docker build -t mock-server-1 -f Dockerfile.mock .
# docker run -d --name mock1-container -p 8080:8080 mock-server-1
# cd ..

# For mock_server_2.py (assuming it's in a directory 'mock2')
# Create Dockerfile.mock in 'mock2' with CMD ["python", "mock_server_2.py"]
# cd mock2
# docker build -t mock-server-2 -f Dockerfile.mock .
# docker run -d --name mock2-container -p 8081:8081 mock-server-2
# cd ..
```
**Networking Note:** If running mock servers as Docker containers, you can use their container names as hostnames in `HEALTH_CHECK_URLS` if they are on the same Docker network. Create a custom Docker network:
```bash
docker network create healthcheck-net
```
Then run your mock servers and `gesundheitswaechter` on this network:
```bash
# Example for mock server 1
docker run -d --name mock1-container --network healthcheck-net -p 8080:8080 mock-server-1
# Example for mock server 2
docker run -d --name mock2-container --network healthcheck-net -p 8081:8081 mock-server-2

# And for Gesundheitswächter
docker run -d -p 5000:5000 \
  --network healthcheck-net \
  -e HEALTH_CHECK_URLS="http://mock1-container:8080/health,http://mock2-container:8081/status,http://nonexistent.example.com/ping" \
  --name health-guardian \
  gesundheitswaechter
```
If not using a custom network and mock servers are run via `docker run -p <host_port>:<container_port>`, you might need to use `host.docker.internal` (on Docker Desktop) or your machine's IP address for the URLs if `gesundheitswaechter` needs to reach them via the host. For simplicity, using a shared Docker network is recommended.

### 3. Run Gesundheitswächter

Build the `gesundheitswaechter` image if you haven't already:
```bash
docker build -t gesundheitswaechter .
```

Run the `gesundheitswaechter` container, pointing `HEALTH_CHECK_URLS` to your mock servers.
If using the Docker network `healthcheck-net` and container names `mock1-container`, `mock2-container`:
```bash
docker run -d -p 5000:5000 \
  --network healthcheck-net \
  -e HEALTH_CHECK_URLS="http://mock1-container:8080/health,http://mock2-container:8081/status,http://unreachable-mock.com/status" \
  -e HEALTH_CHECK_INTERVAL_SECONDS=5 \
  --name health-guardian \
  gesundheitswaechter
```
If your mock servers are running directly on your host machine (e.g., `python mock_server_1.py`) and accessible via `localhost`:
You might need to use `host.docker.internal` (on Docker Desktop for Windows/Mac) or your host's IP address in `HEALTH_CHECK_URLS`.
Example for Docker Desktop:
```bash
docker run -d -p 5000:5000 \
  -e HEALTH_CHECK_URLS="http://host.docker.internal:8080/health,http://host.docker.internal:8081/status" \
  --name health-guardian \
  gesundheitswaechter
```

### 4. Observe Behavior

-   **Check Logs**:
    ```bash
    docker logs -f health-guardian
    docker logs -f mock1-container # If running mock server in Docker
    ```
    You should see logs from `gesundheitswaechter` indicating startup configuration and health check attempts.

-   **Query Endpoint**:
    ```bash
    curl http://localhost:5000/healthy-endpoint
    ```
    Initially, it should return the highest priority healthy mock server (e.g., `http://mock1-container:8080/health`).

### 5. Simulate Failures

-   **Stop a Mock Server**:
    ```bash
    docker stop mock1-container # Stop the P1 server
    ```
-   **Observe Logs and Endpoint**:
    -   `gesundheitswaechter` logs should show P1 failing.
    -   After a short delay (based on `HEALTH_CHECK_INTERVAL_SECONDS`), querying `http://localhost:5000/healthy-endpoint` should now return the P2 server (e.g., `http://mock2-container:8081/status`).

-   **Stop All Mock Servers**:
    ```bash
    docker stop mock2-container # Stop the P2 server as well
    ```
-   **Observe Logs and Endpoint**:
    -   `gesundheitswaechter` logs should show P2 failing.
    -   Querying `http://localhost:5000/healthy-endpoint` should now return:
        ```json
        {
          "status": "all_endpoints_down",
          "message": "No healthy endpoints available."
        }
        ```

-   **Restart a Mock Server**:
    ```bash
    docker start mock1-container # Bring P1 back online
    ```
-   **Observe Logs and Endpoint**:
    -   `gesundheitswaechter` logs should show P1 becoming healthy again.
    -   Querying `http://localhost:5000/healthy-endpoint` should revert to P1.

This testing process allows you to verify the core logic of prioritization and failover.

---

This completes the initial setup for Gesundheitswächter.
