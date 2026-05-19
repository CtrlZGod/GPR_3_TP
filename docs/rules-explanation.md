# Explicação das Regras nftables

## Tabela `inet firewall`

Usa a família `inet` que aplica a IPv4 e IPv6 simultaneamente.

### Chain `input` (tráfego para o próprio firewall)

| Regra | Propósito |
|-------|-----------|
| `ct state established,related accept` | Permite respostas a conexões iniciadas pelo firewall |
| `ct state invalid drop` | Descarta pacotes com estado de conexão inválido |
| `iif "lo" accept` | Permite tráfego loopback (necessário para serviços locais) |
| `icmp echo-request limit rate 5/second` | Permite ping ao firewall, mas limita a 5/s para prevenir flood |
| `iifname "br-lan" tcp dport 22 accept` | SSH permitido apenas a partir da LAN (administração) |
| `log prefix "[FW-INPUT-DROP]" drop` | Loga e descarta todo o resto (default deny) |

### Chain `forward` (tráfego que atravessa o firewall)

**Princípios:**
1. Stateful first — conexões estabelecidas passam sempre
2. Regras explícitas por direção (interface entrada -> interface saída)
3. Bloqueios críticos com logging específico
4. Default deny no final

| Direção | Portos/Protocolos | Justificação |
|---------|-------------------|-------------|
| WAN -> DMZ | TCP 80, 443, 53; UDP 53 | Serviços públicos (web, DNS) |
| LAN -> WAN | TCP 80, 443; UDP/TCP 53 | Acesso internet para utilizadores |
| LAN -> DMZ | TCP 80, 443, 22, 53; UDP 53 | Acesso a serviços + SSH para admin |
| DMZ -> WAN | TCP 80, 443; UDP/TCP 53 | Updates e resolução DNS |
| ICMP | echo-request, echo-reply | Diagnóstico entre todas as zonas |
| WAN -> LAN | **BLOQUEADO** | Hosts externos nunca acedem à LAN |
| DMZ -> LAN | **BLOQUEADO** | DMZ comprometida não alcança a LAN |

### Named Sets

- `blacklist` — IPs bloqueados (dinâmico, com timeout automático)
- `allowed_tcp_dmz` — portos TCP permitidos do WAN para DMZ `{80, 443, 53}`
- `rate_limit_ssh` — tracking dinâmico para rate limiting de SSH

## Tabela `ip nat`

### Chain `prerouting` (DNAT)

Redireciona tráfego que chega à interface WAN do firewall para os servidores na DMZ:
- HTTP (80) -> 10.0.3.10:80
- HTTPS (443) -> 10.0.3.10:443
- DNS (53 TCP/UDP) -> 10.0.3.10:53

### Chain `postrouting` (SNAT/Masquerade)

Todo o tráfego que sai pela interface WAN é mascarado com o IP do firewall (10.0.1.1). Isto:
- Esconde os IPs internos da LAN e DMZ
- Permite que múltiplos hosts internos partilhem um único IP público
- Simula o comportamento de um router NAT real
