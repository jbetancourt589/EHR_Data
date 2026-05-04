import json
import re  # importing regex
from datetime import datetime

#for the ref ranges and flags
import gzip

def build_ref_range_lookup(gz_file, max_records=5000):
    lookup = {}
    with gzip.open(gz_file, "rt", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i >= max_records:
                break
            record = json.loads(line)
            for event in record.get("events", []):
                if event.get("type") == "LAB":
                    text = event.get("text", "")
                    ref_range = event.get("ref_range")
                    derived_flag = event.get("derived_flag")
                    match = re.match(r"LAB: (.+?) =", text)
                    if match and ref_range:
                        lab_name = match.group(1).strip()
                        if lab_name not in lookup:
                            lookup[lab_name] = {
                                "ref_range": ref_range,
                                "derived_flag": derived_flag
                            }
    return lookup

ref_lookup = build_ref_range_lookup("Compressed Raw Data/train.jsonl.gz")


file_name = "Compressed Raw Data/test.jsonl.gz"


#Parse Med Events: Drug, Dose, Route, Order Type (Order vs Stop)

# take out redundant colons and other stuff
def normalize_drug_name(name):
    return name.strip().lstrip(":").strip().title()

def parse_med(text):

    if "MED STOP" in text:
        category = "MED_STOP"
    else:
        category = "MED_ORDER"

    #The replace is to remove the "MED STOP" or "MED ORDER" from the text, so we can extract the drug, dose, and route information more easily.
    clean_text = text.replace("MED STOP", "").replace("MED ORDER", "").strip()

    # Fix: split on "(" to avoid absorbing dose into drug name, then normalize
    drug = normalize_drug_name(clean_text.split("(")[0])

    #set dose and route to None for now, as they are not always present in the text.
    dose = None
    route = None

    #takes the dose and route by splitting what comes after dose= and what comes after route=,
    if "dose=" in clean_text:
        dose = clean_text.split("dose=")[1].split(",")[0].strip().rstrip(")")
    if "route=" in clean_text:
        route = clean_text.split("route=")[1].split(",")[0].strip().rstrip(")")

    structured = {
        "drug": drug,
        "dose": dose,
        "route": route
    }

    #returns the category (MED_STOP or MED_ORDER) and the structured information (drug, dose, route)
    return category, structured


#     ---Parse Lab Events: Lab Name, Value, Units, Flag (Normal vs Abnormal)---

def parse_lab(text):
    match = re.search(r"LAB: (.+?) = ([\d\.]+) (.+?) \[flag=(.+?)\]", text)

    if match:
        lab_name = match.group(1)
        ref_info = ref_lookup.get(lab_name, {})
        structured = {
            "lab_name": lab_name,
            "value": float(match.group(2)),
            "units": match.group(3),
            "flag": match.group(4),
            "ref_range": ref_info.get("ref_range"),
            "derived_flag": ref_info.get("derived_flag")
        }
    else:
        structured = None

    return "LAB", structured

def parse_time(ts):
    # "YYYY-MM-DD HH:MM:SS"
    if ts is None:
        return None
    try:
        return datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        try:
            return datetime.strptime(ts.split(".")[0], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None

#    ---Parse Transfer Events: Direction (IN vs OUT), Care Unit---

def parse_transfer(text):

    transfer_direction = None
    if text.startswith("TRANSFER IN"):
        transfer_direction = "IN"
    elif text.startswith("TRANSFER OUT"):
        transfer_direction = "OUT"

    careunit = None
    if "careunit=" in text:
        careunit = text.split("careunit=")[1].strip()

    return {
        "direction": transfer_direction,
        "careunit": careunit
    }

def parse_timestamp(timestamp_string):

    if timestamp_string is None:
        return None

    try:
        return datetime.strptime(timestamp_string, "%Y-%m-%d %H:%M:%S")

    except ValueError:
        try:
            return datetime.strptime(timestamp_string.split(".")[0], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None




def clean_patient (raw): # Cleans the data of 1 patient. Takes in raw record as parameter
    context = raw.get("context", {})

    clean_output = {
        "patient_info": {
            "subject_id": raw.get("subject_id"),
            "hadm_id": raw.get("hadm_id"),

            # demographics at the top
            "age": context.get("anchor_age"),
            "gender": context.get("gender"),
            "race": context.get("race"),
            "insurance": context.get("insurance"),
            "marital_status": context.get("marital_status"),
            "language": context.get("language"),
        },
        "timeline": []
    }

    # Pin admission event — always first
    admission_event = {
        "time": context.get("admittime"),
        "category": "ADMISSION",
        "data": {
            "admission_type": context.get("admission_type"),
            "admission_location": context.get("admission_location"),
        },
        "notes": None
    }

    # Pin discharge event — always last
    discharge_event = {
        "time": context.get("dischtime"),
        "category": "DISCHARGE",
        "data": {
            "discharge_location": context.get("discharge_location"),
        },
        "notes": None
    }

    seen = set()
    middle_events = []

    for event in raw.get("events", []):
        key = (event.get("time"), event.get("type"), event.get("text"))
        if key in seen:
            continue
        seen.add(key)

        event_type = event.get("type")
        event_text = event.get("text")

        entry = {
            "time": event.get("time"),
            "category": event_type,
            "data": None,
            "notes": None
        }

        if event_type == "MED":
            cat, structured = parse_med(event_text)
            entry["category"] = cat
            entry["data"] = structured

        elif event_type == "LAB":
            cat, structured = parse_lab(event_text)
            entry["category"] = cat
            entry["data"] = structured
            if structured is None:
                entry["notes"] = event_text

        elif event_type == "TRANSFER":
            entry["data"] = parse_transfer(event_text)

        elif event_type == "NOTE":
            entry["notes"] = event_text

        else:
            entry["notes"] = event_text

        middle_events.append(entry)

    # Sort all middle events chronologically
    middle_events.sort(key=lambda e: (parse_time(e["time"]) is None, parse_time(e["time"]) or datetime.max))

    grouped_events = {}

    for event in middle_events:
        time = event["time"]

        if time not in grouped_events:
            grouped_events[time] = {
                "time": time,
                "events": {}
            }

        category = event["category"]

        if category not in grouped_events[time]["events"]:
            grouped_events[time]["events"][category] = []

        # Remove redundant notes
        if category == "NOTE":
            note_text = event["notes"]
            existing_notes = grouped_events[time]["events"][category]

            if note_text not in existing_notes:
                existing_notes.append(note_text)

        else:
            grouped_events[time]["events"][category].append(event["data"])


    def clean_note(text):

        if text is None:
            return None

        # normalize newline markers from source text
        text = re.sub(r"(?:\\n|/n)+", "\n", text, flags=re.IGNORECASE)
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        # remove duplicated report if it appears twice
        half = len(text) // 2
        if text[:half] == text[half:]:
            text = text[:half]

        # ensure common uppercase section headers start on a new line
        text = re.sub(
            r"\s*(NOTES|INDICATION|COMPARISON|TECHNIQUE|FINDINGS|IMPRESSION):",
            r"\n\1:",
            text,
            flags=re.IGNORECASE
        )

        # ensure common discharge-note style section headers start on a new line
        text = re.sub(
            r"\s*(Chief Complaint|Major Surgical or Invasive Procedure|History of Present Illness|Past Medical History|Social History|Family History|Physical Exam|Pertinent Results|Brief Hospital Course|Medications on Admission|Discharge Medications|Discharge Disposition|Facility|Discharge Diagnosis|Discharge Condition|Discharge Instructions|Followup Instructions):",
            r"\n\1:",
            text,
            flags=re.IGNORECASE
        )

        # collapse excessive blank lines
        text = re.sub(r"\n{3,}", "\n\n", text)

        return text.strip()


    # Clean notes and remove discharge note from timeline — attach it to discharge event instead
    for grouped_event in grouped_events.values():
        note_list = grouped_event["events"].get("NOTE")
        if not note_list:
            continue

        cleaned_notes = []
        for note in note_list:
            cleaned_note = clean_note(note)
            if cleaned_note and cleaned_note not in cleaned_notes:
                cleaned_notes.append(cleaned_note)

        grouped_event["events"]["NOTE"] = cleaned_notes

    # Pull discharge note out of timeline and attach to discharge event
    for time_key in list(grouped_events.keys()):
        note_list = grouped_events[time_key]["events"].get("NOTE", [])
        discharge_notes = [n for n in note_list if n and "[DISCHARGE]" in n[:20]]
        if discharge_notes:
            discharge_event["notes"] = discharge_notes[0]
            remaining = [n for n in note_list if not ("[DISCHARGE]" in n[:20])]
            if remaining:
                grouped_events[time_key]["events"]["NOTE"] = remaining
            else:
                del grouped_events[time_key]["events"]["NOTE"]
            break

    # Build final timeline: admission first, sorted middle events, discharge last
    timeline = []
    timeline.append(admission_event)

    for time in sorted(grouped_events.keys(), key=lambda t: parse_time(t) or datetime.max):
        entry = grouped_events[time]
        # Drop any timestamp buckets where all event lists are empty
        non_empty = {k: v for k, v in entry["events"].items() if v}
        if non_empty:
            entry["events"] = non_empty
            timeline.append(entry)

    timeline.append(discharge_event)
    clean_output["timeline"] = timeline

    return clean_output

#runs the function for every patient.
with open("output.jsonl", "w", encoding="utf-8") as out:
    with gzip.open(file_name, "rt", encoding="utf-8") as f:
        for line in f:
            raw = json.loads(line)

            clean_output = clean_patient(raw)

            out.write(json.dumps(clean_output) + "\n")

print("Done. Output written to output.jsonl")