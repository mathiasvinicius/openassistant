#!/usr/bin/env python3

"""
WhatsApp Monitor - Notify on Changes
Envia áudio resumo SEMPRE que houver atualizações na sincronização
"""

import json
import subprocess
import time
from pathlib import Path
from datetime import datetime
import sys

WORKSPACE = Path.home() / ".openclaw" / "workspace"
LOG_DIR = WORKSPACE / "logs" / "wacli"
STATE_FILE = LOG_DIR / ".notification_state.json"

def load_state():
    """Carrega estado anterior"""
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {
        "last_msg_count": 0,
        "last_notification_time": 0,
        "last_conversation_count": 0
    }

def save_state(state):
    """Salva estado"""
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

def get_current_state():
    """Coleta estado atual do daemon"""
    msg_count = 0
    if (LOG_DIR / "messages.jsonl").exists():
        msg_count = sum(1 for _ in open(LOG_DIR / "messages.jsonl"))
    
    notification_time = 0
    if (LOG_DIR / "daemon.log").exists():
        for line in open(LOG_DIR / "daemon.log"):
            if "Notificação enviada" in line:
                notification_time = time.time()
    
    return {
        "msg_count": msg_count,
        "last_notification": notification_time,
        "timestamp": time.time()
    }

def detect_changes(previous, current):
    """Detecta se houve mudanças significativas"""
    changes = []
    
    # Novas mensagens processadas?
    if current["msg_count"] > previous["last_msg_count"]:
        delta = current["msg_count"] - previous["last_msg_count"]
        changes.append(f"msg:{delta}")
    
    # Novas notificações enviadas?
    if current["last_notification"] > previous["last_notification_time"]:
        changes.append("notif:sent")
    
    return changes

def generate_audio_summary(changes):
    """Gera áudio resumo baseado nas mudanças"""
    if not changes:
        return None
    
    parts = []
    
    for change in changes:
        if change.startswith("msg:"):
            count = int(change.split(":")[1])
            if count == 1:
                parts.append(f"Uma mensagem foi processada")
            else:
                parts.append(f"{count} mensagens foram processadas")
        
        elif change == "notif:sent":
            parts.append("Uma notificação foi enviada para você")
    
    text = "Atualização do WhatsApp Monitor. " + ". ".join(parts) + "."
    
    return text

def send_audio_notification(text):
    """Envia áudio via TTS + WhatsApp"""
    try:
        # Gerar áudio
        result = subprocess.run(
            ["bash", WORKSPACE / "data" / "skills" / "azure-tts" / "scripts" / "speak.sh", text],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            print(f"Erro ao gerar áudio: {result.stderr}")
            return False
        
        # Extrair caminho do áudio
        audio_path = None
        for line in result.stdout.split('\n'):
            if line.startswith("MEDIA:"):
                audio_path = line.replace("MEDIA:", "").strip()
                break
        
        if not audio_path:
            print("Não consegui extrair caminho do áudio")
            return False
        
        # Enviar via WhatsApp
        subprocess.run([
            "docker", "compose", "exec", "-T", "openclaw-gateway",
            "wacli", "send", "text",
            "--to", "+5519992859614",
            "--message", text,
            "--store", str(Path.home() / ".openclaw" / "wacli")
        ], check=True, capture_output=True)
        
        # Enviar áudio depois
        subprocess.run([
            "docker", "compose", "exec", "-T", "openclaw-gateway",
            "wacli", "send", "file",
            "--to", "+5519992859614",
            "--file", audio_path,
            "--store", str(Path.home() / ".openclaw" / "wacli")
        ], check=True, capture_output=True)
        
        print(f"✅ Notificação enviada: {text}")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao enviar: {e}")
        return False

def main():
    """Loop principal"""
    print("📡 Monitorando atualizações do daemon...")
    
    state = load_state()
    check_interval = 5  # Verificar a cada 5 segundos
    
    while True:
        try:
            current = get_current_state()
            changes = detect_changes(state, current)
            
            if changes:
                print(f"🔔 Mudanças detectadas: {changes}")
                text = generate_audio_summary(changes)
                
                if text and send_audio_notification(text):
                    state.update(current)
                    state["last_notification_time"] = current["last_notification"]
                    save_state(state)
            
            time.sleep(check_interval)
            
        except KeyboardInterrupt:
            print("\n✓ Encerrando...")
            break
        except Exception as e:
            print(f"Erro: {e}")
            time.sleep(check_interval)

if __name__ == "__main__":
    main()
