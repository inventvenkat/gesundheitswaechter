# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
# (We'll create a requirements.txt next, for now, this is a placeholder if needed)
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the current directory contents into the container at /app
COPY . .

# Make port 5000 available to the world outside this container
EXPOSE 5000

# Define environment variables with default values (can be overridden at runtime)
ENV HEALTH_CHECK_URLS=""
ENV HEALTH_CHECK_INTERVAL_SECONDS=5
ENV HEALTH_CHECK_TIMEOUT_SECONDS=2
ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0

# Run app.py when the container launches
CMD ["flask", "run"]
