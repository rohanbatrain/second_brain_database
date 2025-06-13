# Use a lightweight base image for production
FROM python:3.9-slim as base

# Set the working directory inside the container
WORKDIR /app

# Copy only requirements to leverage Docker cache
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create a non-root user and group named sbd_user with home directory
RUN groupadd -r sbd_user && useradd -r -g sbd_user -d /sbd_user -m sbd_user

# Set ownership of the working directory
RUN chown -R sbd_user:sbd_user /app

# Copy the entire project into the container
COPY . .

# Ensure all files are owned by sbd_user after copy
RUN chown -R sbd_user:sbd_user /app

# Install your package (assuming setup.py or pyproject.toml exists)
RUN pip install .

# Switch to the non-root user
USER sbd_user

# Set HOME environment variable for sbd_user
ENV HOME=/sbd_user

# Expose the port
EXPOSE 5000

# Use Gunicorn for production with optimized settings
CMD ["gunicorn", "--workers=3", "--threads=2", "--bind", "0.0.0.0:5000", "second_brain_database.main:app"]