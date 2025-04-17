# Use the official Python image
FROM python:3.9-slim

# Set the working directory inside the container
WORKDIR /app

# Copy only requirements to leverage Docker cache
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire project into the container
COPY . .

# Install your package (assuming setup.py or pyproject.toml exists)
RUN pip install .

# Expose the port
EXPOSE 5000

# Run the app
CMD ["python3", "-m", "Second_Brain_Database"]
