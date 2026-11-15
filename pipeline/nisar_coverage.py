"""Phase 5 coverage check: NISAR L2 GCOV acquisitions over active construction sites.

Usage:
    python pipeline/nisar_coverage.py [--sites data/nisar_coverage_sites.csv]
        [--start 2026-06-01] [--end 2026-11-15] [--out data/nisar_gcov_coverage.csv]
        [--no-pixels] [--workers 8]

Steps
1. For each site in --sites, search NASA CMR (public, no credentials) for granules of the three
   NISAR GCOV collections that contain the site point and start between --start and --end:
     NISAR_L2_GCOV_V1             C3622241360-ASF
     NISAR_L2_GCOV_PROVISIONAL_V1 C2854338529-ASF
     NISAR_L2_GCOV_BETA_V1        C3622214170-ASF
   Track, frame, pass direction, polarizations per frequency, range bandwidth, full/partial frame
   and product version are copied from each granule's CMR AdditionalAttributes.
2. Unless --no-pixels, open each granule's HDF5 on ASF with HTTP Range requests (the environment
   attaches the Earthdata token; no file is written to disk, roughly 10-25 MB is read per granule)
   and read a 51 x 51 pixel window of frequency A centred on the site:
     valid_frac_HH / valid_frac_HV   share of pixels with finite, positive backscatter
     median_HH_db / median_HV_db     10*log10 of the median linear gamma0 (RTC) in the window
     mask_values                     value:count of the subswath mask (0 = partially focused,
                                     255 = outside the swath, 1..n = valid subswath)
     anomaly_px                      pixels whose inputDataExceptionMask has a low-byte anomaly
                                     bit set (e.g. 2 = qFSP-H1 sample slip); the high bits
                                     256/512 only mean "HH/HV fully focused" and are not anomalies
     is_urgent, diagnostic_flag, has_input_exception  from science/LSAR/identification
3. usable = freq A has HH and HV, valid_frac_HH and valid_frac_HV >= 0.9, anomaly_px == 0,
   diagnostic flag 0. usable_reason says why not. Duplicate products of one acquisition
   (a 40 MHz partial frame plus a 20 MHz full frame, or a reprocessed _002) are kept and the
   secondary copy names the primary in duplicate_of (see mark_duplicates).

A 401/403 from ASF stops the run (the token may have expired). Nothing is invented: blank cells
mean the value was not available.
"""
import argparse
import concurrent.futures as cf
import csv
import io
import os
import sys

import numpy as np
import requests

CMR = "https://cmr.earthdata.nasa.gov/search/granules.umm_json"
CMR_GRANULE = "https://cmr.earthdata.nasa.gov/search/concepts/{}.umm_json"
COLLECTIONS = {
    "C3622241360-ASF": "NISAR_L2_GCOV_V1",
    "C2854338529-ASF": "NISAR_L2_GCOV_PROVISIONAL_V1",
    "C3622214170-ASF": "NISAR_L2_GCOV_BETA_V1",
}
HALF = 25  # 51 x 51 pixels: 510 m at 10 m posting (40 MHz), 1020 m at 20 m posting (20 MHz)
MIN_VALID = 0.9
CA = os.environ.get("REQUESTS_CA_BUNDLE") or ("/root/.ccr/ca-bundle.crt" if os.path.exists("/root/.ccr/ca-bundle.crt") else True)


class TokenError(RuntimeError):
    pass


class RangeFile(io.RawIOBase):
    """Read-only file object over HTTP Range requests with a block cache (for h5py)."""

    def __init__(self, url, block=4 * 2**20):
        self.s = requests.Session()
        self.s.verify = CA
        r = self.s.get(url, headers={"Range": "bytes=0-0"}, allow_redirects=True, timeout=60)
        if r.status_code in (401, 403):
            raise TokenError(f"HTTP {r.status_code} from ASF: the Earthdata token may have expired")
        r.raise_for_status()
        self.url = r.url  # signed redirect target; never printed
        self.size = int(r.headers["Content-Range"].split("/")[1])
        self.pos, self.block, self.cache = 0, block, {}

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, off, whence=0):
        self.pos = {0: off, 1: self.pos + off, 2: self.size + off}[whence]
        return self.pos

    def _blk(self, i):
        if i not in self.cache:
            a = i * self.block
            b = min(self.size, a + self.block) - 1
            r = self.s.get(self.url, headers={"Range": f"bytes={a}-{b}"}, timeout=120)
            r.raise_for_status()
            self.cache[i] = r.content
        return self.cache[i]

    def readinto(self, buf):
        n = min(len(buf), self.size - self.pos)
        if n <= 0:
            return 0
        out, p = bytearray(), self.pos
        while len(out) < n:
            i = p // self.block
            d = self._blk(i)
            chunk = d[p - i * self.block: p - i * self.block + n - len(out)]
            out += chunk
            p += len(chunk)
        buf[:n] = out
        self.pos += n
        return n


