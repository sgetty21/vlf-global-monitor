#!/usr/bin/env python3
"""Retrieve and process CRAAM Open VLF type-A recordings for one UTC date.

Read-only against CRAAM. Downloads are temporary; only JSON measurements and
an inventory are emitted. Each source object is handled independently.
"""
from __future__ import annotations
import argparse, gzip, hashlib, json, re, sys, tempfile, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
from scipy.io import loadmat

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from archive_format import classify_archive_file, eligible_for_current_engine
from vlf_json_exporter import load_amplitude_array, normalize_and_filter, build_export

BUCKET = "craam-files-bucket"
REGION = "sa-east-1"
HOST = f"https://{BUCKET}.s3.{REGION}.amazonaws.com/"
NS = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}

def list_objects(prefix: str) -> list[dict]:
    found, token = [], None
    while True:
        q = {"list-type":"2", "prefix":prefix}
        if token: q["continuation-token"] = token
        req = urllib.request.Request(HOST+"?"+urllib.parse.urlencode(q),
          headers={"User-Agent":"vlf-global-monitor/1.0"})
        with urllib.request.urlopen(req, timeout=60) as res:
            root = ET.fromstring(res.read())
        for el in root.findall("s3:Contents", NS):
            found.append({
              "key":el.findtext("s3:Key",default="",namespaces=NS),
              "size_bytes":int(el.findtext("s3:Size",default="0",namespaces=NS)),
              "last_modified":el.findtext("s3:LastModified",default="",namespaces=NS),
              "etag":el.findtext("s3:ETag",default="",namespaces=NS).strip('"')
            })
        if root.findtext("s3:IsTruncated",default="false",namespaces=NS).lower()!="true":
            return found
        token=root.findtext("s3:NextContinuationToken",default="",namespaces=NS)
        if not token: raise RuntimeError("S3 pagination truncated without a continuation token")

def load_metadata(path: Path) -> dict:
    mat=loadmat(str(path), squeeze_me=True, struct_as_record=False)
    # Keep only small scalar/string metadata. Never serialize the signal array.
    out={}
    for k,v in mat.items():
        if k.startswith("__") or k=="data": continue
        a=np.asarray(v)
        if a.size<=16 and (a.dtype.kind in "biufUS"):
            val=a.tolist()
            out[k]=val
    return out

def verify_mat_metadata(metadata: dict, filename: str) -> float:
    """Require internal MAT evidence for 1 Hz amplitude-only input."""
    normalized={str(k).lower():v for k,v in metadata.items()}
    rate_keys=("sample_rate_hz","sampling_rate_hz","sampling_rate","sample_rate","samplingrate","fs")
    rate=None
    for key in rate_keys:
        if key in normalized:
            try: rate=float(np.asarray(normalized[key]).reshape(-1)[0])
            except (TypeError,ValueError,IndexError): continue
            break
    if rate is None or not np.isfinite(rate):
        raise ValueError(f"{filename}: MAT metadata does not expose a verifiable sample rate; refusing to assume 1 Hz")
    if abs(rate-1.0)>1e-9:
        raise ValueError(f"{filename}: MAT sample rate is {rate} Hz; frozen engine requires exactly 1 Hz")
    for key in ("is_amp","is_amplitude","amplitude"):
        if key in normalized and str(normalized[key]).lower() not in ("1","true","yes"):
            raise ValueError(f"{filename}: MAT metadata {key} does not confirm amplitude data")
    for key in ("is_broadband","broadband"):
        if key in normalized and str(normalized[key]).lower() in ("1","true","yes"):
            raise ValueError(f"{filename}: MAT metadata identifies broadband data")
    return rate

