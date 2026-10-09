import os
import json
import re
import datetime
import subprocess
import logging
import argparse
from Bio import Entrez, SeqIO
import boto3

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

DATA_DIR = "/app/data"
os.makedirs(DATA_DIR, exist_ok=True)

DEFAULT_STATES = [
    "Iowa", "Minnesota", "North Carolina", "Illinois", "Indiana",
    "Nebraska", "Missouri", "Ohio", "Kansas", "Oklahoma"
]
MONTH_NAMES = ["", "January", "February", "March", "April", "May", "June",
               "July", "August", "September", "October", "November", "December"]


def parse_collection_date(date_str):
    """
    Parse a GenBank-style collection date into Auspice-friendly components.
    Returns: (iso_date, year, month_name, num_date)
      - iso_date:  'YYYY-MM-DD' | 'YYYY-MM' | 'YYYY' | '?'   (used for Auspice time filter)
      - year:      'YYYY' | 'Unknown'                        (categorical color)
      - month_name:'January'..'December' | 'Unknown'         (categorical color)
      - num_date:  decimal year (float) | None               (continuous color)
    """
    if not date_str or str(date_str).strip() in ("", "Unknown", "?", "NA", "N/A"):
        return "?", "Unknown", "Unknown", None

    s = str(date_str).strip().replace("/", "-").replace("_", "-").replace(".", "-")
    parts = s.split("-")

    year = parts[0] if parts and parts[0].isdigit() and len(parts[0]) == 4 else None
    month = None
    day = None
    if year:
        if len(parts) >= 2 and parts[1].isdigit() and 1 <= int(parts[1]) <= 12:
            month = int(parts[1])
        if month and len(parts) >= 3 and parts[2].isdigit() and 1 <= int(parts[2]) <= 31:
            day = int(parts[2])

    if not year:
        return "?", "Unknown", "Unknown", None

    y = int(year)
    if month and day:
        iso = f"{y:04d}-{month:02d}-{day:02d}"
        try:
            d = datetime.date(y, month, day)
        except ValueError:
            d = datetime.date(y, month, 1)
        ys = datetime.date(y, 1, 1)
        ye = datetime.date(y + 1, 1, 1)
        num_date = y + (d - ys).days / (ye - ys).days
    elif month:
        iso = f"{y:04d}-{month:02d}"
        num_date = y + (month - 0.5) / 12.0
    else:
        iso = f"{y:04d}"
        num_date = y + 0.5

    month_name = MONTH_NAMES[month] if month else "Unknown"
    return iso, str(y), month_name, num_date


def upload_to_cloudflare_r2(file_path, object_name):
    """Pushes a file (JSON, manifest, etc.) to Cloudflare R2 bucket."""
    if not file_path or not os.path.exists(file_path):
        return

    endpoint_url = os.environ.get("R2_ENDPOINT_URL")
    access_key = os.environ.get("R2_ACCESS_KEY_ID")
    secret_key = os.environ.get("R2_SECRET_ACCESS_KEY")
    bucket_name = os.environ.get("R2_BUCKET_NAME", "swine-flu-tracker-data")

    if not all([endpoint_url, access_key, secret_key]):
        logging.warning(f"Skipping R2 upload for {object_name}: Environment variables missing.")
        return

    logging.info(f"Uploading {file_path} to Cloudflare R2 as '{object_name}'...")
    s3 = boto3.client(
        's3',
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name='auto'
    )

    try:
        s3.upload_file(
            file_path, 
            bucket_name, 
            object_name, 
            ExtraArgs={'ContentType': 'application/json'}
        )
        logging.info(f"Successfully uploaded {object_name} to R2.")
    except Exception as e:
        logging.error(f"Upload failed for {object_name}: {e}")

