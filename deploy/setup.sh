#!/usr/bin/env bash
set -euo pipefail

echo "=== Kakao Bot OCI 배포 스크립트 ==="
DOMAIN="${1:-}"
WEB="${2:-apache}"   # apache (default) or nginx

# --- 시스템 패키지 ---
sudo apt update && sudo apt upgrade -y
PKGS="python3 python3-venv python3-pip git"
if [ "$WEB" = "nginx" ]; then
    PKGS="$PKGS nginx certbot python3-certbot-nginx"
else
    PKGS="$PKGS apache2 certbot python3-certbot-apache"
fi
sudo apt install -y $PKGS

# --- 프로젝트 클론 ---
if [ ! -d /home/ubuntu/kakao-bot-oci ]; then
    cd /home/ubuntu
    git clone https://github.com/SungHoonGit/kakao-bot-oci.git
fi
cd /home/ubuntu/kakao-bot-oci

# --- Python 가상환경 ---
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install gunicorn

# --- config.json ---
if [ ! -f config.json ]; then
    echo ""
    echo ">>> config.json 을 생성합니다. REST API 키를 입력하세요."
    echo -n "REST API Key: "
    read -r KEY
    cat > config.json << EOF
{
  "kakao": {
    "rest_api_key": "$KEY"
  }
}
EOF
fi

# --- 웹 서버 설정 ---
if [ "$WEB" = "nginx" ]; then
    echo ">>> nginx 설정 중..."
    sudo cp deploy/nginx.conf /etc/nginx/sites-available/kakao-bot
    sudo ln -sf /etc/nginx/sites-available/kakao-bot /etc/nginx/sites-enabled/
    if [ -n "$DOMAIN" ]; then
        sudo sed -i "s/YOUR_DOMAIN/$DOMAIN/g" /etc/nginx/sites-available/kakao-bot
        sudo certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos -m "admin@$DOMAIN" || true
    else
        # 도메인 없음 → SSL 없이 80 only
        sudo tee /etc/nginx/sites-available/kakao-bot > /dev/null <<'EOF'
upstream kakao_bot { server 127.0.0.1:5000; }
server {
    listen 80; server_name _;
    location / {
        proxy_pass http://kakao_bot;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
EOF
    fi
    sudo nginx -t && sudo systemctl reload nginx
else
    echo ">>> Apache 설정 중..."
    sudo a2enmod proxy proxy_http
    sudo cp deploy/apache.conf /etc/apache2/sites-available/kakao-bot.conf
    sudo a2dissite 000-default.conf 2>/dev/null || true
    sudo a2ensite kakao-bot.conf
    if [ -n "$DOMAIN" ]; then
        sudo certbot --apache -d "$DOMAIN" --non-interactive --agree-tos -m "admin@$DOMAIN" || true
    fi
    sudo systemctl reload apache2
fi

# --- systemd 서비스 ---
sudo cp deploy/kakao-bot.service /etc/systemd/system/kakao-bot.service
sudo systemctl daemon-reload
sudo systemctl enable kakao-bot
sudo systemctl start kakao-bot

echo ""
echo "=== 배포 완료! (WEB=$WEB) ==="
echo "sudo systemctl status kakao-bot    # 봇 서버"
echo "sudo systemctl status $WEB         # 웹 서버"
echo ""
