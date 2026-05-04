# EHR Data Cleaning & Structuring for LLMs

## Overview

Raw clinical data is messy — it includes:
- Free-text physician notes
- Irregular timestamps
- Mixed event types (labs, meds, transfers, notes)
- Redundant and noisy entries

This pipeline:
- Parses raw JSONL EHR data
- Extracts structured medical information
- Cleans and formats physician notes
- Orders events chronologically
- Outputs a clean patient timeline

## Key Features

### Event Parsing

Extracts structured data from:

Medications
- Drug name
- Dose
- Route
- Order vs Stop

Labs
- Lab name
- Value
- Units
- Flag (e.g. abnormal)

Transfers
- Direction (IN / OUT)
- Care unit

Notes
- Cleaned and formatted

### Timeline Construction
- Converts events into a chronological timeline
- Groups events logically
- Ensures correct time ordering
- Handles missing or malformed timestamps

### Note Cleaning
- Removes noisy formatting (\n, duplicates, spacing issues)
- Preserves important structure (e.g. ___ redactions)
- Formats section headers cleanly

### Deduplication
- Removes duplicate events
- Prevents redundant clinical information

### Scalable Design
- Works with large .jsonl datasets
- Can process:
  - Single patient (debugging)
  - Full dataset (training pipeline)

## Project Structure
EHR_Data/
│
├── format.py # Main pipeline (parsing + structuring)
├── patient_checker.py # Debug tool (inspect 1 patient)
├── .gitignore # Ignores raw data + outputs


## How to Use

### 1. Input Data
Place raw MIMIC JSONL files locally (not tracked in Git):
Raw Data/

### 2. Run Formatter
python format.py

Output:

{
"patient_info": {...},
"timeline": [
{
"time": "...",
"category": "LAB",
"data": {...},
"notes": null
}]
}


### 3. Inspect a Single Patient
python patient_checker.py

Useful for:
- Debugging parsing logic
- Verifying formatting
- Checking chronological order



## Why This Matters

Clinical data is not model-ready. This project bridges that gap by:
- Converting unstructured EHR text into structured data
- Making patient timelines interpretable
- Preparing data for:
  - LLM training
  - Clinical AI models
  - Bioinformatics pipelines