def fetch_ncbi_sequences(output_fasta, state, days_back=180):
    """Fetches real Swine HA sequences from NCBI Nucleotide over a rolling window."""
    logging.info(f"Fetching US Swine HA sequences for {state} (Last {days_back} days)...")
    Entrez.email = "faith508@iastate.edu"
    
    query = (
        f'influenza A virus[organism] AND swine[host] '
        f'AND USA[Location] AND "{state}"[All Fields] '
        f'AND hemagglutinin[protein] AND ("last {days_back} days"[PDAT])'
    )
    
    try:
        search_handle = Entrez.esearch(db="nuccore", term=query, retmax=2000)
        search_results = Entrez.read(search_handle)
        search_handle.close()
        
        id_list = search_results["IdList"]
        logging.info(f"NCBI returned {len(id_list)} potential matches for {state}. Filtering...")
        
        if not id_list:
            open(output_fasta, "w").close()
            return False
            
        records = []
        batch_size = 200 
        
        for start in range(0, len(id_list), batch_size):
            batch_ids = id_list[start:start + batch_size]
            fetch_handle = Entrez.efetch(db="nuccore", id=batch_ids, rettype="gb", retmode="text")
            
            for seq_record in SeqIO.parse(fetch_handle, "genbank"):
                accession = seq_record.id
                strain, date, location = "Unknown", "Unknown", "Unknown"
                
                for feature in seq_record.features:
                    if feature.type == "source":
                        qualifiers = feature.qualifiers
                        strain = qualifiers.get("strain", [strain])[0]
                        date = qualifiers.get("collection_date", [date])[0]
                        location = qualifiers.get("country", [location])[0]
                
                # Loose matching to avoid dropping valid state isolates
                state_lower = state.lower()
                if state_lower not in strain.lower() and state_lower not in location.lower():
                    continue
                
                clean_id = f"{accession}|{strain}|{date}"
                seq_record.id = clean_id
                seq_record.description = ""
                records.append(seq_record)
                
            fetch_handle.close()
            
        SeqIO.write(records, output_fasta, "fasta")
        logging.info(f"Filter applied. Saved {len(records)} verified {state} sequences.")
        return len(records) > 0
        
    except Exception as e:
        logging.error(f"Error fetching NCBI data for {state}: {e}")
        return False

def run_octoflu(fasta_file):
    """Run OctoFLU on the downloaded state FASTA"""
    if not os.path.exists(fasta_file) or os.stat(fasta_file).st_size == 0:
        return False

    logging.info(f"Running OctoFLU clade classification on {fasta_file}...")
    try:
        # Pass full path to fasta_file so octoFLU can locate it regardless of working directory
        abs_fasta = os.path.abspath(fasta_file)
        subprocess.run(["bash", "./octoFLU.sh", abs_fasta], cwd="/opt/octoFLU", check=True)
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"OctoFLU failed: {e}")
        return False
def norm(x):
    # keep only the accession-like first token, strip separators
    return re.split(r"[|\s_]", x.strip())[0]

def write_auspice_config(path, state):
    cfg = {
        "title": f"US Swine Influenza HA — {state}",
        "maintainers": [
            {"name": "Swine Flu Tracker", "url": "https://github.com/propenster/swine-flu-tracker"}
        ],
        "colorings": [
            {"key": "clade",   "title": "Clade",            "type": "categorical"},
            {"key": "lineage", "title": "Lineage",          "type": "categorical"},
            {"key": "year",    "title": "Collection Year",  "type": "categorical"},
            {"key": "month",   "title": "Collection Month", "type": "categorical"}
        ],
        "filters": ["clade", "lineage", "year", "month"],
        "display_defaults": {"color_by": "clade"}
    }
    with open(path, "w") as f:
        json.dump(cfg, f, indent=2)
    return path


