import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import torch
from transformers import AutoModelForMaskedLM, AutoTokenizer
import numpy as np
from Bio import SeqIO

# Load PlantCaduceus Model & Tokenizer
model_path = "kuleshov-group/PlantCaduceus_l32"
device = "cuda:0" if torch.cuda.is_available() else "cpu"

tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
model = AutoModelForMaskedLM.from_pretrained(model_path, trust_remote_code=True).to(device)
model.eval()

# Parameters for Sliding Window Analysis
WINDOW_SIZE = 50
STEP_SIZE = 10
LIKELIHOOD_THRESHOLD = -1.5

# Function to Read Genome from FASTA File
def read_fasta(file_path):
    log_message("📂 Opening genome file...", "info")
    with open(file_path, "r") as file:
        for record in SeqIO.parse(file, "fasta"):
            return str(record.seq)  # Return first sequence as a string

# Compute Log-Likelihood of a Sequence
def compute_log_likelihood(sequence):
    encoding = tokenizer.encode_plus(sequence, return_tensors="pt", return_attention_mask=False, return_token_type_ids=False)
    input_ids = encoding["input_ids"].to(device)

    with torch.inference_mode():
        outputs = model(input_ids=input_ids)
    
    logits = outputs.logits
    log_probs = torch.nn.functional.log_softmax(logits, dim=-1)
    seq_probs = log_probs[0, torch.arange(len(input_ids[0])), input_ids[0]]
    
    return seq_probs.sum().item()

# Function to Log Messages in the GUI
def log_message(message, tag="info"):
    log_display.config(state=tk.NORMAL)
    log_display.insert(tk.END, f"{message}\n", tag)
    log_display.config(state=tk.DISABLED)
    log_display.see(tk.END)  # Auto-scroll to latest log

# Function to Process Genome and Detect Helitrons
def scan_genome(file_path):
    log_message("📂 Reading genome file...", "info")
    genome_sequence = read_fasta(file_path)

    scan_results = []
    log_message(f"🔍 Scanning genome with window size {WINDOW_SIZE} and step {STEP_SIZE}...", "info")

    for i in range(0, len(genome_sequence) - WINDOW_SIZE + 1, STEP_SIZE):
        sub_seq = genome_sequence[i:i + WINDOW_SIZE]
        log_likelihood = compute_log_likelihood(sub_seq)
        scan_results.append((i, i + WINDOW_SIZE, log_likelihood))

    # Normalize Scores
    log_likelihoods = np.array([x[2] for x in scan_results])
    normalized_scores = (log_likelihoods - log_likelihoods.mean()) / log_likelihoods.std()

    # Identify Helitron Regions
    highlighted_regions = [(start, end) for (start, end, score), norm_score in zip(scan_results, normalized_scores) if norm_score < LIKELIHOOD_THRESHOLD]

    log_message("✅ Scanning complete!", "success")
    return genome_sequence, highlighted_regions

# Function to Open File and Process Genome
def open_file():
    file_path = filedialog.askopenfilename(filetypes=[("FASTA files", "*.fasta"), ("All files", "*.*")])
    if file_path:
        log_message(f"📁 Selected file: {file_path}", "info")
        genome_sequence, highlighted_regions = scan_genome(file_path)
        display_sequence(genome_sequence, highlighted_regions)

# Function to Display Genome Sequence with Highlights
def display_sequence(genome_sequence, highlighted_regions):
    text_display.config(state=tk.NORMAL)
    text_display.delete("1.0", tk.END)

    text_display.insert(tk.END, "Scanned Genome:\n\n", "header")

    last_end = 0
    for start, end in highlighted_regions:
        text_display.insert(tk.END, genome_sequence[last_end:start], "normal")
        text_display.insert(tk.END, genome_sequence[start:end], "highlight")  # Highlighted region
        last_end = end

    text_display.insert(tk.END, genome_sequence[last_end:], "normal")
    text_display.config(state=tk.DISABLED)

    log_message(f"🔬 Found {len(highlighted_regions)} potential Helitron regions!", "warning" if highlighted_regions else "success")

# GUI Setup
root = tk.Tk()
root.title("Helitron Scanner")
root.geometry("900x600")

style = ttk.Style()
style.configure("TButton", font=("Arial", 12), padding=5)
style.configure("TLabel", font=("Arial", 14))
style.configure("TFrame", background="#f0f0f0")

frame = ttk.Frame(root, padding=20)
frame.pack(fill="both", expand=True)

label = ttk.Label(frame, text="Helitron Scanner", font=("Arial", 16, "bold"))
label.pack(pady=10)

open_button = ttk.Button(frame, text="Open FASTA File", command=open_file)
open_button.pack(pady=10)

# Genome Sequence Display (Scrollable)
text_frame = ttk.Frame(frame)
text_frame.pack(fill="both", expand=True, padx=10, pady=10)

text_display = tk.Text(text_frame, wrap="word", font=("Courier", 12), state=tk.DISABLED, bg="#F8F8F8")
text_display.pack(side="left", fill="both", expand=True)

scrollbar = ttk.Scrollbar(text_frame, command=text_display.yview)
scrollbar.pack(side="right", fill="y")
text_display.config(yscrollcommand=scrollbar.set)

# Define Text Tags for Styling
text_display.tag_configure("normal", foreground="black")
text_display.tag_configure("highlight", foreground="red", font=("Courier", 12, "bold"))
text_display.tag_configure("header", foreground="blue", font=("Arial", 14, "bold"))

# Log Panel
log_frame = ttk.Frame(frame)
log_frame.pack(fill="x", padx=10, pady=10)

log_display = tk.Text(log_frame, wrap="word", font=("Arial", 10), height=6, state=tk.DISABLED, bg="#222222", fg="white")
log_display.pack(side="left", fill="x", expand=True)

log_scrollbar = ttk.Scrollbar(log_frame, command=log_display.yview)
log_scrollbar.pack(side="right", fill="y")
log_display.config(yscrollcommand=log_scrollbar.set)

# Log Styling
log_display.tag_configure("info", foreground="lightblue")
log_display.tag_configure("success", foreground="lightgreen")
log_display.tag_configure("warning", foreground="yellow")
log_display.tag_configure("error", foreground="red")

# Run GUI
root.mainloop()
