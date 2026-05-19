# Tema 18 — Firewall por Regras + Testes Automatizados

Firewall baseado em **nftables** com topologia de rede simulada usando **Linux network namespaces** e suite de testes automatizados em **Python (pytest)**.

## Arquitetura

```
 EXTERNAL (ns-wan)           INTERNAL (ns-lan, ns-lan2)
 10.0.1.10                    10.0.2.10, 10.0.2.20
      |                              |
      | veth-fw-wan          br-lan (bridge)
      |                       |           |
      +------ FIREWALL ------+     veth-fw-lan, veth-fw-lan2
      |       (ns-fw)
      | veth-fw-dmz
      |
 DMZ (ns-dmz)
 10.0.3.10
```

### Zonas

| Zona | Namespace | Rede | Papel |
|------|-----------|------|-------|
| WAN | ns-wan | 10.0.1.0/24 | Internet (hosts externos) |
| LAN | ns-lan, ns-lan2 | 10.0.2.0/24 | Rede interna (workstations) |
| DMZ | ns-dmz | 10.0.3.0/24 | Servidores expostos (web, DNS) |
| Firewall | ns-fw | Todas | Gateway e firewall central |

### Regras implementadas

- **Stateful filtering** — `ct state established,related accept` em todas as chains
- **Default deny** — policy `drop` em input e forward
- **Zone-based forwarding** — regras por interface (WAN/LAN/DMZ)
- **Named sets** — portos permitidos mantidos em sets nomeados
- **NAT** — DNAT para serviços da DMZ, masquerade para tráfego LAN->WAN
- **Rate limiting** — ICMP ao firewall limitado a 5/segundo
- **Logging** — pacotes dropped são logados com prefixos distintos
- **DMZ isolation** — DMZ nunca consegue alcançar a LAN
- **WAN isolation** — WAN nunca consegue alcançar a LAN diretamente

## Pré-requisitos

- Linux com kernel >= 4.10 (Raspberry Pi OS ou Ubuntu)
- nftables instalado (`sudo apt install nftables`)
- Python 3.8+
- Root/sudo access

```bash
pip install -r requirements.txt
```

## Utilização

### Rápido (tudo de uma vez)

```bash
sudo make all
```

Isto cria a topologia, corre os testes e limpa tudo no final.

### Passo a passo

```bash
# 1. Verificar pré-requisitos
make check

# 2. Criar topologia e aplicar regras
sudo make setup

# 3. Correr testes
sudo make test

# 4. (Opcional) Gerar relatório HTML
sudo make report

# 5. Limpar
sudo make teardown
```

### Inspecionar regras ativas

```bash
sudo bash scripts/show-rules.sh
```

### Re-aplicar regras sem recriar topologia

```bash
sudo bash scripts/apply-rules.sh
```

## Estrutura dos testes

| Ficheiro | Testes | Descrição |
|----------|--------|-----------|
| `test_basic_filtering.py` | 20 | Filtragem por porto/zona (WAN->DMZ, WAN->LAN, LAN->WAN, etc.) |
| `test_stateful.py` | 5 | Connection tracking (established, related, invalid) |
| `test_nat.py` | 6 | DNAT (WAN->DMZ) e masquerade (LAN->WAN) |
| `test_rate_limiting.py` | 6 | Rate limiting de ICMP |
| `test_logging.py` | 5 | Verificação de logs de pacotes dropped |
| `test_protocol_filtering.py` | 9 | Filtragem por protocolo (TCP, UDP, ICMP) |

## Estrutura do projeto

```
├── setup.sh                    # Cria namespaces, veth pairs, bridge, IPs, rotas
├── teardown.sh                 # Destrói toda a topologia
├── Makefile                    # Targets de conveniência
├── requirements.txt            # Dependências Python
├── nftables/
│   ├── firewall.nft            # Regras de filtragem (input, forward, output)
│   └── nat.nft                 # Regras NAT (DNAT, masquerade)
├── scripts/
│   ├── apply-rules.sh          # Recarrega regras nftables
│   ├── start-services.sh       # Inicia serviços dummy (netcat)
│   └── show-rules.sh           # Mostra regras ativas
├── tests/
│   ├── conftest.py             # Fixtures pytest (setup/teardown da topologia)
│   ├── helpers.py              # Funções utilitárias (run_in_ns, tcp_connect, etc.)
│   ├── test_basic_filtering.py
│   ├── test_stateful.py
│   ├── test_nat.py
│   ├── test_rate_limiting.py
│   ├── test_logging.py
│   └── test_protocol_filtering.py
└── docs/
    └── rules-explanation.md    # Explicação detalhada das regras
```