def generate_auspice_jsons(state):
    """Prunes OctoFLU global references, builds clean trees, and exports Auspice JSONs."""
    safe_state = state.replace(' ', '_')
    fasta_path = os.path.join(DATA_DIR, f"swine_HA_{safe_state}.fasta")
    
    if not os.path.exists(fasta_path) or os.stat(fasta_path).st_size == 0:
        logging.warning(f"No FASTA file found at {fasta_path}")
        return []

    # OctoFLU outputs relative to /opt/octoFLU or /app/data depending on execution
    octoflu_dir = f"/opt/octoFLU/swine_HA_{safe_state}.fasta_output"
    if not os.path.exists(octoflu_dir):
        octoflu_dir = os.path.join(DATA_DIR, f"swine_HA_{safe_state}.fasta_output")

    metadata_file = os.path.join(DATA_DIR, f"metadata_{safe_state}.tsv")

    # Map state sequence headers
    seen_ids = set()
    accession_map = {}
    
    for record in SeqIO.parse(fasta_path, "fasta"):
        seen_ids.add(record.id)
        acc = record.id.split("|")[0]
        accession_map[acc] = record.id

        # Parse OctoFLU clade calls from potential output locations
    clade_mapping = {}          # normalized_id -> clade
    clade_mapping_raw = {}      # raw seq_id    -> clade (fallback)
    lineage_mapping = {}        # normalized_id -> lineage
    logging.info(f"octoflu_dir = {octoflu_dir}")
    logging.info(f"octoflu_dir exists = {os.path.exists(octoflu_dir)}")
    possible_reports = [
        f"/opt/octoFLU/swine_HA_{safe_state}.fasta_Final_Output.txt",
        os.path.join(DATA_DIR, f"swine_HA_{safe_state}.fasta_Final_Output.txt"),
        os.path.join(octoflu_dir, "Final_Output.txt"),
    ]

    octoflu_report = None
    for rep in possible_reports:
        if os.path.exists(rep):
            octoflu_report = rep
            break

    if octoflu_report and os.path.exists(octoflu_report):
        logging.info(f"Parsing clade calls from {octoflu_report}")

        with open(octoflu_report, "r") as f:
            for line in f:
                line = line.rstrip("\n")
                if not line.strip():
                    continue
                parts = line.split("\t")
                if len(parts) < 4:
                    continue

                seq_id = parts[0].strip()
                clade = parts[3].strip() or "Unknown"

                clade_mapping[norm(seq_id)] = clade       # <-- norm() here
                clade_mapping_raw[seq_id] = clade
                lineage_mapping[norm(seq_id)] = parts[2].strip() if len(parts) > 2 else "Unknown"

        logging.info(f"Parsed {len(clade_mapping)} clade calls from report")

    # Write Metadata TSV (enriched with date-derived columns for Auspice)
    date_min = None
    date_max = None
    unmatched_clades = 0
    with open(metadata_file, "w") as f:
        f.write("name\tstrain\tdate\tyear\tmonth\tstate\tclade\tlineage\n")
        for rec_id in seen_ids:
            parts = rec_id.split("|")
            if len(parts) != 3:
                continue

            strain, raw_date = parts[1], parts[2]
            iso_date, year, month_name, _ = parse_collection_date(raw_date)

            # Try normalized lookup first, then raw, then accession-only
            seq_clade = (
                clade_mapping.get(norm(rec_id))
                or clade_mapping_raw.get(rec_id)
                or clade_mapping.get(norm(parts[0]))
                or "Unclassified"
            )
            seq_lineage = lineage_mapping.get(norm(rec_id), "Unknown")
            if seq_clade == "Unclassified":
                unmatched_clades += 1

            if iso_date != "?":
                if date_min is None or iso_date < date_min:
                    date_min = iso_date
                if date_max is None or iso_date > date_max:
                    date_max = iso_date

            f.write(
                f"{rec_id}\t{strain}\t{iso_date}\t{year}\t{month_name}\t"
                f"{state}\t{seq_clade}\t{seq_lineage}\n"
            )

    logging.info(
        f"[{state}] date range: {date_min or 'n/a'} → {date_max or 'n/a'} | "
        f"clades: {len(seen_ids) - unmatched_clades}/{len(seen_ids)} matched"
    )
    
    auspice_cfg = write_auspice_config(
    os.path.join(DATA_DIR, f"auspice_config_{safe_state}.json"),
    state
)
    generated_subtypes = []

    for subtype in ["H1", "H3"]:
        octoflu_aln = os.path.join(octoflu_dir, f"{subtype}_aln.fa")
        
        clean_aln = os.path.join(DATA_DIR, f"{safe_state}_{subtype}_clean.fa")
        clean_tree = os.path.join(DATA_DIR, f"{safe_state}_{subtype}_clean.tre")
        
        refined_tree = os.path.join(DATA_DIR, f"refined_{safe_state}_{subtype}.tre")
        branch_lengths = os.path.join(DATA_DIR, f"branch_lengths_{safe_state}_{subtype}.json")
        out_json = os.path.join(DATA_DIR, f"auspice_{safe_state}_{subtype}.json")
        
        if os.path.exists(octoflu_aln):
            try:
                seen_norm = {norm(s) for s in seen_ids}
                accession_map_norm = {norm(k): v for k, v in accession_map.items()}
                valid_records = []
                for record in SeqIO.parse(octoflu_aln, "fasta"):
                    key = norm(record.id)
                    record_acc = record.id.split("|")[0]
                    if key in seen_norm or key in accession_map_norm:
                        record.id = accession_map_norm.get(key, record.id)
                        record.description = ""
                        valid_records.append(record)
                        
                logging.info(f"{subtype}: kept {len(valid_records)} / {sum(1 for _ in SeqIO.parse(octoflu_aln,'fasta'))} records for {state}")
                        
                if len(valid_records) < 1:
                    logging.warning(f"No {subtype} matching sequences found for {state}.")
                    continue
                    
                SeqIO.write(valid_records, clean_aln, "fasta")
                logging.info(f"Building clean {subtype} tree for {state} with {len(valid_records)} sequences...")
                
                if len(valid_records) < 3:
                    with open(clean_tree, "w") as out_f:
                        taxa = [f"'{r.id}':0.001" for r in valid_records]
                        out_f.write(f"({','.join(taxa)});")
                else:
                    with open(clean_tree, "w") as out_f, open(clean_aln, "r") as in_f:
                        subprocess.run(["FastTree", "-nt"], stdin=in_f, stdout=out_f, check=True)

                # Augur Refine & Export
                subprocess.run([
                    "augur", "refine",
                    "--tree", clean_tree,
                    "--alignment", clean_aln,
                    "--metadata", metadata_file,
                    "--metadata-id-columns", "name",
                    "--output-tree", refined_tree,
                    "--output-node-data", branch_lengths
                ], check=True)
                subprocess.run([
                    "augur", "export", "v2",
                    "--tree", refined_tree,
                    "--metadata", metadata_file,
                    "--metadata-id-columns", "name",
                    "--node-data", branch_lengths,
                    "--auspice-config", auspice_cfg,   # <-- add this
                    "--output", out_json
                ], check=True)
                                
                # subprocess.run([
                #     "augur", "export", "v2",
                #     "--tree", refined_tree,
                #     "--metadata", metadata_file,
                #     "--metadata-id-columns", "name",
                #     "--node-data", branch_lengths,
                #     "--output", out_json
                # ], check=True)
                
                logging.info(f"Successfully generated {out_json}")
                
                object_name = f"auspice_{safe_state}_{subtype}.json"
                upload_to_cloudflare_r2(out_json, object_name)
                
                generated_subtypes.append(subtype)
            except subprocess.CalledProcessError as e:
                logging.error(f"Augur failed for {state} {subtype}: {e}")

    return generated_subtypes

def process_state(state, days):
    
    safe_state = state.replace(' ', '_')
    fasta_path = os.path.join(DATA_DIR, f"swine_HA_{safe_state}.fasta")
    
    has_data = fetch_ncbi_sequences(fasta_path, state=state, days_back=days)
    if has_data:
        success = run_octoflu(fasta_path)
        if success:
            subtypes = generate_auspice_jsons(state)
            return {"state": state, "subtypes": subtypes}
    return None

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Multi-State Swine Flu Pipeline")
    parser.add_argument("--states", nargs="+", default=DEFAULT_STATES, help="List of US states")
    parser.add_argument("--days", type=int, default=2160,  help="Days back to search")
    # parser.add_argument("--start-date", default="2009-01-01", help="YYYY-MM-DD earliest collection date")
    args = parser.parse_args()
    
    manifest = []

    for state in args.states:
        res = process_state(state, args.days)
        if res and res["subtypes"]:
            manifest.append(res)

    manifest_path = os.path.join(DATA_DIR, "manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    upload_to_cloudflare_r2(manifest_path, "manifest.json")

    logging.info(f"Pipeline complete! Uploaded data for {len(manifest)} states to Cloudflare R2.")