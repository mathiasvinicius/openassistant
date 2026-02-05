#!/usr/bin/env python3

"""
WhatsApp Monitor Daemon v2
- Conversation batching: aguarda mais mensagens da mesma pessoa
- VIP list: notifica imediatamente de contatos específicos
- Smart delays: curtas mensagens aguardam mais tempo
"""

import json
import sqlite3
import subprocess
import time
import signal
import sys
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
import yaml

WORKSPACE = Path.home() / ".openclaw" / "workspace"
WACLI_STORE = Path.home() / ".openclaw" / "wacli"
LOG_DIR = WORKSPACE / "logs" / "wacli"
CONFIG_FILE = WORKSPACE / "config" / "wacli-config.yaml"
STATE_FILE = LOG_DIR / ".daemon_state.json"

LOG_DIR.mkdir(parents=True, exist_ok=True)

CONFIG = {}
RUNNING = True
CONVERSATIONS = defaultdict(lambda: {"messages": [], "last_msg_time": 0})

def log(level, msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [{level}] {msg}", flush=True)
    with open(LOG_DIR / "daemon.log", "a") as f:
        f.write(f"[{ts}] [{level}] {msg}\n")

def load_config():
    global CONFIG
    try:
        with open(CONFIG_FILE) as f:
            CONFIG = yaml.safe_load(f)
        log("INFO", "Configuração carregada")
        return True
    except Exception as e:
        log("ERROR", f"Erro ao carregar config: {e}")
        return False

def is_vip(sender_name):
    """Verifica se é contato VIP (notifica imediatamente)"""
    vip_list = CONFIG.get("monitor", {}).get("conversation_batching", {}).get("vip_list", [])
    return sender_name in vip_list

def should_wait_for_more(text_length):
    """Determina se deve aguardar mais mensagens"""
    threshold = CONFIG.get("monitor", {}).get("conversation_batching", {}).get("short_message_threshold", 50)
    return text_length < threshold

def is_blacklisted(chat_name, sender_name):
    bl = CONFIG.get("blacklist", {})
    return (
        chat_name in bl.get("groups", []) or
        sender_name in bl.get("contacts", [])
    )

def get_strategy(chat_name, chat_jid):
    strategies = CONFIG.get("strategies", {})
    
    for strat_name, strat in strategies.items():
        if strat.get("type") == "group":
            if chat_name in strat.get("groups", []):
                return strat_name, strat
        elif strat.get("type") == "individual":
            if "Grupo" not in chat_name:
                return strat_name, strat
    
    return ("default_group" if "Grupo" in chat_name else "default_dm"), None

def fetch_new_messages():
    try:
        result = subprocess.run(
            ["wacli", "sync", "--once", "--json", "--store", str(WACLI_STORE)],
            capture_output=True,
            text=True,
            timeout=60  # Aumentado de 30s para 60s
        )
        
        if result.returncode == 0:
            try:
                data = json.loads(result.stdout.strip().split('\n')[-1])
                count = data.get("data", {}).get("messages_stored", 0)
                if count > 0:
                    log("INFO", f"Sincronizadas {count} mensagens")
                return count > 0
            except:
                return False
    except Exception as e:
        log("ERROR", f"Erro ao sincronizar: {e}")
    return False

def process_messages():
    """Processa com conversation batching"""
    state = get_state()
    processed = set(state["processed_msg_ids"])
    
    try:
        conn = sqlite3.connect(WACLI_STORE / "wacli.db")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cutoff = int(time.time() * 1000) - (3600 * 1000)
        
        cursor.execute("""
            SELECT 
                msg_id, chat_jid, chat_name, sender_name, ts, text, media_type
            FROM messages
            WHERE ts > ? AND from_me = 0
            ORDER BY ts ASC
        """, (cutoff,))
        
        messages = cursor.fetchall()
        conn.close()
        
        new_count = 0
        for msg in messages:
            msg_id = msg["msg_id"]
            
            if msg_id in processed:
                continue
            
            if is_blacklisted(msg["chat_name"], msg["sender_name"]):
                processed.add(msg_id)
                continue
            
            # Chave da conversa: (chat, sender)
            conv_key = f"{msg['chat_jid']}:{msg['sender_name']}"
            
            # Extrair campos
            fields = CONFIG.get("fields", {}).get("capture", [])
            record = {
                k: msg[k] for k in fields if k in msg.keys()
            }
            record["timestamp"] = datetime.fromtimestamp(msg["ts"]/1000).isoformat()
            record["text"] = (record.get("text") or "")[:200]
            record["msg_ts"] = msg["ts"]
            
            # Adicionar à conversa
            CONVERSATIONS[conv_key]["messages"].append(record)
            CONVERSATIONS[conv_key]["last_msg_time"] = msg["ts"]
            CONVERSATIONS[conv_key]["chat_name"] = msg["chat_name"]
            CONVERSATIONS[conv_key]["sender_name"] = msg["sender_name"]
            CONVERSATIONS[conv_key]["chat_jid"] = msg["chat_jid"]
            
            processed.add(msg_id)
            new_count += 1
        
        state["processed_msg_ids"] = processed
        save_state(state)
        
        if new_count > 0:
            log("INFO", f"Processadas {new_count} mensagens (aguardando batching...)")
        
        return new_count
        
    except Exception as e:
        log("ERROR", f"Erro ao processar: {e}")
        return 0

def check_ready_conversations():
    """Verifica conversas prontas para notificar"""
    now = time.time() * 1000
    ready = []
    
    for conv_key, conv_data in list(CONVERSATIONS.items()):
        if not conv_data["messages"]:
            continue
        
        sender = conv_data["sender_name"]
        msg_count = len(conv_data["messages"])
        last_msg_time = conv_data["last_msg_time"]
        time_since_last = (now - last_msg_time) / 1000
        
        # VIP: notifica imediatamente
        if is_vip(sender):
            ready.append(conv_key)
            log("INFO", f"VIP '{sender}': notificando imediatamente ({msg_count} msgs)")
            continue
        
        # Mensagem curta: aguarda mais tempo
        total_length = sum(len(m.get("text", "")) for m in conv_data["messages"])
        is_short = should_wait_for_more(total_length)
        wait_time = 120 if is_short else 120  # Padrão 2 min para ambos
        
        if time_since_last >= wait_time:
            ready.append(conv_key)
            wait_reason = "curta e aguardou" if is_short else "batch timeout"
            log("INFO", f"'{sender}': pronta ({msg_count} msgs, {wait_reason})")
    
    return ready

def notify_conversation(conv_key):
    """Envia notificação de uma conversa"""
    conv = CONVERSATIONS[conv_key]
    messages = conv["messages"]
    
    if not messages:
        return
    
    whatsapp_target = CONFIG.get("notifications", {}).get("whatsapp", {}).get("target")
    if not whatsapp_target:
        return
    
    # Montar mensagem
    sender = conv["sender_name"]
    chat_name = conv["chat_name"]
    msg_count = len(messages)
    
    # Formato inteligente
    if msg_count == 1:
        text = f"💬 **{sender}** ({chat_name}):\n\n{messages[0].get('text', '[mídia]')}"
    else:
        text = f"💬 **{sender}** ({chat_name}) - {msg_count} mensagens:\n\n"
        for msg in messages:
            ts = msg['timestamp'].split('T')[1][:5]
            text += f"[{ts}] {msg.get('text', '[mídia]')}\n"
    
    try:
        subprocess.run([
            "docker", "compose", "exec", "-T", "openclaw-gateway",
            "wacli", "send", "text",
            "--to", whatsapp_target,
            "--message", text,
            "--store", str(WACLI_STORE)
        ], check=True, capture_output=True)
        
        log("INFO", f"Notificação enviada: {sender} ({msg_count} msgs)")
        del CONVERSATIONS[conv_key]
        
    except Exception as e:
        log("ERROR", f"Erro ao notificar: {e}")

def get_state():
    try:
        if STATE_FILE.exists():
            with open(STATE_FILE) as f:
                return json.load(f)
    except:
        pass
    return {"processed_msg_ids": []}

def save_state(state):
    state["processed_msg_ids"] = list(state["processed_msg_ids"])
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

def signal_handler(sig, frame):
    global RUNNING
    log("INFO", "Encerrando daemon...")
    RUNNING = False
    sys.exit(0)

def main():
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    if not load_config():
        sys.exit(1)
    
    log("INFO", "=== WhatsApp Monitor Daemon v2 (Conversation Batching) ===")
    log("INFO", f"Config: {CONFIG_FILE}")
    
    last_fetch = 0
    fetch_interval = 30
    
    while RUNNING:
        try:
            # Sincronizar
            if time.time() - last_fetch > fetch_interval:
                fetch_new_messages()
                last_fetch = time.time()
            
            # Processar novas mensagens
            process_messages()
            
            # Verificar conversas prontas
            ready = check_ready_conversations()
            for conv_key in ready:
                notify_conversation(conv_key)
            
            time.sleep(5)
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            log("ERROR", f"Erro: {e}")
            time.sleep(10)
    
    log("INFO", "Daemon encerrado")

if __name__ == "__main__":
    main()
