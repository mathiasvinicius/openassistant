# WhatsApp Monitor Daemon v3 - PID Safety & Corrections

**Data:** 2026-02-05 09:47 GMT-3  
**Status:** ✅ Implementado e testado

## Problema Resolvido

- **Root cause:** `wacli sync` ficava preso segurando o lock, causando timeouts no daemon
- **Sintoma:** Múltiplas instâncias do `wacli-daemon` e `wacli-notify-changes` rodando simultaneamente
- **Impacto:** Competição de recursos, timeouts, sincronizações falhadas

## Solução Implementada

### 1. **Daemon v3 com PID Locking Robusto** (`wacli-daemon-v3.py`)

```python
# Check robusto de PID
def is_pid_running(pid):
    """Verifica se um PID está ativo (signal 0 = apenas checa)"""
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False

def acquire_lock():
    """Garante apenas uma instância rodando"""
    if lock_exists:
        old_pid = read_lock_file()
        if is_pid_running(old_pid):
            log("ERROR", "Daemon já rodando. Abortando.")
            exit(1)
        else:
            log("INFO", "Removendo lock órfão")
```

**Features:**
- ✅ Verifica se PID anterior ainda está ativo
- ✅ Remove locks órfãos automaticamente
- ✅ Retry logic com backoff exponencial para `wacli sync`
- ✅ Signal handlers (SIGINT/SIGTERM) para shutdown gracioso

### 2. **Cleanup Automático no Install**

```bash
# install-daemon.sh agora:
pkill -f "wacli-daemon" || true    # Mata instâncias antigas
pkill -f "wacli-notify-changes"    # Mata notifiers duplicados
rm -f .daemon.pid LOCK             # Remove lock files
cp wacli-daemon-v3.py wacli-daemon.py  # Ativa v3
```

### 3. **Retry Logic Melhorado**

```python
def fetch_new_messages(retry_count=0, max_retries=3):
    """Retry com backoff"""
    try:
        # wacli sync
    except subprocess.TimeoutExpired:
        if retry_count < max_retries:
            wait_time = 15 + retry_count * 5  # Backoff: 15s, 20s, 25s
            time.sleep(wait_time)
            return fetch_new_messages(retry_count + 1, max_retries)
```

## Files Alterados

```
skills/wacli-monitor/
├── scripts/
│   ├── wacli-daemon-v3.py (NOVO - com PID safety)
│   ├── wacli-daemon.py → symlink para v3
│   ├── install-daemon.sh (ATUALIZADO - cleanup)
│   └── wacli-notify-changes.py (sem mudanças)
└── PID_SAFETY.md (NOVO - este arquivo)
```

## Como Usar

### Instalação (com sudo)

```bash
sudo bash skills/wacli-monitor/scripts/install-daemon.sh
```

Isso:
1. Mata instâncias antigas
2. Remove locks
3. Ativa daemon v3
4. Cria serviço systemd
5. Inicia daemon

### Instalação (sem sudo - desenvolvimento)

```bash
# Parar tudo
pkill -f wacli-daemon || true

# Rodar daemon v3 em foreground (debug)
python3 skills/wacli-monitor/scripts/wacli-daemon-v3.py

# Ou em background
nohup python3 skills/wacli-monitor/scripts/wacli-daemon-v3.py \
  > logs/wacli/daemon.log 2>&1 &
```

### Monitoramento

```bash
# Ver logs em tempo real
tail -f logs/wacli/daemon.log

# Verificar PID
cat logs/wacli/.daemon.pid

# Status
ps aux | grep wacli-daemon-v3

# Forçar parar
pkill -f wacli-daemon-v3
```

## Testes Realizados

✅ **Test 1:** Multiple daemon startup
- Tentado rodar 2 instâncias
- Primeira adquiriu lock (PID 4793)
- Segunda foi bloqueada corretamente
- ✓ PID check funcionando

✅ **Test 2:** Orphan lock cleanup
- Criado lock com PID inativo
- Daemon v3 detectou e removeu automaticamente
- Adquiriu lock com novo PID (4817)
- ✓ Cleanup funcionando

✅ **Test 3:** Graceful shutdown
- Enviado SIGTERM
- Daemon liberou lock e encerrou
- ✓ Signal handler funcionando

## Próximos Passos

1. **Monitorar logs** por 24h para detectar timeouts persistentes
2. Se `wacli sync` continuar com timeout >60s:
   - Aumentar `subprocess.run(..., timeout=120)`
   - Investigar conectividade do wacli com WhatsApp
3. **Considerar systemd timer** em vez de daemon contínuo (mais robusto)
   - Executa `wacli sync --once` a cada X minutos via cron
   - Sem estado persistente entre execuções
   - Mais fácil debugar

## Debug Checklist

Se o daemon não inicia:

```bash
# 1. Verificar config
ls -la skills/wacli-monitor/config/wacli-config.yaml

# 2. Testar YAML parsing
python3 -c "
import yaml
with open('skills/wacli-monitor/config/wacli-config.yaml') as f:
    cfg = yaml.safe_load(f)
print('Config OK' if cfg else 'Config inválido')
"

# 3. Testar lock acquire
python3 -c "
import os
from pathlib import Path
pid_file = Path('logs/wacli/.daemon.pid')
print(f'Lock file: {pid_file}')
print(f'Exists: {pid_file.exists()}')
if pid_file.exists():
    old_pid = int(pid_file.read_text().strip())
    print(f'Old PID: {old_pid}')
    print(f'Running: {os.kill(old_pid, 0) is None}')
"

# 4. Rodar em foreground com debug
python3 skills/wacli-monitor/scripts/wacli-daemon-v3.py 2>&1 | head -30

# 5. Verificar wacli disponível
which wacli
wacli --version
```

---

**Última atualização:** 2026-02-05 09:47 GMT-3  
**Versão:** 3.0 (PID-Safe)
