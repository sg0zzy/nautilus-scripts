#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import subprocess
from pathlib import Path
import shutil
from multiprocessing import Pool, cpu_count
import os
import time
from datetime import datetime

# --- CONFIGURAZIONE GLOBALE ---
# Numero di processi di conversione da eseguire in parallelo.
NUM_PROCESSES = min(8, cpu_count())

# File per la gestione della coda e del lock in memoria condivisa (/dev/shm è una RAM disk)
QUEUE_FILE = Path("/dev/shm/nautilus_converter_av1_queue.txt")
LOCK_FILE = Path("/dev/shm/nautilus_converter_av1.lock")

# Parametri per FFMPEG. Modificali qui per cambiare le impostazioni di conversione.
FFMPEG_PARAMS = [
    '-map', '0:v',  # Mappa la traccia video
    '-map', '0:a',  # Mappa tutte le tracce audio
    '-c:v', 'av1_nvenc',  # Codec video (NVIDIA hardware encoder)
    '-rc', 'constqp',     # Rate control: Constant Quantization Parameter
    '-cq:v', '19',        # Livello di qualità (più basso è meglio, 19 è molto alto)
    '-preset', 'p7',      # Preset di velocità/qualità (p1-p7, p7 è il più veloce)
    '-c:a', 'copy',       # Copia la traccia audio senza ricodificarla
    '-c:s', 'copy',       # Copia i sottotitoli senza ricodificarli
]
# --- FINE CONFIGURAZIONE ---

# --- GESTIONE LOCK ---
def acquire_lock():
    """
    Tenta di acquisire un lock creando un file.
    Usa una tecnica atomica per evitare race condition.
    Restituisce True se il lock è stato acquisito, False altrimenti.
    """
    try:
        # O_CREAT | O_EXCL è un'operazione atomica: crea il file solo se non esiste.
        fd = os.open(LOCK_FILE, os.O_CREAT | os.O_EXCL)
        os.close(fd)
        return True
    except FileExistsError:
        # Il file esiste già, quindi un altro processo detiene il lock.
        return False

def release_lock():
    """Rilascia il lock eliminando il file."""
    try:
        LOCK_FILE.unlink()
    except FileNotFoundError:
        # Il lock era già stato rilasciato, non è un problema.
        pass

# --- GESTIONE CODA ---
def add_files_to_queue(files_to_add):
    """Aggiunge una lista di file alla coda, evitando duplicati."""
    existing_files = set()
    if QUEUE_FILE.exists():
        with open(QUEUE_FILE, 'r') as f:
            existing_files = set(line.strip() for line in f if line.strip())
    
    new_files_added = 0
    with open(QUEUE_FILE, 'a') as f:
        for file_path in files_to_add:
            if os.path.abspath(file_path) not in existing_files:
                f.write(f"{os.path.abspath(file_path)}\n")
                new_files_added += 1
    return new_files_added

def read_and_remove_from_queue(batch_size):
    """Legge un batch di file dalla coda e li rimuove dal file."""
    if not QUEUE_FILE.exists() or QUEUE_FILE.stat().st_size == 0:
        return []

    # Questa operazione è sicura perché protetta dal lock principale
    with open(QUEUE_FILE, 'r') as f:
        all_files = [line.strip() for line in f.readlines() if line.strip()]

    batch = all_files[:batch_size]
    remaining_files = all_files[batch_size:]

    # Sovrascrive il file con i file rimanenti
    with open(QUEUE_FILE, 'w') as f:
        if remaining_files:
            f.write("\n".join(remaining_files) + "\n")
        # Se non ci sono file rimanenti, il file viene svuotato
    
    return batch

def get_queue_size():
    """Restituisce il numero di file attualmente in coda."""
    if not QUEUE_FILE.exists():
        return 0
    with open(QUEUE_FILE, 'r') as f:
        return len([line for line in f if line.strip()])

# --- FUNZIONI DI UTILITÀ E CONVERSIONE ---
def show_zenity_notification(type, text):
    """Mostra una notifica desktop usando Zenity."""
    try:
        subprocess.run(['zenity', f'--{type}', '--text', text, '--timeout', '8'], check=True)
    except FileNotFoundError:
        print(f"AVVISO: 'zenity' non trovato. Impossibile mostrare la notifica: {text}")
    except Exception as e:
        print(f"Errore durante la visualizzazione della notifica zenity: {e}")

