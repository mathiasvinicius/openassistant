#!/bin/bash

# Instala o daemon do WhatsApp Monitor como serviço systemd (v3 com PID-Safe)

set -e

WORKSPACE="/home/node/.openclaw/workspace"
SKILLS_DIR="$WORKSPACE/skills/wacli-monitor"
SCRIPTS_DIR="$SKILLS_DIR/scripts"
SERVICE_FILE="/etc/systemd/system/wacli-daemon.service"
LOG_DIR="$WORKSPACE/logs/wacli"
USER="node"

echo "📦 Instalando WhatsApp Monitor Daemon v3 (PID-Safe)..."

# 0. Cleanup: matar instâncias antigas e remover lock
echo "🧹 Limpando instâncias antigas..."
pkill -f "wacli-daemon" || true
pkill -f "wacli-notify-changes" || true
sleep 1

mkdir -p "$LOG_DIR"
rm -f "$LOG_DIR/.daemon.pid" "$LOG_DIR/LOCK"
echo "✓ Lock files removidos"

# 1. Usar v3 e tornar executável
cp "$SCRIPTS_DIR/wacli-daemon-v3.py" "$SCRIPTS_DIR/wacli-daemon.py"
chmod +x "$SCRIPTS_DIR/wacli-daemon.py"
echo "✓ Script v3 ativado e executável"

# 2. Criar arquivo de serviço
sudo tee "$SERVICE_FILE" > /dev/null << EOF
[Unit]
Description=WhatsApp Monitor Daemon (wacli)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$WORKSPACE
Environment="PATH=/usr/local/bin:/usr/bin:/bin:/usr/local/sbin:/usr/sbin:/sbin"
ExecStart=$SCRIPTS_DIR/wacli-daemon.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
Environment="PYTHONUNBUFFERED=1"

[Install]
WantedBy=multi-user.target
EOF

echo "✓ Serviço criado em $SERVICE_FILE"

# 3. Recarregar systemd
sudo systemctl daemon-reload
echo "✓ Systemd recarregado"

# 4. Habilitar e iniciar
sudo systemctl enable wacli-daemon.service
echo "✓ Serviço habilitado"

sudo systemctl start wacli-daemon.service
echo "✓ Serviço iniciado"

# 5. Status
echo ""
echo "📊 Status:"
sudo systemctl status wacli-daemon.service --no-pager

echo ""
echo "✅ Instalação completa!"
echo ""
echo "Comandos úteis:"
echo "  sudo systemctl status wacli-daemon"
echo "  sudo systemctl restart wacli-daemon"
echo "  sudo journalctl -u wacli-daemon -f"
echo "  sudo systemctl stop wacli-daemon"
