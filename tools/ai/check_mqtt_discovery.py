#!/usr/bin/env python3
"""Check the Home Assistant discovery configs a PLC actually publishes.

Two questions, and the second is the one that is easy to get wrong.

**Is each config well formed?** Valid JSON, not cut short, carrying the keys Home
Assistant needs, with a `uniq_id` that matches its own topic and is unique across
the broker. A config that fails any of these is dropped by Home Assistant
silently: the entity simply never appears, and the PLC logs the discovery as
added.

**Was it published by THIS download, or is it left over from months ago?** MQTT
carries no publish timestamp, and a retained config looks identical whether it
was written a second or a year ago - which is exactly how a PLC came to publish
no discovery config at all for weeks while the broker looked fully populated. The
distinguishing fact is the **retain flag**: subscribe live, and every message the
broker replays from its store arrives with retain=1, while a genuine publish
arrives with retain=0. So "recent enough to match this download" is answerable,
and this is how.

    # 1. record what Home Assistant currently knows - the expectation
    py tools/ai/check_mqtt_discovery.py --snapshot .ai/mqtt/expect.json

    # 2. start watching, and download while it runs (another shell, or
    #    background this one). It fails if anything expected stays silent.
    py tools/ai/check_mqtt_discovery.py --watch 240 --expect .ai/mqtt/expect.json \
        --device Wago_PFC200_G1_Lab

    # structure only, against whatever is retained now - no PLC needed
    py tools/ai/check_mqtt_discovery.py

Exits non-zero on any finding.

LIMITS worth knowing. A config payload is assumed to be one line, which is what
STRUCT_TO_JSON produces. The watch cannot tell "the PLC chose not to republish"
from "the PLC never started" - so run it around a download you know completed,
and read the `published` count as coverage, not as proof of liveness.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

DEFAULT_BROKER = "10.101.1.11"
DEFAULT_PORT = 1883
DEFAULT_PREFIX = "homeassistant"
# The PLC logs a composer failure here rather than publishing a bad config.
DEFAULT_LOG_TOPIC = "Devices/PLC/+/diagnostic/Log"

COMPOSER_ERRORS = ("composed truncated json", "failed json root strip",
                   "had empty MqttJSON")

# A discovery config has to give Home Assistant something to talk to. Any one of
# these is enough; a config with none of them describes an entity that can
# neither report nor be commanded.
TOPIC_KEYS = ("stat_t", "state_topic", "cmd_t", "command_topic",
              "json_attr_t", "json_attributes_topic", "pos_t", "position_topic",
              "bri_stat_t", "curr_temp_t", "mode_stat_t")


def mosquitto_sub():
    """The client, wherever it is. The Windows installer skips PATH."""
    for cand in ("mosquitto_sub", "mosquitto_sub.exe"):
        for path in os.environ.get("PATH", "").split(os.pathsep):
            full = os.path.join(path, cand)
            if os.path.isfile(full):
                return full
    for path in (r"C:\Program Files\mosquitto\mosquitto_sub.exe",
                 r"C:\Program Files (x86)\mosquitto\mosquitto_sub.exe",
                 "/usr/bin/mosquitto_sub"):
        if os.path.isfile(path):
            return path
    sys.exit("mosquitto_sub not found. Install it with:\n"
             "    winget install --id EclipseFoundation.Mosquitto --scope machine\n"
             "The installer does not add itself to PATH; this also looks in\n"
             r"C:\Program Files\mosquitto.")


def collect(topics, seconds, broker, port, user, password, retained_only):
    """Run mosquitto_sub and return (retain_flag, topic, payload) per message.

    -W makes the client print "Timed out" and exit non-zero; that is its normal
    end here, so the return code is not an error signal.
    """
    # %r is the retain flag. %R is the RESPONSE TOPIC, which is empty here - use
    # it by mistake and every message parses as a live publish, so a watch run
    # against a powered-down PLC reports full coverage and passes. That happened;
    # hence the strict flag check below rather than a tolerant split.
    cmd = [mosquitto_sub(), "-h", broker, "-p", str(port), "-W", str(seconds),
           "-F", "%r %t %p"]
    for t in topics:
        cmd += ["-t", t]
    if retained_only:
        cmd.append("--retained-only")
    if user:
        cmd += ["-u", user]
    if password:
        cmd += ["-P", password]

    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out = proc.stdout.decode("utf-8", "replace")
    messages = []
    for line in out.split("\n"):
        line = line.strip("\r").rstrip("\n")
        if not line.strip():
            continue
        parts = line.split(" ", 2)
        if len(parts) < 3:
            continue
        retain, topic, payload = parts
        if retain not in ("0", "1"):
            sys.exit("cannot read the retain flag from %r - without it a live "
                     "publish cannot be told from the retained backlog, and "
                     "this check would pass on a PLC that published nothing."
                     % line[:80])
        messages.append((retain == "1", topic, payload))
    return messages


def validate(topic, payload, prefix):
    """Every structural complaint about one config. Empty list means good."""
    bad = []
    if payload == "":
        return ["empty payload (a cleared config, or nothing composed)"]

    # Checked before parsing, because it is the specific shape a truncated
    # compose takes and it names the fault precisely rather than as a syntax
    # error somewhere in the middle.
    if not payload.rstrip().endswith("}"):
        bad.append("does not end in '}' - truncated at %d characters" % len(payload))

    try:
        cfg = json.loads(payload)
    except ValueError as exc:
        bad.append("not valid JSON: %s" % exc)
        return bad
    if not isinstance(cfg, dict):
        bad.append("top level is %s, not an object" % type(cfg).__name__)
        return bad

    uniq = cfg.get("uniq_id") or cfg.get("unique_id")
    if not uniq:
        bad.append("no uniq_id - Home Assistant cannot key the entity")

    # homeassistant/<platform>/<node_id>/config, and the node id is the uniq_id.
    # A mismatch means a republish under a new id orphans the old topic instead
    # of replacing it, which shows up as a duplicate entity.
    parts = topic.split("/")
    if len(parts) >= 4 and parts[0] == prefix and parts[-1] == "config":
        node = parts[-2]
        if uniq and node != uniq:
            bad.append("topic node %r does not match uniq_id %r" % (node, uniq))

    dev = cfg.get("dev") or cfg.get("device")
    if not isinstance(dev, dict):
        bad.append("no dev object - the entity will not attach to a device")
    elif not dev.get("ids") and not dev.get("identifiers"):
        bad.append("dev has no ids")

    if not any(k in cfg for k in TOPIC_KEYS):
        bad.append("no state or command topic - nothing to talk to")

    avty = cfg.get("avty") or cfg.get("availability")
    if avty is not None:
        if not isinstance(avty, list) or not avty:
            bad.append("avty is not a non-empty list")
        else:
            for i, entry in enumerate(avty):
                if not isinstance(entry, dict) or not entry.get("topic"):
                    bad.append("avty[%d] has no topic" % i)
        mode = cfg.get("avty_mode")
        if mode is not None and mode not in ("all", "any", "latest"):
            bad.append("avty_mode %r is not all/any/latest" % mode)

    # exp_aft 0 is Home Assistant's "no expiry", which most entities here use
    # deliberately. Only a negative value is malformed. A small POSITIVE one is
    # not malformed either - it is merely almost certainly wrong - so it is
    # reported separately by suspect_expiry() rather than failed here.
    exp = cfg.get("exp_aft", cfg.get("expire_after"))
    if exp is not None:
        if not isinstance(exp, int) or isinstance(exp, bool):
            bad.append("exp_aft %r is not an integer" % exp)
        elif exp < 0:
            bad.append("exp_aft is %d" % exp)

    return bad


# Below this many seconds, an expiry is shorter than any heartbeat this project
# publishes on, so Home Assistant would show the entity as unavailable for most
# of every interval. exp_aft=3 against a one-minute heartbeat is what a stale
# config from a T#1S era looks like, and it is worth naming even though it is
# structurally legal.
SUSPECT_EXPIRY = 30


def suspect_expiry(payload):
    try:
        cfg = json.loads(payload)
    except ValueError:
        return None
    if not isinstance(cfg, dict):
        return None
    exp = cfg.get("exp_aft", cfg.get("expire_after"))
    if isinstance(exp, int) and not isinstance(exp, bool) and 0 < exp < SUSPECT_EXPIRY:
        return exp
    return None


def configs_from(messages, prefix, device):
    """topic -> (payload, was_retained), for discovery configs only."""
    out = {}
    for retained, topic, payload in messages:
        if not (topic.startswith(prefix + "/") and topic.endswith("/config")):
            continue
        if device and device not in topic:
            continue
        # A later live publish supersedes the retained copy delivered at subscribe.
        if topic in out and out[topic][1] is False:
            continue
        out[topic] = (payload, retained)
    return out


def report_structure(configs, prefix):
    """Validate every config; returns the number of bad ones."""
    findings, seen = 0, {}
    for topic in sorted(configs):
        payload = configs[topic][0]
        bad = validate(topic, payload, prefix)
        if bad:
            findings += 1
            print("  FAIL %s" % topic)
            for b in bad:
                print("       %s" % b)
        else:
            try:
                uniq = (json.loads(payload).get("uniq_id")
                        or json.loads(payload).get("unique_id"))
            except ValueError:
                uniq = None
            if uniq:
                seen.setdefault(uniq, []).append(topic)

    for uniq, topics in sorted(seen.items()):
        if len(topics) > 1:
            findings += 1
            print("  FAIL uniq_id %r is used by %d topics:" % (uniq, len(topics)))
            for t in topics:
                print("       %s" % t)

    suspects = [(t, suspect_expiry(configs[t][0])) for t in sorted(configs)]
    suspects = [(t, e) for t, e in suspects if e is not None]
    if suspects:
        print("  NOTE %d config(s) expire faster than %ds, so Home Assistant will"
              % (len(suspects), SUSPECT_EXPIRY))
        print("       show them unavailable between publishes. Legal, rarely "
              "intended, and")
        print("       what a config left over from a faster heartbeat looks like:")
        for t, exp in suspects:
            print("       exp_aft=%-5d %s" % (exp, t))
    return findings


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--broker", default=DEFAULT_BROKER)
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--prefix", default=DEFAULT_PREFIX,
                    help="discovery prefix (default %s)" % DEFAULT_PREFIX)
    ap.add_argument("--device", default="",
                    help="only configs whose topic contains this, e.g. a PLC name")
    ap.add_argument("--seconds", type=int, default=5,
                    help="collect window for the retained snapshot")
    ap.add_argument("--snapshot", metavar="FILE",
                    help="write the retained configs as an expectation file")
    ap.add_argument("--watch", type=int, metavar="SECONDS",
                    help="watch live publishes for this long, then report")
    ap.add_argument("--expect", metavar="FILE",
                    help="with --watch: fail if a config in this file is not republished")
    ap.add_argument("--log-topic", default=DEFAULT_LOG_TOPIC)
    ap.add_argument("--user")
    ap.add_argument("--password")
    args = ap.parse_args()

    topics = ["%s/#" % args.prefix]
    findings = 0

    if args.watch:
        topics.append(args.log_topic)
        print("watching %s:%d for %ds - download now if you have not already"
              % (args.broker, args.port, args.watch))
        messages = collect(topics, args.watch, args.broker, args.port,
                           args.user, args.password, retained_only=False)

        # Composer failures never reach a config topic, so they are invisible
        # unless the log is read. Only live lines count: the retained one is
        # whatever was logged last, possibly long ago.
        for retained, topic, payload in messages:
            if retained or topic == "%s/#" % args.prefix:
                continue
            if any(e in payload for e in COMPOSER_ERRORS):
                findings += 1
                print("  FAIL composer error logged: %s" % payload.strip())

        configs = configs_from(messages, args.prefix, args.device)
        published = {t: v for t, v in configs.items() if v[1] is False}

        print("\nstructure of everything seen (%d config(s)):" % len(configs))
        findings += report_structure(configs, args.prefix)

        print("\npublished during the window: %d of %d config(s) seen"
              % (len(published), len(configs)))

        if args.expect:
            if not os.path.exists(args.expect):
                sys.exit("expectation file not found: %s" % args.expect)
            with open(args.expect, encoding="utf-8") as fh:
                expected = json.load(fh)["configs"]
            missing = sorted(t for t in expected if t not in published)
            if missing:
                findings += len(missing)
                print("\n  FAIL %d expected config(s) were NOT republished:"
                      % len(missing))
                for t in missing:
                    print("       %s" % t)
                print("\n  A retained config that is never rewritten is the "
                      "failure this test exists for:")
                print("  Home Assistant keeps showing an old config while the "
                      "PLC believes it announced itself.")
            else:
                print("  all %d expected config(s) were republished" % len(expected))
    else:
        messages = collect(topics, args.seconds, args.broker, args.port,
                           args.user, args.password, retained_only=True)
        configs = configs_from(messages, args.prefix, args.device)
        print("retained discovery configs: %d" % len(configs))
        findings += report_structure(configs, args.prefix)

        if args.snapshot:
            payload = {"broker": "%s:%d" % (args.broker, args.port),
                       "prefix": args.prefix,
                       "device": args.device,
                       "configs": sorted(configs)}
            directory = os.path.dirname(args.snapshot)
            if directory and not os.path.isdir(directory):
                os.makedirs(directory)
            with open(args.snapshot, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2)
            print("wrote %s with %d config topic(s)" % (args.snapshot, len(configs)))

    print("")
    if findings:
        print("FAILED: %d finding(s)" % findings)
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