def cmr_search(lat, lon, start, end):
    rows = []
    for cid, short in COLLECTIONS.items():
        r = requests.get(CMR, params={"concept_id": cid, "point": f"{lon},{lat}",
                                      "temporal": f"{start}T00:00:00Z,{end}T23:59:59Z",
                                      "page_size": 2000, "sort_key": "start_date"}, timeout=60)
        r.raise_for_status()
        for it in r.json()["items"]:
            u, meta = it["umm"], it["meta"]
            a = {x["Name"]: x["Values"] for x in u["AdditionalAttributes"]}
            g = lambda k: "+".join(a.get(k, [""]))
            h5 = [x["URL"] for x in u["RelatedUrls"] if x.get("Type") == "GET DATA" and x["URL"].endswith(".h5")]
            png = [x["URL"] for x in u["RelatedUrls"] if x["URL"].startswith("https") and x["URL"].endswith("_LATLON.png")]
            t = u["TemporalExtent"]["RangeDateTime"]["BeginningDateTime"]
            rows.append({
                "acq_start_utc": t[:19] + "Z", "acq_date": t[:10], "collection": short,
                "granule_ur": u["GranuleUR"], "cycle": u["GranuleUR"].split("_")[4],
                "track": g("TRACK_NUMBER"), "frame": g("FRAME_NUMBER"),
                "direction": g("ASCENDING_DESCENDING"), "stack_id": g("STACK_ID"),
                "freq_a_pols": g("FREQUENCY_A_POLARIZATION"), "freq_b_pols": g("FREQUENCY_B_POLARIZATION"),
                "range_bandwidth_mhz": g("RANGE_BANDWIDTH_CONCAT"), "full_frame": g("FULL_FRAME"),
                "product_version": g("PRODUCT_VERSION"), "orbit_type": g("ORBIT_TYPE"),
                "cmr_concept_id": meta["concept-id"],
                "source": CMR_GRANULE.format(meta["concept-id"]),
                "download_url": h5[0] if h5 else "", "browse_url": png[0] if png else "",
            })
    return rows


def probe(row, lat, lon):
    import h5py
    from pyproj import Transformer
    if not row["download_url"]:
        return {"usable_reason": "no HDF5 link in CMR"}
    f = RangeFile(row["download_url"])
    with h5py.File(f, "r") as h:
        idn = h["science/LSAR/identification"]
        g = h["science/LSAR/GCOV/grids/frequencyA"]
        val = lambda d: (lambda v: v.decode() if isinstance(v, bytes) else (v.item() if hasattr(v, "item") else v))(d[()])
        epsg = int(g["projection"][()])
        x, y = Transformer.from_crs(4326, epsg, always_xy=True).transform(lon, lat)
        xs, ys = g["xCoordinates"][:], g["yCoordinates"][:]
        j = int(round((x - xs[0]) / (xs[1] - xs[0])))
        i = int(round((y - ys[0]) / (ys[1] - ys[0])))
        out = {"file_gb": round(f.size / 1e9, 2), "epsg": epsg,
               "pixel_spacing_m": float(g["xCoordinateSpacing"][()]),
               "is_urgent": val(idn["isUrgentObservation"]), "diagnostic_flag": val(idn["diagnosticModeFlag"]),
               "has_input_exception": val(idn["hasInputDataException"])}
        if not (0 <= i < len(ys) and 0 <= j < len(xs)):
            out["usable_reason"] = "site outside the product grid"
            return out
        sl = (slice(max(i - HALF, 0), i + HALF + 1), slice(max(j - HALF, 0), j + HALF + 1))
        for term, key in (("HHHH", "HH"), ("HVHV", "HV")):
            if term in g:
                arr = g[term][sl]
                ok = np.isfinite(arr) & (arr > 0)
                out[f"valid_frac_{key}"] = round(float(ok.mean()), 3)
                out[f"median_{key}_db"] = round(float(10 * np.log10(np.median(arr[ok]))), 2) if ok.any() else ""
            else:
                out[f"valid_frac_{key}"] = 0.0
                out[f"median_{key}_db"] = ""
        m = g["mask"][sl]
        out["mask_values"] = " ".join(f"{v}:{c}" for v, c in zip(*np.unique(m, return_counts=True)))
        ex = g["inputDataExceptionMask"][sl] if "inputDataExceptionMask" in g else None
        out["anomaly_px"] = int(((ex & 0xFF) != 0).sum()) if ex is not None else ""
    return out


