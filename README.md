# Hantavirus Data Engine

Script Python per raccogliere notizie recenti sul tema hantavirus da piu' sorgenti RSS, deduplicarle, estrarre localita' dal titolo, dalla descrizione HTML del feed e, quando utile, dalla pagina originale dell'articolo, geocodificarle con Nominatim e fallback Photon e salvare il risultato in [data/outbreaks.json](data/outbreaks.json). Quando una voce non contiene una localita' abbastanza esplicita, il motore applica una inferenza finale basata su contesto, sorgente e cluster dell'evento in modo da assegnare comunque coordinate a ogni record.

Sorgenti attualmente usate:

- Google News RSS
- PAHO RSS
- ECDC News feed
- ECDC Threat Report feed

Per i feed non Google, lo script mantiene solo le voci che contengono keyword rilevanti come `hantavirus`, `orthohantavirus` o `hps`. Per Google News applica inoltre un filtro sul titolo per scartare explainers, opinioni e pezzi solo speculativi che contengono la keyword ma non descrivono un evento concreto. Le voci duplicate vengono rimosse usando titolo e link. Quando viene trovata piu' di una localita', il JSON conserva sia il campo principale retrocompatibile sia l'elenco completo delle localita' geocodificate; se non viene trovata una localita' affidabile nel testo, il motore assegna un fallback coerente con il contesto dell'articolo.

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

Con `--watch` il processo resta attivo e riscrive [data/outbreaks.json](data/outbreaks.json) a ogni ciclo. `1800` secondi corrispondono a 30 minuti.

Se vuoi l'aggiornamento automatico nel repository anche quando il tuo Mac e' spento, e' disponibile il workflow GitHub Actions in [.github/workflows/update_data.yml](.github/workflows/update_data.yml). Dopo il push su GitHub, il job verra' eseguito ogni 30 minuti, evitera' esecuzioni sovrapposte, fara' fino a 3 tentativi in caso di errore transitorio e fara' commit del file JSON solo quando ci sono modifiche.

## CI/CD

Il repository usa due workflow GitHub Actions distinti:

- CI: [.github/workflows/ci.yml](.github/workflows/ci.yml) viene eseguito su push, pull request e avvio manuale; installa le dipendenze, verifica la sintassi di `fetch_data.py`, controlla che [data/outbreaks.json](data/outbreaks.json) sia JSON valido e lancia i test offline in `tests/`
- CD: [.github/workflows/update_data.yml](.github/workflows/update_data.yml) esegue gli stessi controlli offline e poi aggiorna automaticamente [data/outbreaks.json](data/outbreaks.json) ogni 30 minuti o su esecuzione manuale, con commit automatico solo se il dataset cambia

## Output

Il file JSON contiene, per ogni voce:

- `id`
- `title`
- `link`
- `location_name`: localita' primaria selezionata per retrocompatibilita'
- `coordinates`: coordinate della localita' primaria
- `location_method`: come e' stata scelta la localita' primaria (`extracted`, `inferred`, `fallback`)
- `location_confidence`: livello qualitativo associato alla localita' primaria (`high`, `medium`, `low`)
- `locations`: elenco delle localita' geocodificate trovate per la stessa voce
- `published`
- `source`
- `fetch_timestamp`

Note operative:

- `location_name` e `coordinates` restano presenti per retrocompatibilita'
- `locations` contiene fino a piu' localita' geocodificate per la stessa notizia, ciascuna con `method` e `confidence`
- ogni record riceve coordinate anche quando la localita' viene inferita da contesto e fallback

## Consumo a valle

[data/outbreaks.json](data/outbreaks.json) e' la sorgente dati canonica del progetto. Il repository `hantavirus-visualizer` lo scarica nel proprio workflow (dalla URL raw di GitHub) e lo serve come `public/outbreak.json`, da cui leggono sia la mappa React sia il bot Telegram. Lo schema sopra e' percio' retrocompatibile con entrambi i consumatori: usano `title`, `link`, `published`, `source`, `location_name` e `coordinates`, ignorando i campi aggiuntivi.