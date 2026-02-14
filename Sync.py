import os
import json
import psutil
import shutil
import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk
import customtkinter as ctk
import threading

from PIL import Image, ImageDraw
import pystray
from pystray import MenuItem as item

class SyncApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("SyncPersonal Win11 - Autonomous Dashboard")
        self.geometry("1100x850")

        # CONFIGURAZIONE TEMPI [Art. 3.2]   in millisecondi
        self.ritardo_esecuzione = 20000     # ritardo partenza della copia
        self.ritardo_tray = 45000           # ritado riduzione automatica ad icona in system tray     

        # Gestione eventi finestra
        self.protocol("WM_DELETE_WINDOW", self.minimize_to_tray)
        self.bind("<Unmap>", self.on_minimize)

        # 1. REGISTRO NOMI E STATI
        self.app_data_dir = Path(os.getenv('LOCALAPPDATA')) / "SyncPersonal_Win11"
        self.metadata_file = self.app_data_dir / "sync_db.json"
        
        self.source_drive = tk.StringVar()
        self.target_drive = tk.StringVar()
        self.TargetRootPath = tk.StringVar()
        
        self.last_sync_time = "--:--:--"
        self.last_sync_status = "IDLE"
        self.total_files_synced = 0
        self.folders_count = 0
        self.sync_timer_id = None 

        self.CHECKED_CHAR = "☑ "
        self.UNCHECKED_CHAR = "☐ "
        self.PARTIAL_CHAR = "◩ "

        self.ensure_appdata_dir()
        self.init_gui()
        self.setup_tray()
        
        # 2. BINDING E RECOVERY
        self.LeftTree.bind("<Double-1>", self.toggle_left_node)
        self.RightTree.bind("<ButtonRelease-1>", self.select_right_node)
        self.check_recovery_status()

    def ensure_appdata_dir(self):
        if not self.app_data_dir.exists():
            self.app_data_dir.mkdir(parents=True)

    def check_recovery_status(self):
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r') as f:
                    data = json.load(f)
                    self.source_drive.set(data.get("source_drive", ""))
                    
                    # FIX: Correzione chiave JSON e integrazione Smart Search [Art. 7.4]
                    saved_target_drive = data.get("target_drive_letter", "")
                    saved_rel_path = data.get("target_relative_path", "")
                    
                    # Se il drive salvato non esiste più, cerca ovunque
                    if saved_target_drive and not os.path.exists(saved_target_drive):
                        found_path = self.find_destination_on_any_drive(saved_rel_path)
                        if found_path:
                            saved_target_drive = os.path.splitdrive(found_path)[0] + "\\"
                            self.TargetRootPath.set(found_path)
                    else:
                        # Ricostruisce il path completo se il drive è ancora lì
                        if saved_target_drive and saved_rel_path:
                            self.TargetRootPath.set(os.path.join(saved_target_drive, saved_rel_path))

                    self.target_drive.set(saved_target_drive)
                    
                    # Carichiamo gli alberi se i drive sono salvati
                    if self.source_drive.get(): self.tree_insert_folders("left")
                    if self.target_drive.get(): self.tree_insert_folders("right")
                    
                    # Ripristiniamo le spunte
                    saved_checks = data.get("checked_items", [])
                    self.restore_checks(saved_checks)
                    
                    # ... resto della logica (UI, Tray, ecc.) ...
            except Exception as e: print(f"Errore recovery: {e}")

   
    def save_config(self):
        # 1. Raccogliamo i percorsi selezionati (☑)
        checked_paths = []
        def collect_checked(node_id):
            txt = self.LeftTree.item(node_id, "text")
            if txt.startswith(self.CHECKED_CHAR):
                checked_paths.append(self.get_full_path(self.LeftTree, node_id, self.source_drive.get()))
            for child in self.LeftTree.get_children(node_id):
                collect_checked(child)
        
        for root_node in self.LeftTree.get_children(""):
            collect_checked(root_node)

        # 2. Scomponiamo la destinazione per la "Smart Search"
        target_path = self.TargetRootPath.get()
        drive_letter, rel_path = "", ""
        if target_path:
            drive_letter = os.path.splitdrive(target_path)[0] + "\\"
            rel_path = os.path.relpath(target_path, drive_letter)

        data = {
            "source_drive": self.source_drive.get(),
            "target_drive_letter": drive_letter,
            "target_relative_path": rel_path,
            "checked_items": checked_paths, # Persistenza spunte
            "last_sync_time": self.last_sync_time,
            "last_sync_status": self.last_sync_status
        }
        
        with open(self.metadata_file, 'w') as f:
            json.dump(data, f, indent=4)
    
    def init_gui(self):
        """Inizializzazione completa dell'interfaccia grafica [Art. 4]."""
        # Configurazione Stile Treeview per Windows 11
        style = ttk.Style()
        style.configure("Treeview", font=("Segoe UI", 11), rowheight=28)
        style.configure("Treeview.Heading", font=("Segoe UI", 12, "bold"))

        # Layout principale a due colonne
        self.grid_columnconfigure((0, 1), weight=1)
        self.grid_rowconfigure(0, weight=1)

        for i, title in enumerate(["SORGENTE", "DESTINAZIONE"]):
            frame = ctk.CTkFrame(self)
            frame.grid(row=0, column=i, padx=10, pady=10, sticky="nsew")
            
            ctk.CTkLabel(frame, text=title, font=("Segoe UI", 15, "bold")).pack(pady=5)
            
            # Pannello selezione Drive
            drive_cont = ctk.CTkFrame(frame)
            drive_cont.pack(fill="x", padx=5)
            var = self.source_drive if i == 0 else self.target_drive
            side = "left" if i == 0 else "right"
            
            # Scansione dinamica delle unità connesse [Art. 7]
            for d in [d.device for d in psutil.disk_partitions() if 'fixed' in d.opts or 'removable' in d.opts]:
                ctk.CTkRadioButton(drive_cont, text=d, variable=var, value=d, font=("Segoe UI", 12),
                                   command=lambda s=side: self.tree_insert_folders(s)).pack(side="left", padx=5)

            # Creazione Albero Directory
            tree = ttk.Treeview(frame)
            # Tag per visualizzare in grigio le cartelle senza permessi di accesso [Art. 8.2]
            tree.tag_configure('access_denied', foreground='gray') 
            tree.pack(expand=True, fill="both", padx=5, pady=5)
            
            if i == 0:
                self.LeftTree = tree
            else:
                self.RightTree = tree
                # Pulsante di RESET per revocare la destinazione selezionata
                self.BtnReset = ctk.CTkButton(frame, text="REVOCA DESTINAZIONE", 
                                              fg_color="#E57373", hover_color="#EF5350",
                                              font=("Segoe UI", 12, "bold"),
                                              command=self.reset_destination)
                self.BtnReset.pack(pady=5, fill="x", padx=10)

        # FOOTER: Pannello di Stato e Statistiche
        self.Footer = ctk.CTkFrame(self, height=150)
        self.Footer.grid(row=1, column=0, columnspan=2, padx=10, pady=10, sticky="nsew")
        self.Footer.grid_columnconfigure((0, 1, 2), weight=1)
        
        # Colonna 1: Stato Operativo
        self.StatusCont = ctk.CTkFrame(self.Footer, fg_color="transparent")
        self.StatusCont.grid(row=0, column=0, padx=15, pady=10, sticky="w")
        
        self.StatusDot = ctk.CTkLabel(self.StatusCont, text="●", font=("Segoe UI", 26), text_color="gray")
        self.StatusDot.pack(side="left")
        
        self.LabelStatus = ctk.CTkLabel(self.StatusCont, text="STATO: ATTESA", font=("Segoe UI", 14, "bold"))
        self.LabelStatus.pack(side="left", padx=8)
        
        self.LabelDest = ctk.CTkLabel(self.Footer, text="DEST: ---", font=("Segoe UI", 12))
        self.LabelDest.grid(row=1, column=0, padx=15, sticky="w")

        # Colonna 2: Informazioni Temporali
        self.LabelLastSync = ctk.CTkLabel(self.Footer, text="ULTIMO BACKUP: mai", font=("Segoe UI", 12))
        self.LabelLastSync.grid(row=0, column=1)
        
        self.LabelNext = ctk.CTkLabel(self.Footer, text="Pronto per la configurazione", 
                                      font=("Segoe UI", 11, "italic"), text_color="#1E90FF")
        self.LabelNext.grid(row=1, column=1)

        # Colonna 3: Contatori File
        self.LabelStats = ctk.CTkLabel(self.Footer, text="FILES: 0 | CARTELLE: 0", font=("Segoe UI", 12))
        self.LabelStats.grid(row=0, column=2, padx=15, sticky="e")

    
    def ignore_inaccessible(self, dir, contents):
        """Callback per shutil.copytree: salta file/cartelle senza permessi [Art. 8.2]."""
        ignored = []
        for name in contents:
            full_path = os.path.join(dir, name)
            if not os.access(full_path, os.R_OK):
                ignored.append(name)
        return ignored

    def trigger_smart_sync(self):
        if self.sync_timer_id: self.after_cancel(self.sync_timer_id)
        self.update_ui_safe(self.LabelStatus.configure, text="MODIFICHE RILEVATE", text_color="#1E90FF")
        self.update_ui_safe(self.StatusDot.configure, text_color="#1E90FF")
        self.update_ui_safe(self.LabelNext.configure, text="Sincronizzazione programmata...")
        self.sync_timer_id = self.after(self.ritardo_esecuzione, self.run_sync_thread)

    def run_sync_thread(self):
        if not self.TargetRootPath.get():
            self.LabelStatus.configure(text="SYNC SOSPESA: NO DEST", text_color="orange")
            return
        threading.Thread(target=self.sync_engine, daemon=True).start()
    
    def update_ui_safe(self, func, *args, **kwargs):
        """Helper per aggiornare la UI dal thread in modo sicuro."""
        self.after(0, lambda: func(*args, **kwargs))

    def sync_engine(self):
        """Motore Mirroring Resistente: ignora i blocchi di sistema [Art. 8]."""
        try:
            self.last_sync_status = "IN_PROGRESS"
            self.after(0, self.save_config) # Save config deve girare nel main thread se tocca la UI (Treeview)
            self.update_ui_safe(self.StatusDot.configure, text_color="red")
            self.update_ui_safe(self.LabelStatus.configure, text="SINCRONIZZAZIONE...", text_color="red")
            
            job_list = self.generate_manifest()
            target_root = self.TargetRootPath.get()
            
            # Mirroring: Pulizia
            allowed_folders = [os.path.basename(job['dst']) for job in job_list]
            if os.path.exists(target_root):
                for entry in os.scandir(target_root):
                    if entry.is_dir() and entry.name not in allowed_folders:
                        try: shutil.rmtree(entry.path)
                        except: pass
            
            self.total_files_synced, self.folders_count = 0, 0
            for job in job_list:
                try:
                    if job['mode'] == 'FULL':
                        shutil.copytree(job['src'], job['dst'], 
                                        dirs_exist_ok=True, 
                                        copy_function=shutil.copy2,
                                        ignore=self.ignore_inaccessible) # Salta divieti
                        for r, d, f in os.walk(job['src']): self.total_files_synced += len(f)
                    elif job['mode'] == 'DIR_ONLY':
                        os.makedirs(job['dst'], exist_ok=True)
                    self.folders_count += 1
                except: continue # Se un intero job fallisce, passa al prossimo

            self.last_sync_time = datetime.datetime.now().strftime("%H:%M:%S")
            self.last_sync_status = "SUCCESS"
            self.update_ui_safe(self.LabelStatus.configure, text="MONITORAGGIO ATTIVO", text_color="green")
            self.update_ui_safe(self.StatusDot.configure, text_color="green")
            self.update_ui_safe(self.LabelLastSync.configure, text=f"ULTIMO BACKUP: {self.last_sync_time}")
            self.update_ui_safe(self.LabelNext.configure, text="IN ATTESA MODIFICHE")
        except:
            self.last_sync_status = "FAILED"
            self.update_ui_safe(self.StatusDot.configure, text_color="orange")
        finally:
            self.sync_timer_id = None
            self.after(0, self.save_config)

    def setup_tray(self):
        icon_img = self.create_tray_icon_img()
        menu = (item('Apri Pannello', self.show_window), item('Esci', self.quit_app))
        self.tray_icon = pystray.Icon("SyncPersonal", icon_img, "SyncPersonal Attivo", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def create_tray_icon_img(self):
        img = Image.new('RGB', (64, 64), color=(30, 144, 255))
        d = ImageDraw.Draw(img)
        d.ellipse((16, 16, 48, 48), fill=(255, 255, 255))
        return img

    def minimize_to_tray(self, event=None):
        """Nasconde la finestra solo se la configurazione è completa [Art. 6.2]."""
        if not self.TargetRootPath.get():
            self.LabelStatus.configure(text="CONFIGURAZIONE INCOMPLETA", text_color="orange")
            self.LabelNext.configure(text="Seleziona una destinazione prima di nascondere")
            return
            
        self.withdraw() # Nasconde l'app solo se c'è un target

    def show_window(self):
        self.deiconify()
        self.attributes("-topmost", True)
        self.after_idle(self.attributes, "-topmost", False)

    def quit_app(self):
        self.tray_icon.stop()
        self.destroy()
        os._exit(0)

    # --- METODI SUPPORTO ALBERI ---

    def tree_insert_folders(self, side):
        tree = self.LeftTree if side == "left" else self.RightTree
        drive = self.source_drive.get() if side == "left" else self.target_drive.get()
        prefix = self.UNCHECKED_CHAR if side == "left" else ""
        for i in tree.get_children(): tree.delete(i)
        
        try:
            for entry in os.scandir(drive):
                if entry.is_dir() and not entry.name.startswith('$'):
                    try:
                        # Test preventivo di lettura [Art. 8.2]
                        os.scandir(entry.path)
                        node = tree.insert("", "end", text=f"{prefix}{entry.name}", open=False)
                        tree.insert(node, "end", text="dummy")
                    except PermissionError:
                        # Rappresentazione visiva del divieto
                        tree.insert("", "end", text=f"🚫 {entry.name} (Proibito)", tags=('access_denied',))
        except: pass
        tree.bind("<<TreeviewOpen>>", lambda e: self.on_tree_expand(e, tree, drive))

    def on_tree_expand(self, event, tree, root_path, target_id=None):
        node_id = target_id if target_id else tree.focus()
        if not node_id: return
        # Impedisce espansione se proibito
        if 'access_denied' in tree.item(node_id, 'tags'): return

        children = tree.get_children(node_id)
        if children and tree.item(children[0], "text") == "dummy":
            tree.delete(children[0])
            full_path = self.get_full_path(tree, node_id, root_path)
            prefix = self.UNCHECKED_CHAR if tree == self.LeftTree else ""
            if tree.item(node_id, "text").startswith(self.CHECKED_CHAR): prefix = self.CHECKED_CHAR
            
            try:
                for entry in os.scandir(full_path):
                    if entry.is_dir() and not entry.name.startswith(('$', '.')):
                        try:
                            os.scandir(entry.path)
                            new_node = tree.insert(node_id, "end", text=f"{prefix}{entry.name}", open=False)
                            tree.insert(new_node, "end", text="dummy")
                        except PermissionError:
                            tree.insert(node_id, "end", text=f"🚫 {entry.name}", tags=('access_denied',))
            except: pass


    def get_full_path(self, tree, item_id, drive_root):
        path_parts = []
        curr = item_id
        while curr:
            raw_text = tree.item(curr, "text")
            clean_text = raw_text.replace(self.CHECKED_CHAR, "").replace(self.UNCHECKED_CHAR, "").replace(self.PARTIAL_CHAR, "").replace("➤ ", "").strip()
            path_parts.append(clean_text)
            curr = tree.parent(curr)
        return os.path.join(drive_root, *reversed(path_parts))

    def toggle_left_node(self, event):
        item_id = self.LeftTree.identify_row(event.y)
        if not item_id or 'access_denied' in self.LeftTree.item(item_id, 'tags'): return
        txt = self.LeftTree.item(item_id, "text")
        state = "CHECKED" if txt.startswith(self.UNCHECKED_CHAR) or txt.startswith(self.PARTIAL_CHAR) else "UNCHECKED"
        self.set_node_state(item_id, state)
        self.update_parent_states(item_id)
        self.trigger_smart_sync()

    def set_node_state(self, item_id, state):
        char = self.CHECKED_CHAR if state == "CHECKED" else self.UNCHECKED_CHAR
        pure_name = self.LeftTree.item(item_id, "text")[2:]
        self.LeftTree.item(item_id, text=char + pure_name)
        children = self.LeftTree.get_children(item_id)
        if children and self.LeftTree.item(children[0], "text") == "dummy":
            self.on_tree_expand(None, self.LeftTree, self.source_drive.get(), target_id=item_id)
            children = self.LeftTree.get_children(item_id)
        for child in children: self.set_node_state(child, state)

    def update_parent_states(self, item_id):
        parent_id = self.LeftTree.parent(item_id)
        if not parent_id: return
        states = [self.LeftTree.item(c, "text")[0] for c in self.LeftTree.get_children(parent_id)]
        if all(s == self.CHECKED_CHAR[0] for s in states): new_char = self.CHECKED_CHAR
        elif all(s == self.UNCHECKED_CHAR[0] for s in states): new_char = self.UNCHECKED_CHAR
        else: new_char = self.PARTIAL_CHAR
        self.LeftTree.item(parent_id, text=new_char + self.LeftTree.item(parent_id, "text")[2:])
        self.update_parent_states(parent_id)

    def select_right_node(self, event):
        item_id = self.RightTree.identify_row(event.y)
        if not item_id: return
        
        # CONTROLLO INCROCIO SORGENTE-DESTINAZIONE [Art. 7.5]
        selected_drive = self.target_drive.get().upper()
        source_drive = self.source_drive.get().upper()
        
        if selected_drive == source_drive:
            self.LabelStatus.configure(text="⚠️ ERRORE: DESTINAZIONE NON VALIDA", text_color="red")
            self.LabelNext.configure(text="Non puoi salvare il backup sullo stesso disco dei dati!", text_color="red")
            return

        # Se il controllo passa, procedi normalmente
        for child in self.RightTree.get_children():
            self.RightTree.item(child, text=self.RightTree.item(child, "text").replace("➤ ", ""))
        
        self.RightTree.item(item_id, text="➤ " + self.RightTree.item(item_id, "text"))
        path = self.get_full_path(self.RightTree, item_id, self.target_drive.get())
        self.TargetRootPath.set(path)
        self.LabelDest.configure(text=f"DEST: {os.path.basename(path)}")
        self.save_config()
        self.after(2000, self.minimize_to_tray)

    def on_minimize(self, event):
        """Devia la minimizzazione alla Tray solo se pronto [Art. 6.2]."""
        if self.state() == 'iconic':
            self.minimize_to_tray()


    def get_checked_paths(self):
        """Ritorna la lista dei percorsi completi attualmente selezionati [Art. 5.1]."""
        checked_paths = []
        def collect(node_id):
            if self.LeftTree.item(node_id, "text").startswith(self.CHECKED_CHAR):
                checked_paths.append(self.get_full_path(self.LeftTree, node_id, self.source_drive.get()))
            for child in self.LeftTree.get_children(node_id):
                collect(child)
        
        for root in self.LeftTree.get_children(""):
            collect(root)
        return checked_paths

    def generate_manifest(self):
        """Analizza l'albero di sinistra e genera la lista dei percorsi da copiare [Art. 5]."""
        jobs = []
        source_root = self.source_drive.get()
        target_sub_root = self.TargetRootPath.get()
        
        if not source_root or not target_sub_root:
            return jobs

        def scan_tree(node_id):
            txt = self.LeftTree.item(node_id, "text")
            full_src = self.get_full_path(self.LeftTree, node_id, source_root)
            # Costruisce il percorso di destinazione specchiato
            rel_path = os.path.relpath(full_src, source_root)
            full_dst = os.path.join(target_sub_root, rel_path)

            if txt.startswith(self.CHECKED_CHAR):
                # Se la cartella è spuntata, copia tutto il contenuto
                jobs.append({'src': full_src, 'dst': full_dst, 'mode': 'FULL'})
            elif txt.startswith(self.PARTIAL_CHAR):
                # Se è parziale, crea solo la cartella e scendi nei figli
                jobs.append({'src': full_src, 'dst': full_dst, 'mode': 'DIR_ONLY'})
                for child in self.LeftTree.get_children(node_id):
                    scan_tree(child)

        for root_node in self.LeftTree.get_children(""):
            scan_tree(root_node)
        return jobs


    def find_destination_on_any_drive(self, relative_path):
        """Cerca la cartella di backup ovunque tranne che sulla sorgente [Art. 7.4]."""
        source_unit = self.source_drive.get().upper()
        drives = [d.device for d in psutil.disk_partitions() if 'fixed' in d.opts or 'removable' in d.opts]
        
        for drive in drives:
            # ESCLUSIONE FISICA: Se è lo stesso disco, ignora
            if drive.upper() == source_unit:
                continue
                
            potential_path = os.path.join(drive, relative_path)
            if os.path.exists(potential_path):
                return potential_path
        return None
    
    def restore_checks(self, paths_to_check):
        """Ripristina le spunte espandendo automaticamente l'albero [Art. 9.1]."""
        if not paths_to_check: return
        
        source_drive = self.source_drive.get()
        # Ordina per lunghezza: processa prima le cartelle in alto per efficienza
        paths_to_check.sort(key=len)

        for full_path in paths_to_check:
            # Ignora percorsi che non appartengono al drive attuale
            if not full_path.lower().startswith(source_drive.lower()): continue
            
            rel_path = os.path.relpath(full_path, source_drive)
            if rel_path == ".": continue
            
            parts = rel_path.split(os.sep)
            current_node = "" # Parte dalla radice
            path_exists = True
            
            for part in parts:
                found = False
                # Cerca il segmento del percorso tra i figli del nodo corrente
                for child in self.LeftTree.get_children(current_node):
                    txt = self.LeftTree.item(child, "text")
                    # Pulisce il nome dai simboli di stato (☑, ☐, ◩) per il confronto
                    clean_name = txt[2:] if txt.startswith((self.CHECKED_CHAR, self.UNCHECKED_CHAR, self.PARTIAL_CHAR)) else txt
                    
                    if clean_name == part:
                        current_node = child
                        found = True
                        break
                
                if found:
                    # Se il nodo è "dummy" (non ancora caricato), forza l'espansione
                    children = self.LeftTree.get_children(current_node)
                    if children and self.LeftTree.item(children[0], "text") == "dummy":
                        self.on_tree_expand(None, self.LeftTree, source_drive, target_id=current_node)
                else:
                    path_exists = False
                    break
            
            # Se il percorso è stato trovato interamente, applica la spunta
            if path_exists and current_node:
                self.set_node_state(current_node, "CHECKED")
                self.update_parent_states(current_node)


    def reset_destination(self):
        """Annulla la scelta del percorso di destinazione e aggiorna lo stato [Art. 7.6]."""
        # 1. Svuota le variabili
        self.TargetRootPath.set("")
        
        # 2. Rimuove il simbolo grafico dal Treeview
        for child in self.RightTree.get_children():
            self.RightTree.item(child, text=self.RightTree.item(child, "text").replace("➤ ", ""))
            
        # 3. Aggiorna la UI
        self.LabelDest.configure(text="DEST: ---")
        self.LabelStatus.configure(text="ATTESA CONFIGURAZIONE", text_color="orange")
        self.LabelNext.configure(text="Seleziona una nuova destinazione", text_color="white")
        
        # 4. Rende persistente il reset nel JSON
        self.save_config()





if __name__ == "__main__":
    app = SyncApp()
    app.mainloop()