def judge(r):
    if r.get("usable_reason"):
        return False, r["usable_reason"]
    why = []
    if not ("HH" in r["freq_a_pols"] and "HV" in r["freq_a_pols"]):
        why.append(f"freq A has {r['freq_a_pols'] or 'no'} pols only")
    for k in ("HH", "HV"):
        v = r.get(f"valid_frac_{k}")
        if v == "" or v is None or float(v) < MIN_VALID:
            why.append(f"{k} valid {v} < {MIN_VALID} in window")
    if r.get("anomaly_px") not in (0, "0"):
        why.append(f"{r.get('anomaly_px')} anomaly px")
    if str(r.get("diagnostic_flag")) not in ("0", ""):
        why.append("diagnostic mode")
    return (not why), "; ".join(why)


def mark_duplicates(rows):
    """Same site + track + frame + start minute = one acquisition. Primary: usable, then the
    track's usual range bandwidth (keeps a stack at one pixel spacing), then full frame, then the
    highest counter (_002 over _001)."""
    from collections import Counter, defaultdict
    groups = defaultdict(list)
    for r in rows:
        groups[(r["site_id"], r["track"], r["frame"], r["acq_start_utc"][:15])].append(r)
    bw_mode = Counter((r["site_id"], r["track"], r["range_bandwidth_mhz"]) for r in rows)
    for g in groups.values():
        g.sort(key=lambda r: (r.get("usable") is not True,
                              -bw_mode[(r["site_id"], r["track"], r["range_bandwidth_mhz"])],
                              r["full_frame"] != "TRUE", -int(r["granule_ur"][-3:])))
        for r in g[1:]:
            r["duplicate_of"] = g[0]["granule_ur"]
    for r in rows:
        r.setdefault("duplicate_of", "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sites", default="data/nisar_coverage_sites.csv")
    ap.add_argument("--start", default="2026-06-01")
    ap.add_argument("--end", default="2026-11-15")
    ap.add_argument("--out", default="data/nisar_gcov_coverage.csv")
    ap.add_argument("--no-pixels", action="store_true")
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()

    sites = list(csv.DictReader(open(a.sites)))
    rows = []
    for s in sites:
        lat, lon = float(s["lat"]), float(s["lon"])
        found = cmr_search(lat, lon, a.start, a.end)
        for r in found:
            r.update(site_id=s["site_id"], site_lat=lat, site_lon=lon)
        by = {c: sum(r["collection"] == c for r in found) for c in COLLECTIONS.values()}
        print(f"{s['site_id']}: {len(found)} granules {by}", flush=True)
        rows += found

    if not a.no_pixels:
        def work(r):
            try:
                return probe(r, r["site_lat"], r["site_lon"])
            except TokenError:
                raise
            except Exception as e:  # network or file error: report, do not guess
                return {"usable_reason": f"read failed: {type(e).__name__}"}
        with cf.ThreadPoolExecutor(a.workers) as ex:
            for r, res in zip(rows, ex.map(work, rows)):
                r.update(res)
    for r in rows:
        if a.no_pixels:
            r["usable"], r["usable_reason"] = "", "pixels not checked"
        else:
            r["usable"], r["usable_reason"] = judge(r)
    mark_duplicates(rows)

    cols = ["site_id", "acq_date", "acq_start_utc", "collection", "cycle", "track", "frame", "direction",
            "stack_id", "freq_a_pols", "freq_b_pols", "range_bandwidth_mhz", "pixel_spacing_m", "full_frame",
            "product_version", "orbit_type", "is_urgent", "diagnostic_flag", "has_input_exception",
            "valid_frac_HH", "valid_frac_HV", "median_HH_db", "median_HV_db", "mask_values", "anomaly_px",
            "usable", "usable_reason", "duplicate_of", "granule_ur", "cmr_concept_id", "file_gb",
            "source", "download_url", "browse_url"]
    rows.sort(key=lambda r: (r["site_id"], r["acq_start_utc"], r["granule_ur"]))
    with open(a.out, "w", newline="") as fo:
        w = csv.DictWriter(fo, cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    print(f"wrote {a.out}: {len(rows)} rows")
    for s in sites:
        sr = [r for r in rows if r["site_id"] == s["site_id"] and not r["duplicate_of"]]
        ok = [r for r in sr if r["usable"] is True]
        tracks = sorted({f"{r['track']}{r['direction'][0]}" for r in ok})
        print(f"  {s['site_id']}: {len(sr)} acquisitions, {len(ok)} usable, tracks {tracks}, "
              f"first {min((r['acq_date'] for r in ok), default='-')}, last {max((r['acq_date'] for r in ok), default='-')}")


if __name__ == "__main__":
    sys.exit(main())
