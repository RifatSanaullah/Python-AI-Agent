#!/bin/bash

# Variables
SERVER_USER="your_username"                 # Your server's username
SERVER_IP="your_server_ip"                   # Your server's IP address
PROJECT_NAME="com.boomershub.ai.agent"       # Your project name
REPO_URL="https://gitlab.com/boom-dev/com.boomershub.ai.agent.git"  # Your repository URL
ENV_FILE=".env"                              # Your environment file
REMOTE_DIR="/home/$SERVER_USER/$PROJECT_NAME"  # Directory on server

# Exit on error
set -e

# Step 1: Transfer files to the server
echo "Transferring files to the server..."
rsync -avz --exclude='venv/' --exclude='.git/' . $SERVER_USER@$SERVER_IP:$REMOTE_DIR

# Step 2: SSH into the server and set up the application
ssh $SERVER_USER@$SERVER_IP << 'ENDSSH'
    # Update system packages
    echo "Updating system packages..."
    sudo apt update && sudo apt upgrade -y

    # Install necessary packages
    echo "Installing required packages..."
    sudo apt install -y python3-pip python3-venv git nginx

    # Navigate to project directory
    cd /home/$USER/com.boomershub.ai.agent

    # Create and activate a virtual environment
    echo "Creating a virtual environment..."
    python3 -m venv venv
    source venv/bin/activate

    # Install dependencies
    echo "Installing Python dependencies..."
    pip install -r requirements.txt

    # Step 3: Configure Nginx
    echo "Configuring Nginx..."
    sudo tee /etc/nginx/sites-available/$PROJECT_NAME << 'EOF'
server {
    listen 80;
    server_name your_server_ip;  # Change this to your server's IP or domain

    location / {
        proxy_pass http://127.0.0.1:8000;  # Forward requests to the FastAPI app
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

    # Enable the new site configuration
    sudo ln -s /etc/nginx/sites-available/$PROJECT_NAME /etc/nginx/sites-enabled/

    # Step 4: Start the FastAPI application
    echo "Starting the FastAPI application..."
    nohup uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload &

    # Restart Nginx to apply the changes
    echo "Restarting Nginx..."
    sudo systemctl restart nginx

    echo "Deployment completed successfully!"
    echo "You can access your application at http://your_server_ip/"
ENDSSH
