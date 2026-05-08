# Hantavirus Data Engine

Script Python per raccogliere notizie recenti sul tema hantavirus da Google News RSS, tentare la geolocalizzazione delle localita' estratte dal titolo e salvare il risultato in [data/outbreaks.json](/Users/valentinaschiavon/hantavirus/hantavirus-data-engine/data/outbreaks.json).

## Requisiti

```bash
pip install -r requirements.txt
```

## Esecuzione singola

```bash
python fetch_data.py
```

## Aggiornamento automatico ogni 30 minuti

```bash
python fetch_data.py --watch --interval 1800
```

Con `--watch` il processo resta attivo e riscrive [data/outbreaks.json](/Users/valentinaschiavon/hantavirus/hantavirus-data-engine/data/outbreaks.json) a ogni ciclo. `1800` secondi corrispondono a 30 minuti.

Se vuoi l'aggiornamento automatico nel repository anche quando il tuo Mac e' spento, e' disponibile il workflow GitHub Actions in [.github/workflows/update_data.yml](/Users/valentinaschiavon/hantavirus/hantavirus-data-engine/.github/workflows/update_data.yml). Dopo il push su GitHub, il job verra' eseguito ogni 30 minuti, evitera' esecuzioni sovrapposte, fara' fino a 3 tentativi in caso di errore transitorio e fara' commit del file JSON solo quando ci sono modifiche.

## Output

Il file JSON contiene, per ogni voce:

- `id`
- `title`
- `link`
- `location_name`
- `coordinates`
- `published`
- `source`
- `fetch_timestamp`