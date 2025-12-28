# {{ cookiecutter.service_name | title }}

## Descrizione
Servizio deployato automaticamente tramite Dokploy.

## Variabili obbligatorie
| Variabile | Descrizione |
|---------|-------------|
| SERVICE_NAME | Subdomain del servizio |
| BASE_DOMAIN | Dominio base |
| TZ | Timezone |
| PUID | User ID |
| PGID | Group ID |

## URL pubblico
https://${SERVICE_NAME}.${BASE_DOMAIN}

## Healthcheck
Endpoint HTTP su porta {{ cookiecutter.default_port }}.

## Monitoring
Il servizio può essere monitorato tramite Uptime Kuma usando l'URL pubblico.
