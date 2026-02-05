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
# Conversation key:
# - DMs: chat_jid
# - Groups: chat_jid (one aggregated timeline per group)
CONVERSATIONS = defaultdict(lambda: {"messages": [], "last_msg_time": 0})

PENDING_IMAGE_RE = re.compile(
    r"^\\s*imagem\\s+recebida\\s*;\\s*an[aá]lise\\s+pendente\\.?\\s*$",
    re.IGNORECASE,
)

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

def _normalize_jid_or_number(value: str) -> str:
    s = (value or "").strip()
    if not s:
        return ""
    if "@" in s:
        return s
    digits = re.sub(r"[^0-9]", "", s)
    if not digits:
        return ""
    return f"{digits}@s.whatsapp.net"

def force_clear_store_lock_if_running():
    """
    If a wacli process is hung and still holds the store lock, try to kill it.
    This is a last resort to avoid the daemon getting stuck on sync/send forever.
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
        if is_pid_running(pid):
            try:
                os.kill(pid, signal.SIGTERM)
                time.sleep(0.5)
            except Exception:
                pass
            if is_pid_running(pid):
                try:
                    os.kill(pid, signal.SIGKILL)
                except Exception:
                    pass
        # Whether it was running or not, try removing the file (if possible).
        STORE_LOCK_FILE.unlink(missing_ok=True)
        log("WARNING", f"Forçando limpeza do LOCK do wacli (pid {pid})")
    except Exception as e:
        log("WARNING", f"Falha ao forçar limpeza do LOCK do wacli: {e}")

def log(level, msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [{level}] {msg}"
    # Avoid duplicating log lines when stdout is redirected to the same file.
    if sys.stdout.isatty():
        print(line, flush=True)
    with open(LOG_DIR / "daemon.log", "a") as f:
        f.write(line + "\n")

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

    # Hard ignore by JID (exact match), useful to prevent bot/self notification loops.
    for j in bl.get("jids", []) or []:
        jn = norm(j)
        if jn and jn == jid:
            return True

    # Always ignore WhatsApp Status / newsletters.
    # Some wacli rows can have chat_name populated with the JID, so check both.
    if (
        jid == "status@broadcast"
        or jid.endswith("@newsletter")
        or cn == "status@broadcast"
        or cn.endswith("@newsletter")
    ):
        return True

    # Substring match so "🟧 Comunidade PycodeBR" matches "Comunidade PycodeBR".
    for g in bl.get("groups", []) or []:
        g = norm(g)
        if g and g in cn:
            return True
    for c in bl.get("contacts", []) or []:
        c = norm(c)
        # Apply contact blacklist to both sender_name and chat_name.
        # Some DMs may show sender_name as "(me)" while chat_name is the real contact/bot name.
        if c and (c in sn or c in cn):
            return True
    return False

def _postprocess_summary_text(summary_text: str) -> str:
    """
    Clean model output before delivery:
    - collapse repeated "Imagem recebida; analise pendente." lines
    - strip local paths
    """
    if not summary_text:
        return summary_text

    lines = [ln.rstrip() for ln in summary_text.splitlines()]

    pending_count = sum(1 for ln in lines if PENDING_IMAGE_RE.match(ln))
    if pending_count > 1:
        compacted = []
        inserted = False
        for ln in lines:
            if PENDING_IMAGE_RE.match(ln):
                if not inserted:
                    compacted.append(f"Imagens recebidas ({pending_count}); analise pendente.")
                    inserted = True
                continue
            compacted.append(ln)
        lines = compacted

    out = "\n".join(lines).strip()
    out = re.sub(r"/home/node/\\S+", "[local-media]", out)
    return out

def _schedule_pending_media(chat_jid: str, chat_name: str, media_paths):
    """
    If image analysis is pending due to rate limits, keep a small retry queue in STATE_FILE.
    The retry will attempt to describe the media again and send a short update.
    """
    try:
        paths = [str(p).strip() for p in (media_paths or []) if str(p).strip()]
        seen = set()
        uniq = []
        for p in paths:
            if p in seen:
                continue
            seen.add(p)
            uniq.append(p)
        if not uniq:
            return

        state = get_state()
        pending = state.get("pending_media") or []
        pending = [x for x in pending if (x or {}).get("chat_jid") != chat_jid]
        pending.append(
            {
                "chat_jid": chat_jid,
                "chat_name": chat_name,
                "paths": uniq[:5],
                "attempts": 0,
                "next_try_ts": int(time.time()) + 10 * 60,
            }
        )
        state["pending_media"] = pending
        save_state(state)
        log("INFO", f"Midia pendente agendada para retry: {chat_name} ({len(uniq)} arquivos)")
    except Exception as e:
        log("WARNING", f"Falha ao agendar retry de midia: {e}")

def process_pending_media_retries():
    """
    Retry pending media analysis when the model previously rate-limited.
    Sends a short update if successful, and clears the queue entry.
    """
    state = get_state()
    pending = state.get("pending_media") or []
    if not pending:
        return

    now = int(time.time())
    kept = []

    for item in pending:
        try:
            chat_jid = str((item or {}).get("chat_jid") or "")
            chat_name = str((item or {}).get("chat_name") or chat_jid)
            paths = (item or {}).get("paths") or []
            attempts = int((item or {}).get("attempts") or 0)
            next_try_ts = int((item or {}).get("next_try_ts") or 0)

            if not chat_jid or not paths:
                continue
            if attempts >= 3:
                log("WARNING", f"Desistindo de retry de midia apos 3 tentativas: {chat_name}")
                continue
            if now < next_try_ts:
                kept.append(item)
                continue

            prompt = (
                "Voce e um assistente. Preciso de uma atualizacao curta sobre as imagens recebidas.\n"
                "Tarefa: descrever o conteudo das imagens/arquivos abaixo em 3-5 bullets.\n"
                "- NUNCA inclua caminhos locais (MEDIA_PATH) nem ids tecnicos na resposta.\n"
                "- Se nao conseguir analisar agora, responda apenas: \"Imagem recebida; analise pendente\".\n"
                "- Nao faca perguntas.\n"
                f"\nCHAT: {chat_name}\nJID: {chat_jid}\nARQUIVOS:\n"
                + "\n".join([f"- MEDIA_PATH={p}" for p in paths])
            )

            session_id = f"wacli-monitor:retry:{re.sub(r'[^a-zA-Z0-9:_-]+', '_', chat_jid)[:110]}"
            res = subprocess.run(
                ["openclaw", "agent", "--json", "--session-id", session_id, "--message", prompt],
                check=True,
                capture_output=True,
                text=True,
                timeout=600,
            )
            raw = (res.stdout or "").strip()
            try:
                payload = json.loads(raw)
            except Exception:
                start = raw.find("{")
                end = raw.rfind("}")
                payload = json.loads(raw[start : end + 1]) if (start >= 0 and end > start) else {}
            pls = (((payload or {}).get("result") or {}).get("payloads") or [])
            text = (pls[0].get("text") or "").strip() if pls else ""

            text = _postprocess_summary_text(text)
            if not text or PENDING_IMAGE_RE.match(text.strip()):
                attempts += 1
                backoff = (10 * 60) * attempts
                item["attempts"] = attempts
                item["next_try_ts"] = now + backoff
                kept.append(item)
                log("INFO", f"Retry de midia ainda pendente: {chat_name} (tentativa {attempts}/3)")
                continue

            mode = (CONFIG.get("notifications", {}).get("delivery", {}).get("mode") or "openclaw").strip().lower()
            if mode != "openclaw":
                log("WARNING", "Retry de midia ignorado: notifications.delivery.mode != openclaw")
                continue

            channel = CONFIG.get("notifications", {}).get("delivery", {}).get("openclaw_channel", "whatsapp")
            target = CONFIG.get("notifications", {}).get("delivery", {}).get("openclaw_target")
            if not target:
                raise RuntimeError("notifications.delivery.openclaw_target não configurado")

            msg = f"*📷 Atualizacao de imagem — {chat_name}*\n\n{text}".strip()
            subprocess.run(
                ["openclaw", "message", "send", "--channel", str(channel), "--target", str(target), "--message", msg],
                check=True,
                capture_output=True,
                text=True,
                timeout=180,
            )
            log("INFO", f"Atualizacao de midia entregue: {chat_name}")
        except Exception as e:
            try:
                attempts = int((item or {}).get("attempts") or 0) + 1
                item["attempts"] = attempts
                item["next_try_ts"] = now + (10 * 60) * attempts
                kept.append(item)
            except Exception:
                pass
            log("WARNING", f"Falha no retry de midia: {e}")

    state["pending_media"] = kept
    save_state(state)

def fetch_new_messages(retry_count=0, max_retries=3):
    """Sincroniza com retry logic"""
    try:
        clear_stale_store_lock()
        result = subprocess.run(
            # `wacli sync` holds the store lock while running. That's OK because we
            # call it synchronously (we won't attempt `send` until it returns).
            # Use a more realistic timeout so we actually fetch messages.
            ["wacli", "--timeout", "90s", "sync", "--once", "--json", "--store", str(WACLI_STORE)],
            capture_output=True,
            text=True,
            timeout=110,
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
        elif "store is locked" in (result.stderr or "").lower() or "store is locked" in (result.stdout or "").lower():
            # Another wacli command is running; don't fight it.
            log("WARNING", "Store do wacli está em uso (locked). Sincronização pulada.")
            return False
        else:
            if retry_count < max_retries:
                log("WARNING", f"Falha ao sincronizar (tentativa {retry_count+1}/{max_retries}), aguardando...")
                time.sleep(10 + retry_count * 5)
                return fetch_new_messages(retry_count + 1, max_retries)
            else:
                log("ERROR", f"Falha ao sincronizar após {max_retries} tentativas")
    
    except subprocess.TimeoutExpired:
        # If sync times out, wacli may have left a live process + store lock behind.
        force_clear_store_lock_if_running()
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
                msg_id,
                chat_jid,
                chat_name,
                sender_name,
                sender_jid,
                ts,
                from_me,
                text,
                display_text,
                media_type,
                media_caption,
                filename,
                mime_type,
                local_path
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
        include_from_me_direct = bool(
            CONFIG.get("monitor", {})
            .get("processing", {})
            .get("include_from_me_in_direct", False)
        )
        allowlist = (
            CONFIG.get("monitor", {})
            .get("processing", {})
            .get("include_from_me_direct_allowlist", [])
            or []
        )
        allowlist_jids = { _normalize_jid_or_number(x) for x in allowlist }
        allowlist_jids.discard("")

        for row in messages:
            # Convert early so we can safely use .get() and avoid sqlite3.Row KeyError surprises.
            msg = dict(row)
            msg_id = msg.get("msg_id")
            ts_val = msg.get("ts")
            if not msg_id or ts_val is None:
                # Skip malformed rows; keep going instead of crashing the whole loop.
                log("WARNING", f"Row sem campos essenciais (msg_id/ts). keys={list(msg.keys())}")
                continue

            try:
                ts_i = int(ts_val)
            except Exception:
                log("WARNING", f"Row com ts invalido: ts={ts_val!r} msg_id={msg_id!r}")
                continue

            max_ts_seen = max(max_ts_seen, ts_i)
            
            if msg_id in processed:
                continue

            if target_digits and (target_digits in str(msg.get("sender_jid") or "")):
                processed.add(msg_id)
                continue

            # Default: only incoming. Optionally include our own messages for group chats.
            if int(msg.get("from_me") or 0) == 1:
                chat_jid = str(msg.get("chat_jid") or "")
                if chat_jid.endswith("@g.us"):
                    if not include_from_me_groups:
                        processed.add(msg_id)
                        continue
                else:
                    # Direct message: only include if explicitly enabled or allowlisted.
                    if not include_from_me_direct and chat_jid not in allowlist_jids:
                        processed.add(msg_id)
                        continue
            
            if is_blacklisted(msg.get("chat_name"), msg.get("sender_name"), msg.get("chat_jid")):
                processed.add(msg_id)
                continue
            
            sender = msg.get("sender_name") if int(msg.get("from_me") or 0) == 0 else "(me)"
            sender = sender or "(unknown)"
            chat_jid = str(msg.get("chat_jid") or "")
            # Aggregate groups into a single conversation key (we want a group-level summary).
            conv_key = chat_jid

            fields = CONFIG.get("fields", {}).get("capture", [])
            record = {
                k: msg.get(k) for k in fields if k in msg.keys()
            }
            record["timestamp"] = datetime.fromtimestamp(ts_i).isoformat()
            # Prefer a human-friendly text representation for media-only messages.
            text_val = msg.get("text") or msg.get("display_text") or msg.get("media_caption") or ""
            media_type = (msg.get("media_type") or "").strip()
            if not text_val and media_type:
                text_val = f"[{media_type}]"
            # Keep more text so the LLM doesn't think messages are "cut".
            # (wacli DB stores full text; this is just our capture limit.)
            record["text"] = (text_val or "")[:1200]
            record["msg_ts"] = ts_i
            record["from_me"] = int(msg.get("from_me") or 0)
            # Keep media metadata for possible forwarding.
            record["media_type"] = media_type or None
            record["local_path"] = msg.get("local_path")
            record["filename"] = msg.get("filename")
            record["mime_type"] = msg.get("mime_type")
            record["chat_jid"] = chat_jid
            record["chat_name"] = msg.get("chat_name")
            record["sender_name"] = sender
            record["sender_jid"] = msg.get("sender_jid")

            CONVERSATIONS[conv_key]["messages"].append(record)
            CONVERSATIONS[conv_key]["last_msg_time"] = ts_i
            CONVERSATIONS[conv_key]["chat_name"] = msg.get("chat_name")
            CONVERSATIONS[conv_key]["chat_jid"] = chat_jid
            # Keep last sender for logging only; summary will use per-message sender.
            CONVERSATIONS[conv_key]["sender_name"] = sender

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
    group_wait = parse_duration_seconds(
        CONFIG.get("monitor", {}).get("conversation_batching", {}).get("group_wait", "30m"),
        1800,
    )

    for conv_key, conv_data in list(CONVERSATIONS.items()):
        if not conv_data["messages"]:
            continue
        
        sender = conv_data.get("sender_name") or "(unknown)"
        msg_count = len(conv_data["messages"])
        last_msg_time = conv_data["last_msg_time"]
        time_since_last = now - int(last_msg_time)
        is_group = str(conv_data.get("chat_jid") or "").endswith("@g.us")
        
        if is_vip(sender):
            ready.append(conv_key)
            log("INFO", f"VIP '{sender}': notificando ({msg_count} msgs)")
            continue
        
        total_length = sum(len(m.get("text", "")) for m in conv_data["messages"])
        is_short = should_wait_for_more(total_length)
        # If it's a short exchange, wait longer to avoid pinging on "oi/ok".
        # If it's long, we can notify sooner.
        base_wait = group_wait if is_group else default_wait
        wait_time = base_wait if is_short else min(base_wait, 30)
        
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
    
    # Build a compact context pack (we want LLM summary, not raw replication).
    chat_name = conv.get("chat_name") or conv.get("chat_jid") or "(unknown chat)"
    chat_jid = conv.get("chat_jid") or ""
    msg_count = len(messages)

    download_media = bool(CONFIG.get("notifications", {}).get("whatsapp", {}).get("download_media", True))
    max_mb = float(CONFIG.get("notifications", {}).get("whatsapp", {}).get("media_max_mb", 15))
    max_bytes = int(max_mb * 1024 * 1024)

    def ensure_media_download(msg):
        if not download_media:
            return ""
        media_type = (msg.get("media_type") or "").strip()
        if not media_type:
            return ""
        local_path = (msg.get("local_path") or "").strip()
        if local_path and Path(local_path).is_file():
            return local_path
        msg_id = (msg.get("msg_id") or "").strip()
        if not msg_id or not chat_jid:
            return ""
        try:
            clear_stale_store_lock()
            dl = subprocess.run(
                [
                    "wacli",
                    "--timeout",
                    "5m",
                    "media",
                    "download",
                    "--chat",
                    chat_jid,
                    "--id",
                    msg_id,
                    "--store",
                    str(WACLI_STORE),
                    "--json",
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=330,
            )
            lines = [ln for ln in (dl.stdout or "").splitlines() if ln.strip()]
            if not lines:
                return ""
            payload = json.loads(lines[-1])
            path = (((payload or {}).get("data") or {}).get("path") or "").strip()
            if not path:
                return ""
            p = Path(path)
            if not p.is_file():
                return ""
            try:
                size = p.stat().st_size
            except Exception:
                size = 0
            if max_bytes > 0 and size > max_bytes:
                log("WARNING", f"Mídia grande demais para baixar/analisar ({size} > {max_bytes}).")
                return ""
            msg["local_path"] = str(p)
            return str(p)
        except Exception as e:
            log("WARNING", f"Falha ao baixar mídia (msg_id={msg_id}): {e}")
            return ""

    # Build timeline lines
    lines = []
    for m in messages[-50:]:
        hhmm = (m.get("timestamp") or "").split("T")[-1][:5]
        sender = (m.get("sender_name") or "").strip() or "(unknown)"
        media_type = (m.get("media_type") or "").strip()
        text = (m.get("text") or "").strip()
        if not text:
            text = f"[{media_type}]" if media_type else "[mídia]"
        media_path = ensure_media_download(m)
        if media_type and media_path:
            # Keep the path available for the model to load the file, but strongly
            # discourage the model from echoing it back to the user.
            lines.append(f"[{hhmm}] {sender}: {text} (MEDIA {media_type} MEDIA_PATH={media_path})")
        else:
            lines.append(f"[{hhmm}] {sender}: {text}")

    prompt = (
        "Voce e um assistente. Recebi novas mensagens no WhatsApp.\n"
        "Tarefa: devolver PARA MIM um RESUMO, sem replicar as mensagens.\n"
        "- Se houver imagens/arquivos, use o PATH local (quando presente) para descrever o conteudo.\n"
        "- Para grupos: descreva o contexto geral (temas, perguntas, acoes sugeridas).\n"
        "- NUNCA inclua caminhos locais (MEDIA_PATH) nem ids tecnicos na resposta.\n"
        "- Se nao conseguir analisar a imagem agora (ex.: rate limit), diga apenas: \"Imagem recebida; analise pendente\".\n"
        "- Nao faca perguntas ao usuario.\n"
        "- Nao assuma que uma mensagem esta incompleta; se parecer truncada, diga que pode ter sido truncada pelo monitor.\n"
        "- Seja curto: no maximo 6 bullets.\n"
        f"\nCHAT: {chat_name}\nJID: {chat_jid}\nMENSAGENS ({min(len(lines),50)} de {msg_count}):\n"
        + "\n".join(lines)
    )

    # Ask OpenClaw agent to summarize using the currently active model/routing.
    summary_text = ""
    try:
        # Keep session deterministic per chat so the agent can carry context if needed.
        session_id = f"wacli-monitor:{re.sub(r'[^a-zA-Z0-9:_-]+', '_', chat_jid)[:120]}"
        res = subprocess.run(
            ["openclaw", "agent", "--json", "--session-id", session_id, "--message", prompt],
            check=True,
            capture_output=True,
            text=True,
            timeout=600,
        )
        raw = (res.stdout or "").strip()
        # `openclaw agent --json` returns pretty-printed multi-line JSON.
        # Parse the entire stdout; fall back to extracting the JSON object if extra logs leak in.
        try:
            payload = json.loads(raw)
        except Exception:
            start = raw.find("{")
            end = raw.rfind("}")
            if start >= 0 and end > start:
                payload = json.loads(raw[start : end + 1])
            else:
                raise
        pls = (((payload or {}).get("result") or {}).get("payloads") or [])
        if pls and isinstance(pls, list):
            summary_text = (pls[0].get("text") or "").strip()
    except Exception as e:
        # Include stderr/stdout tail to make failures debuggable from daemon.log.
        err = ""
        out = ""
        if isinstance(e, subprocess.CalledProcessError):
            err = (e.stderr or "").strip()
            out = (e.stdout or "").strip()
        else:
            err = (getattr(res, "stderr", "") or "").strip() if "res" in locals() else ""
            out = (getattr(res, "stdout", "") or "").strip() if "res" in locals() else ""
        tail = (err or out)[-600:] if (err or out) else ""
        log("ERROR", f"Falha ao gerar resumo via OpenClaw agent: {e}; tail={tail!r}")

    if not summary_text:
        # Fallback: minimal non-empty notification.
        summary_text = f"Resumo indisponível. {chat_name}: {msg_count} novas mensagens."
    else:
        # Some models may echo our fallback phrase; strip it if it appears.
        cleaned = []
        for ln in summary_text.splitlines():
            # Some providers prepend/append our own fallback sentence; drop it if present.
            if re.match(r"^\s*Resumo\s+indispon[ií]vel\b", ln.strip(), re.IGNORECASE):
                continue
            cleaned.append(ln)
        summary_text = "\n".join(cleaned).strip()

    # Clean summary output (collapse repeated pending-image lines, redact local paths).
    summary_text = _postprocess_summary_text(summary_text)

    # If the model couldn't analyze media (rate limit), schedule a retry update.
    if "analise pendente" in summary_text.lower():
        media_paths = []
        for m in messages:
            p = (m.get("local_path") or "").strip()
            if p:
                media_paths.append(p)
        if media_paths:
            _schedule_pending_media(chat_jid, chat_name, media_paths)

    # Deliver the summary (preferred: OpenClaw -> WhatsApp -> you).
    mode = (CONFIG.get("notifications", {}).get("delivery", {}).get("mode") or "openclaw").strip().lower()
    max_chars = int(CONFIG.get("notifications", {}).get("whatsapp", {}).get("max_chars", 900))
    if max_chars > 0 and len(summary_text) > max_chars:
        summary_text = summary_text[: max_chars - 20].rstrip() + "\n...[truncado]"

    try:
        if mode == "openclaw":
            channel = CONFIG.get("notifications", {}).get("delivery", {}).get("openclaw_channel", "whatsapp")
            target = CONFIG.get("notifications", {}).get("delivery", {}).get("openclaw_target")
            if not target:
                raise RuntimeError("notifications.delivery.openclaw_target não configurado")

            # Optional: send as audio when the block is big.
            audio_cfg = (CONFIG.get("notifications", {}).get("delivery", {}).get("audio") or {})
            audio_enabled = bool(audio_cfg.get("enabled", False))
            audio_only_groups = bool(audio_cfg.get("only_groups", True))
            audio_min_messages = int(audio_cfg.get("min_messages", 8) or 8)
            audio_min_chars = int(audio_cfg.get("min_chars", 450) or 450)
            is_group = str(chat_jid).endswith("@g.us")
            use_audio = False
            if audio_enabled:
                if (not audio_only_groups) or is_group:
                    if msg_count >= audio_min_messages or len(summary_text) >= audio_min_chars:
                        use_audio = True

            if use_audio:
                # Generate a WhatsApp-friendly OGG/Opus voice note via the azure-tts skill.
                # The skill outputs: "MEDIA: media/tts/tts_<id>.ogg"
                speak_text = summary_text
                # Cheap markdown cleanup for TTS.
                speak_text = re.sub(r"[`*_#>]+", "", speak_text)
                speak_text = re.sub(r"\s*\[[^\]]+\]\([^\)]+\)", "", speak_text)  # links
                speak_text = re.sub(r"\s+", " ", speak_text).strip()

                skill_dir = Path.home() / ".openclaw" / "workspace" / "skills" / "azure-tts"
                speak_sh = skill_dir / "scripts" / "speak.sh"
                if not speak_sh.exists():
                    raise RuntimeError(f"azure-tts skill not found at {speak_sh}")

                tts = subprocess.run(
                    [str(speak_sh), speak_text],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=600,
                )
                media_rel = ""
                for ln in (tts.stdout or "").splitlines():
                    ln = ln.strip()
                    if ln.startswith("MEDIA:"):
                        media_rel = ln.split(":", 1)[1].strip()
                        break
                if not media_rel:
                    raise RuntimeError(f"azure-tts did not return MEDIA path. stdout={(tts.stdout or '')[:200]!r}")

                media_abs = str((Path.home() / ".openclaw" / "workspace" / media_rel).resolve())
                subprocess.run(
                    [
                        "openclaw",
                        "message",
                        "send",
                        "--channel",
                        str(channel),
                        "--target",
                        str(target),
                        "--message",
                        f"(audio) Resumo: {chat_name}",
                        "--media",
                        media_abs,
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=180,
                )
                log("INFO", f"Resumo entregue em audio via OpenClaw: {chat_name} ({msg_count} msgs)")
            else:
                subprocess.run(
                    ["openclaw", "message", "send", "--channel", str(channel), "--target", str(target), "--message", summary_text],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                log("INFO", f"Resumo entregue via OpenClaw: {chat_name} ({msg_count} msgs)")
        else:
            # Legacy fallback: send to yourself via wacli (usually not ideal).
            target = _normalize_jid_or_number(CONFIG.get("notifications", {}).get("whatsapp", {}).get("target") or "")
            if not target:
                raise RuntimeError("notifications.whatsapp.target não configurado para modo wacli")
            clear_stale_store_lock()
            subprocess.run(
                ["wacli", "--timeout", "2m", "send", "text", "--to", target, "--message", summary_text, "--store", str(WACLI_STORE)],
                check=True,
                capture_output=True,
                text=True,
                timeout=150,
            )
            log("INFO", f"Resumo entregue via wacli: {chat_name} ({msg_count} msgs)")

        del CONVERSATIONS[conv_key]
    except Exception as e:
        log("ERROR", f"Erro ao entregar resumo: {e}")

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

                # Retry pending media analysis (e.g. image model rate limit).
                process_pending_media_retries()
                
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
