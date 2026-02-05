#!/usr/bin/env python3

"""
WhatsApp Monitor Daemon v3 (PID-Safe)
- Robust PID locking: previne múltiplas instâncias
- Conversation batching: aguarda mais mensagens
- VIP list: notifica imediatamente
- Retry logic: recupera de falhas de conectividade
"""

import json
import sqlite3
import subprocess
import time
import signal
import sys
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
import yaml

WORKSPACE = Path.home() / ".openclaw" / "workspace"
WACLI_STORE = Path.home() / ".openclaw" / "wacli"
LOG_DIR = WORKSPACE / "logs" / "wacli"
CONFIG_FILE = WORKSPACE / "skills" / "wacli-monitor" / "config" / "wacli-config.yaml"
STATE_FILE = LOG_DIR / ".daemon_state.json"
PID_FILE = LOG_DIR / ".daemon.pid"
STORE_LOCK_FILE = WACLI_STORE / "LOCK"

LOG_DIR.mkdir(parents=True, exist_ok=True)

CONFIG = {}
RUNNING = True
CONVERSATIONS = defaultdict(lambda: {"messages": [], "last_msg_time": 0})

def parse_duration_seconds(value, default_seconds):
    """
    Parse durations like: "10s", "2m", "1h".
    Returns default_seconds on invalid input.
    """
    if value is None:
        return default_seconds
    if isinstance(value, (int, float)):
        return int(value)
    s = str(value).strip().lower()
    if not s:
        return default_seconds
    mult = 1
    if s.endswith("ms"):
        # wacli stores ts in seconds; we keep daemon logic in seconds too.
        try:
            return max(0, int(int(s[:-2]) / 1000))
        except Exception:
            return default_seconds
    if s.endswith("s"):
        mult = 1
        s = s[:-1]
    elif s.endswith("m"):
        mult = 60
        s = s[:-1]
    elif s.endswith("h"):
        mult = 3600
        s = s[:-1]
    try:
        return max(0, int(float(s) * mult))
    except Exception:
        return default_seconds

def clear_stale_store_lock():
    """
    wacli keeps an advisory store lock and writes metadata to ~/.openclaw/wacli/LOCK.
    If a previous wacli process crashed, the LOCK file can stick around and block all commands.
    """
    try:
        if not STORE_LOCK_FILE.exists():
            return
        raw = STORE_LOCK_FILE.read_text(encoding="utf-8", errors="ignore")
        m = re.search(r"pid=(\d+)", raw)
        if not m:
            return
        pid = int(m.group(1))
        if pid <= 1:
            return
        if not is_pid_running(pid):
            STORE_LOCK_FILE.unlink(missing_ok=True)
            log("INFO", f"Removido LOCK órfão do wacli (pid {pid})")
    except Exception as e:
        log("WARNING", f"Falha ao checar/remover LOCK do wacli: {e}")

