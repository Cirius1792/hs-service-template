# Homelab Service Template

Questo repository fornisce un **template standard** per creare nuovi repository di servizi da rilasciare nel homelab tramite:

- Docker Compose
- Dokploy (deploy automatico)
- Traefik (reverse proxy)
- Homepage (dashboard)
- Uptime Kuma (monitoring)

Il template è progettato per essere **usato tramite Cookiecutter** e per supportare:
- configurazione come codice
- deploy automatico da Git
- validazione CI portabile
- release notes automatiche

---

## Prerequisiti

Sul sistema da cui inizializzi un nuovo servizio devono essere disponibili:

- `git`
- `cookiecutter`
- `docker` (per sviluppo/test locale, opzionale)

Per la CI:
- `sh`
- `gitleaks`
- `node` + `semantic-release`

---

## Creazione di un nuovo servizio

### 1. Generazione repository

Usa Cookiecutter puntando a questo repository:

```bash
cookiecutter https://github.com/<org>/clt-hs-compose-template.git
```

Ti verranno richieste alcune informazioni di base:

- nome del servizio (usato come subdomain)
- gruppo Homepage
- icona Homepage
- porta interna del servizio

Al termine verrà generata una nuova directory contenente il repository del servizio.

---

### 2. Configurazione del servizio

Nel repository generato:

1. Compila il file `.env` a partire da `.env.example`
2. Aggiorna l'immagine Docker in `docker-compose.yml`
3. Verifica le label Traefik e Homepage (già preconfigurate)

Tutte le variabili obbligatorie sono documentate nel README del servizio.

---

### 3. Validazione locale (opzionale)

Puoi validare la correttezza del repository prima del push:

```bash
./ci/check.sh
```

Questo script verifica:
- struttura del repository
- completezza delle variabili
- assenza di secret in chiaro (via Gitleaks)

---

### 4. Commit e release

I repository generati utilizzano **Conventional Commits**.

Esempi:

```text
feat: add initial service definition
fix: correct traefik router rule
```

La release viene generata automaticamente tramite:

```bash
./ci/release.sh
```

La release:
- calcola la nuova versione
- aggiorna `CHANGELOG.md`
- crea un tag Git

---

### 5. Deploy

Una volta pushato il repository:

- Dokploy rileva le modifiche
- esegue `docker compose up -d`
- Traefik espone il servizio
- Homepage aggiorna la dashboard

---

## Filosofia del template

- Git è l'unica fonte di verità
- Nessuna configurazione manuale post-deploy
- CI portabile, senza logica vendor-specific
- Nessun valore hardcoded
- Osservabilità separata dal deploy

---

## Documentazione

- `REQUIREMENTS.md` – requisiti e convenzioni
- `ci/check.sh` – validazione repository
- `ci/release.sh` – processo di release

---

## Obiettivo

> Creare un nuovo servizio deve richiedere solo:
> 1. generare un repository
> 2. configurare il servizio
> 3. fare push

Tutto il resto avviene automaticamente.
# hs-service-template
