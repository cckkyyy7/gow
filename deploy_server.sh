#!/bin/bash

# Configuration
APP_NAME="fortunegod"
APP_DIR=$(pwd)
USER_NAME=$(whoami)
DOMAIN="yourdomain.com" # CHANGE THIS

echo "Starting Deployment for $APP_NAME..."

# Root Check
if [ "$(id -u)" -eq 0 ]; then
    alias sudo=""
    SUDO=""
else
    SUDO="sudo"
fi

# 1. Install System Dependencies
echo "Installing dependencies..."
$SUDO apt-get update
$SUDO apt-get install -y python3-venv python3-pip nginx certbot python3-certbot-nginx

# 2. Setup Python Environment
echo "Setting up Virtual Environment..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate
pip install -r requirements.txt

# 3. Setup Systemd Service for Gunicorn
echo "Creating Systemd Service..."
SERVICE_FILE="/etc/systemd/system/$APP_NAME.service"
sudo bash -c "cat > $SERVICE_FILE" <<EOF
[Unit]
Description=Gunicorn instance to serve $APP_NAME
After=network.target

[Service]
User=$USER_NAME
Group=www-data
WorkingDirectory=$APP_DIR
Environment="PATH=$APP_DIR/.venv/bin"
ENVIRONMENT_FILE=$APP_DIR/.env
ExecStart=$APP_DIR/.venv/bin/gunicorn -c gunicorn_config.py app:app

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable $APP_NAME
sudo systemctl restart $APP_NAME

# 4. Setup Nginx
echo "Configuring Nginx..."
NGINX_CONF="/etc/nginx/sites-available/$APP_NAME"
sudo bash -c "cat > $NGINX_CONF" <<EOF
server {
    listen 80;
    server_name $DOMAIN_NAME;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location /static {
        alias $APP_DIR/static;
    }
}
EOF

# Enable Site
sudo ln -sf $NGINX_CONF /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl restart nginx

# 5. Setup Cron Job
echo "Setting up Cron Job for Daily Updates..."
# Cron command: Run hpr_calculator.py at 00:01 using venv python
CRON_JOB="1 0 * * * cd $APP_DIR && $APP_DIR/.venv/bin/python hpr_calculator.py --run-now >> $APP_DIR/cron_log.txt 2>&1"
(crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -

echo "Deployment Complete!"
echo "Don't forget to configure your .env file with BINANCE secrets!"
echo "Domain configured: $DOMAIN (If you have it, run 'sudo certbot --nginx' to enable HTTPS)"
