# Conversation Batching (v2)

**Aguarde mais mensagens antes de notificar - evite spam!**

## O Problema

```
User1 sends: "Olá"
→ Notificação imediata

1 minuto depois...
User1 sends: "Estou com um problema aqui..."
→ Outra notificação

❌ Resultado: 2 notificações para 1 conversa
```

## A Solução

```
User1 sends: "Olá"
→ Aguarda...

1 minuto depois...
User1 sends: "Estou com um problema aqui..."
→ Aguarda...

2 minutos no total → Notificação UMA VEZ com ambas
✅ Resultado: 1 notificação agrupada
```

## Configuração

### Setup Básico

```yaml
monitor:
  conversation_batching:
    enabled: true
    default_wait: "2m"          # Aguarda 2 minutos
    short_message_threshold: 50 # Se <50 chars, aproveita o tempo
    vip_list: []                # Deixe vazio para padrão
```

### Com VIP List (Contatos VIP notificam imediatamente)

```yaml
monitor:
  conversation_batching:
    enabled: true
    default_wait: "2m"
    vip_list:
      - "Mom"
      - "Boss"
      - "Wife"
      - "Emergency Hotline"
```

## Exemplos

### Exemplo 1: Padrão (tudo aguarda 2 min)

```yaml
conversation_batching:
  enabled: true
  default_wait: "2m"
  vip_list: []
```

**Comportamento:**
- Contato qualquer envia "Oi" → Aguarda 2 min
- Se enviar mais no intervalo → Agrupa
- Após 2 min → Notifica tudo junto

### Exemplo 2: Contatos VIP notificam imediatamente

```yaml
conversation_batching:
  enabled: true
  default_wait: "2m"
  vip_list:
    - "Mom"
    - "Doctor"
    - "Boss"
```

**Comportamento:**
- Mom envia "Olá" → Notifica AGORA
- Friend envia "Oi" → Aguarda 2 min depois notifica

### Exemplo 3: Minimizar notificações (batch 5 min)

```yaml
conversation_batching:
  enabled: true
  default_wait: "5m"           # 5 minutos
  short_message_threshold: 50
  vip_list: ["Mom", "Emergency"]
```

**Resultado:** Menos notificações, mais agrupadas

## Entendendo `short_message_threshold`

Mensagens muito curtas são consideradas "incompletas":

```
threshold: 50  (padrão)

"Oi"            → 2 chars < 50 → Aguarda mais
"Olá, tudo bem" → 13 chars < 50 → Aguarda mais
"Oi, vou chegar em 5 minutos amanhã" → 35 chars < 50 → Aguarda
"Oi, vou chegar em 5 minutos amanhã mais ou menos..." → 55 chars > 50 → Aguarda normalmente
```

**Mudar para ser mais agressivo:**

```yaml
short_message_threshold: 100  # Só mensagens MUITO curtas aguardam
```

## Instalação da v2

1. **Backup da v1 (opcional):**
   ```bash
   sudo systemctl stop wacli-daemon
   ```

2. **Usar v2:**
   ```bash
   cp scripts/wacli-daemon-v2.py scripts/wacli-daemon.py
   chmod +x scripts/wacli-daemon.py
   ```

3. **Restart:**
   ```bash
   sudo systemctl restart wacli-daemon
   ```

4. **Monitor:**
   ```bash
   sudo journalctl -u wacli-daemon -f
   ```

## Logs

Veja o que está acontecendo:

```bash
# Acompanhar em tempo real
sudo journalctl -u wacli-daemon -f

# Procurar por batching
sudo journalctl -u wacli-daemon -f | grep "aguardando\|pronta"

# Ver último 1 hora
sudo journalctl -u wacli-daemon --since 1h
```

**Output exemplo:**

```
[2026-02-05 08:45:30] [INFO] Processadas 3 mensagens (aguardando batching...)
[2026-02-05 08:45:32] [INFO] VIP 'Mom': notificando imediatamente (1 msgs)
[2026-02-05 08:46:15] [INFO] 'Friend': pronta (2 msgs, curta e aguardou)
```

## Behavioral Guide

### Quando usar curtos delays (0-1 min)

- Chats de trabalho urgente
- Emergências
- Tempo-sensível

```yaml
vip_list: ["Emergency", "Boss - Urgent"]
```

### Quando usar delays normais (2-5 min)

- Chats pessoais
- Grupos de amigos
- Conversas do dia

```yaml
default_wait: "3m"
```

### Quando usar delays longos (10-30 min)

- Grupos grandes
- Notificações automáticas
- Quando quer minimizar interruptions

```yaml
default_wait: "30m"
```

## Desabilitar Conversation Batching

Se quiser voltar ao comportamento antigo:

```yaml
conversation_batching:
  enabled: false
```

Cada mensagem notifica imediatamente (cuidado com spam!).

## Troubleshooting

### "Não estou recebendo notificações"

Verifique se a conversa foi adicionada:

```bash
sudo journalctl -u wacli-daemon -f | grep -i "pronta\|aguardando"
```

Se nada aparecer: Pode estar no blacklist.

### "Muitas notificações ainda"

Aumentar `default_wait`:

```yaml
default_wait: "5m"  # Aumentar de 2m
```

### "Contato não está no VIP"

Verificar nome exato:

```bash
# Ver nomes no banco
sqlite3 ~/.wacli/wacli.db "SELECT DISTINCT sender_name FROM messages LIMIT 20"
```

Copie o nome exato para `vip_list`.

## Performance

- CPU: <1% (idle)
- Memory: ~60MB (v2 vs 50MB v1)
- Overhead: Mínimo (apenas agrupa em memória)

---

**Questions?** Check `references/advanced.md`
