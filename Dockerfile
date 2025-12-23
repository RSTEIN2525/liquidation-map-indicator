# Use a lightweight Python image
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Copy requirements and install them
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy your source code into the container
COPY src/ ./src/

# Command to run the server
# host 0.0.0.0 is required for Cloud Run
# port 8080 is the default GCP port
# Note: Using src.api:app as our entry point
CMD ["uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "8080"]

