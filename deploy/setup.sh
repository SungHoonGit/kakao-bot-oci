#!/usr/bin/env bash
set -euo pipefail

echo "=== Kakao Bot OCI 배포 스크립트 ==="
DOMAIN="${1:-}"

# --- 시스템 패키지 ---
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-venv python3-pip nginx certbot python3-certbot-nginx git

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
    echo ">>> config.json 을 생성해야 합니다. REST API 키를 입력하세요."
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

# --- nginx 설정 ---
if [ -n "$DOMAIN" ]; then
    sudo certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos -m "admin@$DOMAIN" || true
fi

# nginx config 복사
sudo cp deploy/nginx.conf /etc/nginx/sites-available/kakao-bot
sudo ln -sf /etc/nginx/sites-available/kakao-bot /etc/nginx/sites-enabled/
# nginx.conf의 YOUR_DOMAIN을 실제 도메인으로 치환 (도메인 없는 경우 IP 사용)
if [ -n "$DOMAIN" ]; then
    sudo sed -i "s/YOUR_DOMAIN/$DOMAIN/g" /etc/nginx/sites-available/kakao-bot
else
    # 도메인 없으면 SSL 없이 80 only
    sudo tee /etc/nginx/sites-available/kakao-bot > /dev/null <<'EOF'
upstream kakao_bot {
    server 127.0.0.1:5000;
}
server {
    listen 80;
    server_name _;
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

# --- systemd 서비스 ---
sudo cp deploy/kakao-bot.service /etc/systemd/system/kakao-bot.service
sudo systemctl daemon-reload
sudo systemctl enable kakao-bot
sudo systemctl start kakao-bot

# --- 방화벽 (Oracle Cloud VCN에서도 허용 필요) ---
sudo ufw allow 80/tcp 2>/dev/null || true
sudo ufw allow 443/tcp 2>/dev/null || true

echo ""
echo "=== 배포 완료! ==="
echo "sudo systemctl status kakao-bot  # 상태 확인"
echo ""
