
# SyncPersonal Win11 - Autonomous Dashboard 🚀

**SyncPersonal** è un'utilità di backup intelligente e ultra-leggera progettata specificamente per l'ambiente Windows 11. A differenza dei comuni software di sincronizzazione, agisce come un "collaboratore silenzioso" che monitora le modifiche e specchia i dati in modo autonomo e non invasivo.

## ✨ Caratteristiche Principali

* **Mirroring Dinamico**: Sincronizza solo ciò che selezioni. Se deselezioni una cartella dall'interfaccia, il programma la rimuove dal backup per mantenere la destinazione pulita e identica alla sorgente (senza mai toccare i file originali).
* **Smart Search & Resilience**: Se scolleghi il disco di backup e lo ricolleghi a una porta USB diversa (cambiando lettera di unità), il software scansiona automaticamente tutti i volumi connessi per ritrovare la destinazione, escludendo intelligentemente il disco sorgente.
* **Permission Guard**: Gestisce i divieti di accesso di Windows (es. cartelle di sistema o `AppData`). Le cartelle protette vengono visualizzate con l'icona 🚫 e saltate durante il backup per evitare crash o blocchi.
* **Zero-Distraction UI**: L'interfaccia si riduce automaticamente nella *System Tray* (vicino all'orologio) dopo la configurazione, lavorando nell'ombra.
* **Persistenza del Lavoro**: Tutte le selezioni (le spunte `☑`) e lo stato della sincronizzazione vengono salvati in un database JSON locale per essere ripristinati istantaneamente al riavvio del PC.

## 🛠️ Requisiti

Il software è scritto in **Python 3.10+** e utilizza le seguenti librerie:

* `customtkinter`: Per l'interfaccia moderna in stile Win11.
* `psutil`: Per il monitoraggio dinamico dei dischi.
* `pystray` & `Pillow`: Per la gestione dell'icona nella barra di sistema.

## 🚀 Come si usa

1. **Avvio**: Lancia lo script. Se è la prima volta, vedrai i due pannelli vuoti.
2. **Sorgente**: Seleziona l'unità a sinistra e spunta le cartelle che vuoi proteggere.
3. **Destinazione**: Seleziona un'unità diversa a destra e scegli la cartella di destinazione (apparirà una freccia `➤`).
4. **Automazione**: Una volta configurato, il software avvierà il countdown. Puoi chiudere la finestra: l'app rimarrà attiva nella Tray.
5. **Manutenzione**: Se vuoi cambiare disco, usa il pulsante **"REVOCA DESTINAZIONE"** (in rosso tenue) per resettare la configurazione in modo sicuro.

## 📂 Struttura dei Dati

Il software non sporca il registro di sistema. Salva i suoi metadati in:
`%LOCALAPPDATA%\SyncPersonal_Win11\sync_db.json`

## ⚠️ Avvertenze di Sicurezza

* Il software impedisce fisicamente di selezionare la stessa unità come sorgente e destinazione.
* In caso di crash o spegnimento improvviso, il sistema di recovery analizza l'ultimo stato noto per riprendere la sincronizzazione dal punto in cui era rimasta.

---
requirements:

perIl codice sorgente necessita delle seguenti librerie python che si possono  installare tutte con un solo comando di terminale:
`pip install customtkinter psutil pystray Pillow`
