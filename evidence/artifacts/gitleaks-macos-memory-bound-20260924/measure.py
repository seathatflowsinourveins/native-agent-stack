#!/usr/bin/env python3
"""Measure one command under /usr/bin/time -l with a footprint watchdog.

The watchdog samples the physical footprint (the value Jetsam uses) of every
process in the command's process group and SIGKILLs the group's members,
except /usr/bin/time itself, when the sum crosses --limit-gib or the run
exceeds --timeout. /usr/bin/time then still reports rusage for the child.
"""
import argparse, ctypes, json, os, re, signal, subprocess, sys, time

libproc = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
_V4 = ["ri_user_time", "ri_system_time", "ri_pkg_idle_wkups", "ri_interrupt_wkups", "ri_pageins",
       "ri_wired_size", "ri_resident_size", "ri_phys_footprint", "ri_proc_start_abstime",
       "ri_proc_exit_abstime", "ri_child_user_time", "ri_child_system_time",
       "ri_child_pkg_idle_wkups", "ri_child_interrupt_wkups", "ri_child_pageins",
       "ri_child_elapsed_abstime", "ri_diskio_bytesread", "ri_diskio_byteswritten",
       "ri_cpu_time_qos_default", "ri_cpu_time_qos_maintenance", "ri_cpu_time_qos_background",
       "ri_cpu_time_qos_utility", "ri_cpu_time_qos_legacy", "ri_cpu_time_qos_user_initiated",
       "ri_cpu_time_qos_user_interactive", "ri_billed_system_time", "ri_serviced_system_time",
       "ri_logical_writes", "ri_lifetime_max_phys_footprint", "ri_instructions", "ri_cycles",
       "ri_billed_energy", "ri_serviced_energy", "ri_interval_max_phys_footprint",
       "ri_runnable_time"]


class RUsageV4(ctypes.Structure):
    _fields_ = [("ri_uuid", ctypes.c_uint8 * 16)] + [(n, ctypes.c_uint64) for n in _V4]


def group_pids(pgid):
    buf = (ctypes.c_int * 4096)()
    n = libproc.proc_listpgrppids(pgid, buf, ctypes.sizeof(buf))
    return [buf[i] for i in range(max(n, 0)) if buf[i] > 0]


def usage(pid):
    ru = RUsageV4()
    if libproc.proc_pid_rusage(pid, 4, ctypes.byref(ru)) != 0:
        return None
    name = ctypes.create_string_buffer(256)
    libproc.proc_name(pid, name, 256)
    return name.value.decode(errors="replace"), ru.ri_phys_footprint, ru.ri_resident_size


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True)
    ap.add_argument("--limit-gib", type=float, default=6.0)
    ap.add_argument("--timeout", type=float, default=900.0)
    ap.add_argument("--interval", type=float, default=0.05)
    ap.add_argument("--out", required=True, help="JSON lines file to append to")
    ap.add_argument("--logdir", required=True)
    ap.add_argument("cmd", nargs=argparse.REMAINDER)
    a = ap.parse_args()
    cmd = a.cmd[1:] if a.cmd and a.cmd[0] == "--" else a.cmd
    limit = int(a.limit_gib * 2**30)
    os.makedirs(a.logdir, exist_ok=True)
    out_path = os.path.join(a.logdir, a.label + ".stdout")
    err_path = os.path.join(a.logdir, a.label + ".stderr")
    t0 = time.monotonic()
    with open(out_path, "wb") as so, open(err_path, "wb") as se:
        p = subprocess.Popen(["/usr/bin/time", "-l", *cmd], stdout=so, stderr=se,
                             stdin=subprocess.DEVNULL, start_new_session=True)
        peak_sum = peak_rss_sum = 0
        per_name = {}
        killed = None
        samples = 0
        while p.poll() is None:
            members = [x for x in group_pids(p.pid) if x != p.pid]
            tot = rss = 0
            for pid in members:
                u = usage(pid)
                if not u:
                    continue
                name, fp, rs = u
                tot += fp
                rss += rs
                per_name[name] = max(per_name.get(name, 0), fp)
            samples += 1
            peak_sum = max(peak_sum, tot)
            peak_rss_sum = max(peak_rss_sum, rss)
            elapsed = time.monotonic() - t0
            if killed is None and (tot > limit or elapsed > a.timeout):
                killed = "memory" if tot > limit else "timeout"
                for pid in members:
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
            time.sleep(a.interval)
        wall = time.monotonic() - t0
    err = open(err_path, "rb").read().decode(errors="replace")

    def stat(key):
        m = re.search(r"^\s*(\d+)\s+" + re.escape(key) + r"\s*$", err, re.M)
        return int(m.group(1)) if m else None

    real = re.search(r"^\s*([\d.]+) real\s+([\d.]+) user\s+([\d.]+) sys", err, re.M)
    child_status = None
    m = re.search(r"exit code:?\s*(\d+)", err)
    summary = [ln.strip() for ln in err.splitlines()
               if re.search(r"scanned ~|leaks found|no leaks found|commits scanned", ln)]
    rec = {
        "label": a.label, "cwd": os.getcwd(), "cmd": cmd,
        "time_exit": p.returncode,
        "max_rss_bytes": stat("maximum resident set size"),
        "peak_footprint_bytes": stat("peak memory footprint"),
        "group_peak_footprint_bytes": peak_sum,
        "group_peak_resident_bytes": peak_rss_sum,
        "per_process_peak_footprint_bytes": per_name,
        "real_s": float(real.group(1)) if real else round(wall, 2),
        "user_s": float(real.group(2)) if real else None,
        "sys_s": float(real.group(3)) if real else None,
        "killed": killed, "limit_bytes": limit, "samples": samples,
        "too_large_skips": err.count("skipping file: too large"),
        "summary": summary[-3:],
    }
    with open(a.out, "a") as fh:
        fh.write(json.dumps(rec) + "\n")
    gib = lambda b: None if b is None else round(b / 2**30, 3)
    print(json.dumps({"label": a.label, "time_exit": p.returncode, "killed": killed,
                      "max_rss_GiB": gib(rec["max_rss_bytes"]),
                      "peak_footprint_GiB": gib(rec["peak_footprint_bytes"]),
                      "group_peak_footprint_GiB": gib(peak_sum), "real_s": rec["real_s"],
                      "user_s": rec["user_s"], "summary": rec["summary"]}))


if __name__ == "__main__":
    main()