def log(level, msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [{level}] {msg}", flush=True)
    with open(LOG_DIR / "daemon.log", "a") as f:
        f.write(f"[{ts}] [{level}] {msg}\n")

def is_pid_running(pid):
    """Verifica se um PID está ativo"""
    try:
        os.kill(pid, 0)  # Signal 0 = apenas checa, não mata
        return True
    except (OSError, ProcessLookupError):
        return False

def acquire_lock():
    """Adquire lock de PID, retorna True se sucesso"""
    current_pid = os.getpid()
    
    # Verificar se já existe lock
    if PID_FILE.exists():
        try:
            with open(PID_FILE) as f:
                old_pid = int(f.read().strip())
            
            if is_pid_running(old_pid):
                log("ERROR", f"Daemon já rodando (PID {old_pid}). Abortando.")
                return False
            else:
                log("INFO", f"Removendo lock órfão (PID {old_pid} não está rodando)")
        except Exception as e:
            log("WARNING", f"Erro ao ler PID file: {e}")
    
    # Criar novo lock
    try:
        with open(PID_FILE, "w") as f:
            f.write(str(current_pid))
        log("INFO", f"Lock adquirido (PID {current_pid})")
        return True
    except Exception as e:
        log("ERROR", f"Erro ao criar lock: {e}")
        return False

def release_lock():
    """Libera lock de PID"""
    try:
        if PID_FILE.exists():
            PID_FILE.unlink()
        log("INFO", "Lock liberado")
    except Exception as e:
        log("ERROR", f"Erro ao liberar lock: {e}")

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

def is_blacklisted(chat_name, sender_name, chat_jid=""):
    bl = CONFIG.get("blacklist", {})

    def norm(s):
        s = (s or "")
        s = re.sub(r"\s+", " ", str(s)).strip().lower()
        return s

    cn = norm(chat_name)
    sn = norm(sender_name)
    jid = norm(chat_jid)

    # Always ignore WhatsApp Status / newsletters.
    if jid == "status@broadcast" or jid.endswith("@newsletter"):
        return True

    # Substring match so "🟧 Comunidade PycodeBR" matches "Comunidade PycodeBR".
    for g in bl.get("groups", []) or []:
        g = norm(g)
        if g and g in cn:
            return True
    for c in bl.get("contacts", []) or []:
        c = norm(c)
        if c and c in sn:
            return True
    return False

def fetch_new_messages(retry_count=0, max_retries=3):
    """Sincroniza com retry logic"""
    try:
        clear_stale_store_lock()
        result = subprocess.run(
            ["wacli", "sync", "--once", "--json", "--store", str(WACLI_STORE)],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0:
            try:
                data = json.loads(result.stdout.strip().split('\n')[-1])
                count = data.get("data", {}).get("messages_stored", 0)
                if count > 0:
                    log("INFO", f"Sincronizadas {count} mensagens")
                    return True
            except json.JSONDecodeError:
                pass
        elif "not authenticated" in result.stderr or "not authenticated" in result.stdout:
            log("WARNING", "wacli não autenticado - sincronização pulada")
            return False
        else:
            if retry_count < max_retries:
                log("WARNING", f"Falha ao sincronizar (tentativa {retry_count+1}/{max_retries}), aguardando...")
                time.sleep(10 + retry_count * 5)
                return fetch_new_messages(retry_count + 1, max_retries)
            else:
                log("ERROR", f"Falha ao sincronizar após {max_retries} tentativas")
    
    except subprocess.TimeoutExpired:
        if retry_count < max_retries:
            log("WARNING", f"Timeout ao sincronizar (tentativa {retry_count+1}/{max_retries})")
            time.sleep(15)
            return fetch_new_messages(retry_count + 1, max_retries)
        else:
            log("ERROR", "Timeout ao sincronizar (máximo de tentativas excedido)")
    except Exception as e:
        log("ERROR", f"Erro ao sincronizar: {e}")
    
    return False

def process_messages():
    """Processa com conversation batching"""
    state = get_state()
    processed = set(state.get("processed_msg_ids", []))
    last_processed_ts = int(state.get("last_processed_ts") or 0)
    
    try:
        conn = sqlite3.connect(WACLI_STORE / "wacli.db")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # NOTE: wacli stores `messages.ts` in seconds (not milliseconds).
        retention_hours = int(CONFIG.get("monitor", {}).get("processing", {}).get("retention_hours", 24))
        retention_cutoff = int(time.time()) - (retention_hours * 3600)
        cutoff = max(last_processed_ts, retention_cutoff)
        
        cursor.execute("""
            SELECT 
                msg_id, chat_jid, chat_name, sender_name, sender_jid, ts, from_me, text, media_type
            FROM messages
            WHERE ts >= ?
            ORDER BY ts ASC
        """, (cutoff,))
        
        messages = cursor.fetchall()
        conn.close()
        
        new_count = 0
        max_ts_seen = last_processed_ts
        # Prevent feedback loop: ignore messages sent by the notification target itself.
        target = str(CONFIG.get("notifications", {}).get("whatsapp", {}).get("target") or "").strip()
        target_digits = re.sub(r"[^0-9]", "", target)

        include_from_me_groups = bool(
            CONFIG.get("monitor", {})
            .get("processing", {})
            .get("include_from_me_in_groups", False)
        )

        for msg in messages:
            msg_id = msg["msg_id"]
            max_ts_seen = max(max_ts_seen, int(msg["ts"]))
            
            if msg_id in processed:
                continue

            if target_digits and (target_digits in str(msg["sender_jid"] or "")):
                processed.add(msg_id)
                continue

            # Default: only incoming. Optionally include our own messages for group chats.
            if int(msg["from_me"] or 0) == 1:
                if not include_from_me_groups:
                    processed.add(msg_id)
                    continue
                if not str(msg["chat_jid"] or "").endswith("@g.us"):
                    processed.add(msg_id)
                    continue
            
            if is_blacklisted(msg["chat_name"], msg["sender_name"], msg["chat_jid"]):
                processed.add(msg_id)
                continue
            
            sender = msg["sender_name"] if int(msg["from_me"] or 0) == 0 else "(me)"
            conv_key = f"{msg['chat_jid']}:{sender}"
            
            fields = CONFIG.get("fields", {}).get("capture", [])
            record = {
                k: msg[k] for k in fields if k in msg.keys()
            }
            record["timestamp"] = datetime.fromtimestamp(msg["ts"]).isoformat()
            record["text"] = (record.get("text") or "")[:200]
            record["msg_ts"] = msg["ts"]
            record["from_me"] = int(msg["from_me"] or 0)
            
            CONVERSATIONS[conv_key]["messages"].append(record)
            CONVERSATIONS[conv_key]["last_msg_time"] = msg["ts"]
            CONVERSATIONS[conv_key]["chat_name"] = msg["chat_name"]
            CONVERSATIONS[conv_key]["sender_name"] = sender
            CONVERSATIONS[conv_key]["chat_jid"] = msg["chat_jid"]
            
            processed.add(msg_id)
            new_count += 1
        
        # Keep a small rolling window of msg_ids to handle same-second duplicates.
        keep_ids = int(CONFIG.get("monitor", {}).get("processing", {}).get("max_processed_ids", 5000))
        if keep_ids < 100:
            keep_ids = 100
        state["processed_msg_ids"] = list(processed)[-keep_ids:]
        state["last_processed_ts"] = max_ts_seen
        save_state(state)
        
        if new_count > 0:
            log("INFO", f"Processadas {new_count} mensagens")
        
        return new_count
        
    except Exception as e:
        log("ERROR", f"Erro ao processar: {e}")
        return 0

def check_ready_conversations():
    """Verifica conversas prontas para notificar"""
    now = int(time.time())
    ready = []
    
    default_wait = parse_duration_seconds(
        CONFIG.get("monitor", {}).get("conversation_batching", {}).get("default_wait", "2m"),
        120,
    )

    for conv_key, conv_data in list(CONVERSATIONS.items()):
        if not conv_data["messages"]:
            continue
        
        sender = conv_data["sender_name"]
        msg_count = len(conv_data["messages"])
        last_msg_time = conv_data["last_msg_time"]
        time_since_last = now - int(last_msg_time)
        
        if is_vip(sender):
            ready.append(conv_key)
            log("INFO", f"VIP '{sender}': notificando ({msg_count} msgs)")
            continue
        
        total_length = sum(len(m.get("text", "")) for m in conv_data["messages"])
        is_short = should_wait_for_more(total_length)
        # If it's a short exchange, wait longer to avoid pinging on "oi/ok".
        # If it's long, we can notify sooner.
        wait_time = default_wait if is_short else min(default_wait, 30)
        
        if time_since_last >= wait_time:
            ready.append(conv_key)
            log("INFO", f"'{sender}': pronta para notificar ({msg_count} msgs)")
    
    return ready

def notify_conversation(conv_key):
    """Envia notificação de uma conversa"""
    conv = CONVERSATIONS[conv_key]
    messages = conv["messages"]
    
    if not messages:
        return
    
    whatsapp_target = CONFIG.get("notifications", {}).get("whatsapp", {}).get("target")
    if not whatsapp_target:
        log("WARNING", "notifications.whatsapp.target não configurado (nenhuma notificação enviada)")
        return

    # wacli is more reliable when sending to a JID vs. a phone number.
    # Accept "+55..." or "55..." and normalize to "<digits>@s.whatsapp.net".
    target = str(whatsapp_target).strip()
    if "@" not in target:
        digits = re.sub(r"[^0-9]", "", target)
        if digits:
            target = f"{digits}@s.whatsapp.net"
    
    sender = conv["sender_name"]
    chat_name = conv["chat_name"]
    msg_count = len(messages)
    
    if msg_count == 1:
        text = f"💬 {sender} ({chat_name}):\n{messages[0].get('text', '[mídia]')}"
    else:
        text = f"💬 {sender} ({chat_name}) - {msg_count} mensagens:\n"
        for msg in messages:
            ts = msg['timestamp'].split('T')[1][:5]
            text += f"[{ts}] {msg.get('text', '[mídia]')}\n"

    max_chars = int(CONFIG.get("notifications", {}).get("whatsapp", {}).get("max_chars", 900))
    if max_chars > 0 and len(text) > max_chars:
        text = text[: max_chars - 20].rstrip() + "\n...[truncado]"

    try:
        # Daemon already runs in the gateway container, so call wacli directly.
        clear_stale_store_lock()
        subprocess.run(
            [
                "wacli",
                "--timeout",
                "2m",
                "send",
                "text",
                "--to",
                target,
                "--message",
                text,
                "--store",
                str(WACLI_STORE),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=150,
        )
        
        log("INFO", f"Notificação enviada: {sender} ({msg_count} msgs)")
        del CONVERSATIONS[conv_key]
        
    except Exception as e:
        # Show stderr for debugging (wacli can fail with store locks or connectivity errors).
        if isinstance(e, subprocess.CalledProcessError):
            err = (e.stderr or "").strip()
            out = (e.stdout or "").strip()
            msg = err or out or str(e)
            log("ERROR", f"Erro ao notificar: {msg}")
        else:
            log("ERROR", f"Erro ao notificar: {e}")

def get_state():
    try:
        if STATE_FILE.exists():
            with open(STATE_FILE) as f:
                return json.load(f)
    except:
        pass
    # Bootstrap: avoid processing the entire historical DB on first run.
    bootstrap_catchup = parse_duration_seconds(
        CONFIG.get("monitor", {}).get("processing", {}).get("bootstrap_catchup", "2m"),
        120,
    )
    return {"processed_msg_ids": [], "last_processed_ts": int(time.time()) - bootstrap_catchup}

def save_state(state):
    state["processed_msg_ids"] = list(state.get("processed_msg_ids", []))
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

def signal_handler(sig, frame):
    global RUNNING
    log("INFO", "Recebido sinal de encerramento")
    RUNNING = False

def main():
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Tentar adquirir lock
    if not acquire_lock():
        sys.exit(1)
    
    if not load_config():
        release_lock()
        sys.exit(1)
    
    log("INFO", "=== WhatsApp Monitor Daemon v3 (PID-Safe) ===")
    log("INFO", f"Config: {CONFIG_FILE}")
    
    last_fetch = 0
    fetch_interval = 30
    
    try:
        while RUNNING:
            try:
                if time.time() - last_fetch > fetch_interval:
                    fetch_new_messages()
                    last_fetch = time.time()
                
                process_messages()
                
                ready = check_ready_conversations()
                for conv_key in ready:
                    notify_conversation(conv_key)
                
                time.sleep(5)
                
            except Exception as e:
                log("ERROR", f"Erro no loop: {e}")
                time.sleep(10)
    
    finally:
        log("INFO", "Finalizando daemon...")
        release_lock()
        log("INFO", "Daemon encerrado")

if __name__ == "__main__":
    main()
