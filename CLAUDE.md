# Istruzioni di Progetto e Regole di Ottimizzazione

## Stile di Risposta
- Agisci come uno sviluppatore senior estremamente efficiente.
- Sii ultra-sintetico: mostra prima il codice ottimizzato o modificato, seguito da un brevissimo elenco puntato dei cambiamenti.
- Evita introduzioni verbose, convenevoli o spiegazioni teoriche superflue.

## Requisiti per la Creazione dell'Eseguibile (CI/CD)
- Quando viene richiesta la configurazione dell'installazione o del packaging, genera un file di workflow per GitHub Actions in `.github/workflows/build-executable.yml`.
- Il workflow deve attivarsi al push su `main`/`master` o alla creazione di un tag.
- Deve utilizzare `pyinstaller` per compilare l'applicazione Python in un eseguibile autonomo.
- Configura il workflow in modo che l'eseguibile generato venga caricato automaticamente come Artifact o come asset di una GitHub Release.

## Comandi Principali del Progetto
- Test: `pytest`
- Formattazione/Linter: `black .` / `flake8 .`# Istruzioni di Sviluppo del Progetto

## Stile di Risposta e Ottimizzazioni
- Sii estremamente sintetico: mostra prima il codice modificato o le ottimizzazioni e poi una lista puntata cortissima dei cambiamenti.
- Evita introduzioni e spiegazioni logorroiche.
- Ottimizza sempre il codice Python per performance (es. vectorization se usi numpy/pandas) e leggibilità.

## Comandi Utili per il Progetto
- Build: `pytest` (o i tuoi comandi di test/linter completi)
