#!/usr/bin/env python3
"""Publish one validated Patricia run into the durable data-branch dataset."""
import argparse, json
from pathlib import Path

def load(path):
    with path.open(encoding="utf-8") as f:
        return json.load(f)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",type=Path,required=True)
    p.add_argument("--report",type=Path,required=True)
    p.add_argument("--published-dir",type=Path,default=Path("published"))
    p.add_argument("--run-id",required=True)
    p.add_argument("--run-attempt",required=True)
    p.add_argument("--run-url",required=True)
    p.add_argument("--created-at",required=True)
    a=p.parse_args()
    source=load(a.input); report=load(a.report)
    if not report.get("object_identity_verified"):
        raise SystemExit("Refusing publication: CRAAM object identity was not verified.")
    summary=source.get("summary") or {}
    hourly=source.get("hourly")
    if not isinstance(hourly,list) or not hourly:
        raise SystemExit("Refusing publication: no hourly measurements.")
    for row in hourly:
        if not all(isinstance(row.get(k),(int,float)) for k in ("hour","A","T","tau")):
            raise SystemExit("Refusing publication: malformed hourly measurement.")
    key=f"{a.run_id}-{a.run_attempt}"
    out=a.published_dir/"runs"/f"{key}.json"
    out.parent.mkdir(parents=True,exist_ok=True)
    record={
      "schema_version":1,"run_id":int(a.run_id),"run_attempt":int(a.run_attempt),
      "published_at_utc":a.created_at,"workflow_url":a.run_url,
      "source":source.get("source",{}),"summary":summary,"hourly":hourly,
      "peak":source.get("peak"),"interpretation_policy":source.get("interpretation_policy"),
      "validation":report
    }
    if "state" in source:
        record["legacy_automated_state"]={"scope":"untrusted legacy exporter output; not a human annotation","value":source["state"]}
    if out.exists():
        existing=load(out)
        if existing!=record:
            raise SystemExit(f"Immutable publication conflict: {out} already exists with different content.")
    else:
        out.write_text(json.dumps(record,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    index_path=a.published_dir/"index.json"
    index=load(index_path) if index_path.exists() else {"schema_version":1,"runs":[]}
    runs=index.setdefault("runs",[])
    item={"run_id":int(a.run_id),"run_attempt":int(a.run_attempt),"record":f"runs/{key}.json","published_at_utc":a.created_at,"workflow_url":a.run_url}
    prior=[x for x in runs if x.get("run_id")==int(a.run_id) and x.get("run_attempt")==int(a.run_attempt)]
    if prior and prior[0]!=item:
        raise SystemExit("Index immutability conflict for this run attempt.")
    if not prior:
        runs.append(item)
    runs.sort(key=lambda x:(x["run_id"],x["run_attempt"]))
    index_path.parent.mkdir(parents=True,exist_ok=True)
    index_path.write_text(json.dumps(index,indent=2)+"\n",encoding="utf-8")
    print(f"Prepared immutable publication {out}")
if __name__=="__main__": main()