def process(obj: dict, out_dir: Path, observation_date: str) -> dict:
    key=obj["key"]; name=Path(key).name
    if not eligible_for_current_engine(name,"narrowband"):
        raise ValueError(f"Object is not eligible type-A narrowband amplitude: {name}")
    if obj["size_bytes"]<=0 or obj["size_bytes"]>50_000_000:
        raise ValueError(f"Object size outside safe processing bounds: {obj['size_bytes']} bytes")
    url=HOST+urllib.parse.quote(key,safe="/")
    req=urllib.request.Request(url,headers={"User-Agent":"vlf-global-monitor/1.0"})
    with urllib.request.urlopen(req,timeout=120) as res:
        payload=res.read(50_000_001)
        response_etag=res.headers.get("ETag","").strip('"')
        response_length=res.headers.get("Content-Length")
    if len(payload)!=obj["size_bytes"] or len(payload)>50_000_000:
        raise RuntimeError(f"Size mismatch for {key}: listed={obj['size_bytes']} downloaded={len(payload)}")
    if response_length and int(response_length)!=len(payload):
        raise RuntimeError(f"HTTP Content-Length mismatch for {key}")
    if response_etag and obj["etag"] and response_etag!=obj["etag"]:
        raise RuntimeError(f"ETag changed between listing and download for {key}")
    with tempfile.TemporaryDirectory(prefix="vlf-openvlf-") as td:
        mat_path=Path(td)/name
        mat_path.write_bytes(payload)
        signal=load_amplitude_array(mat_path)
        metadata=load_metadata(mat_path)
        sample_rate=verify_mat_metadata(metadata,name)
        filtered=normalize_and_filter(signal)
        result=build_export(signal,filtered,name)
    # Type A is the archive's 1 Hz narrowband-amplitude product. Reject files
    # too short for even one complete hourly measurement; do not pad.
    if not result["hourly"]:
        raise ValueError(f"{name}: fewer than 3600 usable samples; no complete hour")
    variant=classify_archive_file(name)
    result["source"]={
      "provider":"CRAAM Open VLF public S3 bucket","bucket":BUCKET,"region":REGION,
      "object_key":key,"object_etag":obj["etag"],"object_size_bytes":obj["size_bytes"],
      "last_modified_utc":obj["last_modified"],"downloaded_sha256":hashlib.sha256(payload).hexdigest(),
      "observation_date_utc":observation_date,"archive_station_folder":key.split("/")[4] if len(key.split("/"))>4 else None,
      "transmitter":re.search(r"([A-Z]{3})_\d{3}A\.mat$",name,re.I).group(1).upper() if re.search(r"([A-Z]{3})_\d{3}A\.mat$",name,re.I) else None,
      "archive_type":variant,"sample_rate_hz":sample_rate,
      "mat_metadata":metadata
    }
    result["interpretation_policy"]="No A/B/C/D state is assigned automatically. Human annotations are separate."
    stamp=re.match(r"^[A-Z]{2}(\\d{2})(\\d{2})(\\d{2})(\\d{2})(\\d{2})(\\d{2})",name,re.I)
    if stamp:
        yy,mm,dd,hh,mi,ss=map(int,stamp.groups())
        start=datetime(2000+yy,mm,dd,hh,mi,ss,tzinfo=timezone.utc)
        result["source"]["recording_start_utc"]=start.isoformat().replace("+00:00","Z")
    waveform={
      "sample_rate_hz":1.0,"sample_count":int(signal.size),
      "raw_amplitude":[float(x) for x in signal],
      "filtered_normalized":[float(x) for x in filtered]
    }
    out_dir.mkdir(parents=True,exist_ok=True)
    target=out_dir/(name+".json")
    wave_target=out_dir/(name+".waveform.json.gz")
    target.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    with gzip.open(wave_target,"wt",encoding="utf-8",compresslevel=6) as handle:
        json.dump(waveform,handle,separators=(",",":"),allow_nan=False)
    result["waveform_file"]=wave_target.name
    return {"file":name,"record":target.name,"waveform":wave_target.name,"object_key":key,"size_bytes":obj["size_bytes"],
      "etag":obj["etag"],"samples":result["summary"]["samples"],
      "complete_hours":result["summary"]["complete_hours"],
      "A":result["summary"]["A"],"T":result["summary"]["T"],"tau":result["summary"]["tau"]}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--date",required=True,help="UTC date YYYY-MM-DD")
    p.add_argument("--station-folder",default="",help="Optional CRAAM station folder code, e.g. FE")
    p.add_argument("--transmitter",default="",help="Optional transmitter callsign, e.g. NAA")
    p.add_argument("--max-files",type=int,default=50)
    p.add_argument("--output-dir",type=Path,default=Path("historical-output"))
    a=p.parse_args()
    try: d=date.fromisoformat(a.date)
    except ValueError: p.error("--date must be YYYY-MM-DD")
    if d.isoformat()!=a.date: p.error("--date must be canonical YYYY-MM-DD")
    if not 1<=a.max_files<=20: p.error("--max-files must be between 1 and 20")
    prefix=f"{d:%Y/%m/%d}/narrowband/"
    objects=list_objects(prefix)
    all_count=len(objects)
    eligible=[]
    for o in objects:
        name=Path(o["key"]).name
        try:
            if not eligible_for_current_engine(name,"narrowband"): continue
        except ValueError: continue
        parts=o["key"].split("/")
        station=parts[4] if len(parts)>4 else ""
        tx=re.search(r"([A-Z]{3})_\d{3}A\.mat$",name,re.I)
        tx=tx.group(1).upper() if tx else ""
        if a.station_folder and station.upper()!=a.station_folder.upper(): continue
        if a.transmitter and tx!=a.transmitter.upper(): continue
        eligible.append(o)
    eligible.sort(key=lambda x:x["key"])
    if len(eligible)>a.max_files:
        raise RuntimeError(f"{len(eligible)} eligible files found; exceeds --max-files={a.max_files}. Narrow station/transmitter filters or raise the cap.")
    a.output_dir.mkdir(parents=True,exist_ok=True)
    rows=[]; errors=[]
    for obj in eligible:
        try: rows.append(process(obj,a.output_dir,d.isoformat()))
        except Exception as exc: errors.append({"key":obj["key"],"error":str(exc)})
    inventory={
      "schema_version":1,"source":"CRAAM Open VLF public S3 bucket","bucket":BUCKET,"region":REGION,
      "date_utc":d.isoformat(),"prefix":prefix,"queried_at_utc":datetime.now(timezone.utc).isoformat(),
      "objects_discovered":all_count,"eligible_type_a_objects":len(eligible),
      "processed_count":len(rows),"failed_count":len(errors),
      "filters":{"station_folder":a.station_folder or None,"transmitter":a.transmitter.upper() or None},
      "records":rows,"errors":errors
    }
    (a.output_dir/"index.json").write_text(json.dumps(inventory,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps({"date":d.isoformat(),"discovered":all_count,"eligible":len(eligible),"processed":len(rows),"failed":len(errors)},indent=2))
    if not rows: raise SystemExit("No eligible type-A files were successfully processed for this date.")
    if errors: raise SystemExit(f"{len(errors)} file(s) failed; inspect index.json. Successful files are retained.")
if __name__=="__main__": main()