def convert_file(input_file_path_str):
    """
    Funzione che converte un singolo file video.
    Restituisce una tupla (status, messaggio).
    """
    input_path = Path(input_file_path_str)
    if not input_path.is_file():
        return ("error", f"File non trovato (forse già convertito?): {input_path}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = f"{input_path.stem}_{timestamp}_av1.mkv"
    
    output_path = input_path.parent / output_filename
    # Usa un nome di file temporaneo univoco per evitare conflitti tra processi paralleli
    temp_output_path = Path(f"/dev/shm/{os.getpid()}_{output_filename}")

    if temp_output_path.exists():
        temp_output_path.unlink()

    command = ['nice', '-n', '19', 'ffmpeg', '-hide_banner', '-y', '-i', str(input_path), *FFMPEG_PARAMS, str(temp_output_path)]
    print(f"AVVIO CONVERSIONE: {input_path.name}")

    try:
        result = subprocess.run(command, check=False, capture_output=True, text=True)
        if result.returncode != 0:
            error_msg = f"❌ Errore conversione {input_path.name}:\n{result.stderr[-500:]}"
            print(error_msg)
            if temp_output_path.exists(): temp_output_path.unlink()
            return ("error", error_msg)

        if not temp_output_path.exists():
            return ("error", f"❌ Errore: file temporaneo non creato per {input_path.name}.")

        shutil.move(str(temp_output_path), str(output_path))
        subprocess.run(['gio', 'trash', str(input_path)], check=True)
        return ("success", f"✅ Conversione completata: {output_path.name}")

    except Exception as e:
        error_msg = f"Eccezione imprevista per {input_path.name}: {e}"
        print(error_msg)
        if temp_output_path.exists(): temp_output_path.unlink()
        return ("error", error_msg)

def process_queue():
    """
    Funzione eseguita dal processo "worker" per elaborare l'intera coda in modo dinamico,
    mantenendo il pool di processi sempre pieno.
    """
    total_processed, total_errors = 0, 0
    error_messages = []
    
    # Crea il pool una sola volta
    pool = Pool(processes=NUM_PROCESSES)
    active_tasks = []

    try:
        # Il ciclo continua finché ci sono task attivi O file in coda
        while active_tasks or get_queue_size() > 0:
            # 1. Aggiungi nuovi task se ci sono slot liberi e file in coda
            while len(active_tasks) < NUM_PROCESSES and get_queue_size() > 0:
                file_to_process = read_and_remove_from_queue(1)
                if file_to_process:
                    print(f"Invio al pool: {Path(file_to_process[0]).name}. Task attivi: {len(active_tasks) + 1}/{NUM_PROCESSES}")
                    task = pool.apply_async(convert_file, args=(file_to_process[0],))
                    active_tasks.append(task)

            # 2. Controlla i task completati e raccogli i risultati
            remaining_tasks = []
            for task in active_tasks:
                if task.ready():
                    status, message = task.get()
                    if status == "success":
                        total_processed += 1
                    else:
                        total_errors += 1
                        error_messages.append(message)
                else:
                    # Se il task non è pronto, lo teniamo per il prossimo controllo
                    remaining_tasks.append(task)
            
            active_tasks = remaining_tasks

            # 3. Attendi un po' per non consumare CPU inutilmente
            time.sleep(1)
            
    finally:
        # Assicurati che il pool venga chiuso correttamente
        pool.close()
        pool.join()

    return total_processed, total_errors, error_messages

def main():
    """
    Funzione principale: aggiunge file alla coda e decide se diventare un worker.
    """
    files_to_add = sys.argv[1:]

    if files_to_add:
        added_count = add_files_to_queue(files_to_add)
        queue_size = get_queue_size()
        if added_count > 0:
            show_zenity_notification("info", f"{added_count} nuovi file aggiunti.\nCoda attuale: {queue_size} file.")
        else:
            show_zenity_notification("info", "I file selezionati erano già in coda.")

    if not acquire_lock():
        print("Un'altra istanza è già in esecuzione. I file sono stati aggiunti alla coda. Uscita.")
        sys.exit(0)

    try:
        initial_queue_size = get_queue_size()
        if initial_queue_size == 0:
            print("Coda vuota. Nessuna operazione da eseguire.")
            return

        print(f"Lock acquisito. Avvio elaborazione di {initial_queue_size} file in coda.")
        processed, errors, error_msgs = process_queue()

        summary_text = f"--- RIEPILOGO CONVERSIONE ---\n\n"
        summary_text += f"File totali convertiti con successo: {processed}\n"
        summary_text += f"Errori riscontrati: {errors}\n"
        if errors > 0:
            summary_text += "\n--- Dettaglio Errori ---\n" + "\n\n".join(error_msgs)
            show_zenity_notification("warning", summary_text)
        elif processed > 0:
            show_zenity_notification("info", "Tutte le conversioni in coda sono state completate con successo!")

    finally:
        release_lock()
        print("Elaborazione terminata. Lock rilasciato.")

if __name__ == "__main__":
    main()
