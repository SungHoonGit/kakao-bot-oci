#!/usr/bin/env bash
set -euo pipefail

echo "=== Kakao Bot OCI 배포 스크립트 ==="
DOMAIN="${1:-}"

# --- 시스템 패키지 ---
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-venv python3-pip apache2 certbot python3-certbot-apache git

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

# --- Apache 설정 ---
sudo a2enmod proxy proxy_http
sudo cp deploy/apache.conf /etc/apache2/sites-available/kakao-bot.conf
sudo a2dissite 000-default.conf 2>/dev/null || true
sudo a2ensite kakao-bot.conf

# SSL (도메인 있는 경우)
if [ -n "$DOMAIN" ]; then
    sudo certbot --apache -d "$DOMAIN" --non-interactive --agree-tos -m "admin@$DOMAIN" || true
fi

sudo systemctl reload apache2

# --- systemd 서비스 ---
sudo cp deploy/kakao-bot.service /etc/systemd/system/kakao-bot.service
sudo systemctl daemon-reload
sudo systemctl enable kakao-bot
sudo systemctl start kakao-bot

echo ""
echo "=== 배포 완료! ==="
echo "sudo systemctl status kakao-bot    # 봇 서버 상태"
echo "sudo systemctl status apache2      # 아파치 상태"
echo ""
