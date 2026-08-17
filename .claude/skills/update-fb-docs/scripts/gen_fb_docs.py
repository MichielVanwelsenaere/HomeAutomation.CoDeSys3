#!/usr/bin/env python3
"""Generate the mechanical parts of docs/FunctionBlocks/*.md from the PLCopen export.

Two regions per page are machine-owned:

    <!-- fb-badge:start -->      the MQTT Discovery badge, if the block has one
    <!-- fb-badge:end -->

    <!-- fb-interface:start -->  block diagram, inputs, outputs, methods
    <!-- fb-interface:end -->

Everything else on the page is hand-written and never touched.

Pin and parameter *descriptions* cannot come from the export - only 2% of pins
carry <documentation> - so the generated region doubles as their store. On each
run the structure is rebuilt from the export and existing descriptions are
carried across by name. A pin that gains a description keeps it forever; a pin
that disappears from the code takes its description with it; a new pin arrives
with a TODO marker so it is obvious what still needs writing.

Usage:
    python3 gen_fb_docs.py                  regenerate every page
    python3 gen_fb_docs.py --check          verify only, exit 1 if out of date
    python3 gen_fb_docs.py --new FB_NAME    scaffold a page for a new block
    python3 gen_fb_docs.py --print FB_NAME  print the region to stdout
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys
import xml.etree.ElementTree as ET

NS = {"p": "http://www.plcopen.org/xml/tc6_0200"}
REPO = pathlib.Path(__file__).resolve().parents[4]
EXPORT = REPO / "src" / "Exports" / "PLCopen.xml"
DOCS = REPO / "docs" / "FunctionBlocks"

BADGE = ("![MQTT Discovery]"
         "(https://img.shields.io/badge/MQTT%20Discovery-brightgreen)")
TODO = "_TODO: describe this._"

B_START, B_END = "<!-- fb-badge:start -->", "<!-- fb-badge:end -->"
I_START, I_END = "<!-- fb-interface:start -->", "<!-- fb-interface:end -->"

# FB_init's first two parameters are the CODESYS-implicit ones, never authored.
IMPLICIT_FB_INIT = {"bInitRetains", "bInCopyCode"}

# The export carries no access specifier, so "public API" vs "implementation
# detail" cannot be derived - it has to be curated. These are internal helpers
# that no doc page ever documented and that callers never invoke. A NEW method
# is deliberately NOT hidden by default: it shows up with a TODO so the author
# has to decide, and either describe it or add it here.
HIDDEN_METHODS = {
    "PubMqttMessage",        # ESERA: internal publish helper
    "ProcessTemperature",    # ESERA: per-sensor decoders, called from
    "ProcessHumidity",       #        ProcessDataArray
    "ProcessDewPoint",
    "ProcessAirQuality",
    "ProcessBrigthness",
    "ProcessOwdVoltage",
    "AddNode",               # DucoBox: internal node bookkeeping
    "InitNode",
    "Crc16",                 # RTU transport: framing internals, all PRIVATE.
    "Frame",                 #   Documenting them would describe the block's
    "Judge",                 #   guts as though they were its API.
    "SelectNext",            # Bus controller: arbitration internals, PRIVATE
    "FinishStep",
    # NOT hidden, deliberately: HasWork, BuildTransaction, OnStepResult and
    # OnTransactionDone are the RS485Device contract itself. This set is keyed
    # by bare name and so applies to every block, which is exactly why they
    # must stay out of it.
}

# Descriptions for methods and parameters that mean the same thing on every
# function block. A page-specific description always wins; this only fills the
# gaps, which keeps the wording consistent and means a NEW function block is
# already documented for all the standard plumbing the moment it is created.
# Key a parameter as "Method.param" to scope it, or "param" to apply anywhere.
GLOSSARY = {
    # --- methods -----------------------------------------------------------
    "InitMqtt": "Enables MQTT on the function block. Call once at startup.",
    "InitBaseMqtt": "Shared MQTT setup inherited from `FB_MQTT_BASE`.",
    "InitMqttDiscovery": "Publishes a Home Assistant MQTT discovery config so the "
                         "entity is created automatically. Call once at startup, "
                         "after `InitMqtt`.",
    "PublishReceived": "Callback invoked by the callback collector when a message "
                       "arrives on the subscribed topic. Not called directly.",
    "ConfigureFunctionBlock": "Overrides the default behaviour characteristics. "
                              "Only needed when the defaults do not suit.",
    "FB_init": "CODESYS constructor. These parameters are supplied in the "
               "instance declaration, not by calling a method, and are applied "
               "once at startup.",

    # --- the RS485Device contract ------------------------------------------
    # Identical on every RS485 device block, so it lives here rather than being
    # written out five times and drifting four ways.
    "HasWork": "Asked by the bus controller whether this device wants the bus, "
               "and how badly: `NONE`, `POLL`, or `COMMAND` for something a "
               "person or Home Assistant is waiting on. Must be free of side "
               "effects - it is called on every device, twice per cycle.",
    "BuildTransaction": "Called once after this device has been granted the "
                        "bus. Fills in every step it wants executed and returns "
                        "how many; they then run back to back with the bus "
                        "held. Returning 0 withdraws.",
    "OnStepResult": "Called once per executed step, in order, while the bus is "
                    "still held. A step skipped by an `AbortOnError` "
                    "predecessor is never reported.",
    "OnTransactionDone": "Called once, after the last `OnStepResult`, as the "
                         "bus is released. The one place to publish "
                         "`/availability` and clear a pending command.",
    "BuildTransaction.pSteps": "Scheduler-owned scratch to fill. Only valid for "
                               "the duration of the call.",
    "OnStepResult.StepIndex": "Which step of the transaction this answers, "
                              "indexed as `BuildTransaction` filled them.",
    "OnStepResult.Failed": "No reply, a bad frame, or a Modbus exception. "
                           "`pData` holds nothing meaningful.",
    "OnStepResult.pData": "Registers returned by a read step, big-endian, index "
                          "0 being the first register requested.",
    "OnStepResult.Count": "How many registers `pData` actually holds. Trusting "
                          "this rather than the quantity requested is what "
                          "stops a short reply being read past the end of.",
    "OnTransactionDone.StepsRun": "Steps actually executed. Fewer than "
                                  "requested means an `AbortOnError` step "
                                  "failed.",
    "OnTransactionDone.Failures": "How many of those failed. Zero is the only "
                                  "wholly good outcome.",
    "InitRS485": "Configures the Modbus RTU device address and the polling "
                 "interval(s) for the read command(s).",
    "RequestBusTime": "`RS485Device` interface method. See the "
                      "[RS485Device interface docs](../RS485/RS485Device_Interface.md).",
    "GetRtuQuery": "`RS485Device` interface method. See the "
                   "[RS485Device interface docs](../RS485/RS485Device_Interface.md).",
    "ProcessDataArray": "`RS485Device` interface method. See the "
                        "[RS485Device interface docs](../RS485/RS485Device_Interface.md).",
    "SetValue": "Sets the virtual value. Only effective in output mode.",
    "ConfigureFunctionBlockAsVirtualInput":
        "Configures the block as a virtual input, so a value can be pushed into "
        "the PLC over MQTT and read from output `OUT`.",
    "ConfigureFunctionBlockAsVirtualOutput":
        "Configures the block as a virtual output, publishing the value on input "
        "`IN` over MQTT.",
    # --- MQTT plumbing parameters -----------------------------------------
    "MQTTPublishPrefix": "Pointer to the MQTT publish prefix used for this block. "
                         "The function block name is appended automatically.",
    "MQTTSubscribePrefix": "Pointer to the MQTT subscribe prefix used for this "
                           "block. The function block name is appended automatically.",
    "pMqttPublishQueue": "Pointer to the shared MQTT queue that carries messages "
                         "to the broker.",
    "pMqttCallbackCollector": "Pointer to the callback collector this block "
                              "registers with to receive subscription messages.",
    "MqttQos": "MQTT QoS used for messages published by this block.",
    "MqttRetain": "MQTT retain flag used for messages published by this block.",
    # --- discovery parameters ---------------------------------------------
    "Device": "Pointer to the discovery device this entity belongs to, normally "
              "`MqttVariables.PLC_Device`.",
    "Name": "Name shown in the Home Assistant front-end.",
    "RelayType": "Which way round the driven contact sits: `E_RELAY_TYPE.NO` "
                 "(the default) means the load is live when the output is TRUE, "
                 "`E_RELAY_TYPE.NC` means it is live when the output is FALSE. "
                 "Swaps the payload pair so the entity reports the state of the "
                 "load rather than of the coil.",
    "overruleId": "Overrides the generated entity id. Leave empty to derive it "
                  "from the function block name.",
    "meta": "Extra JSON merged into the discovery config. Leave empty for none.",
    "DeviceClass": "Home Assistant device class for the entity. Leave empty for "
                   "the default.",
    "InitMqttDiscovery.NameValve*": "Name shown in the Home Assistant front-end "
                                    "for this valve. Leave empty to skip it.",
    "PublishReceived.Data": "Received message, supplied by the callback collector.",
    # --- Modbus parameters -------------------------------------------------
    "DeviceAddress": "Modbus RTU address of the device on the RS485 bus.",
    "DataPollingInterval": "How often this block polls the device.",
    "ProcessDataArray.Data": "Pointer to the response data returned by the RTU query.",
    "ProcessDataArray.Error": "Pointer to the bus error flag for the RTU query.",
    "DataAvailable": "High once the block has completed a successful read. Low "
                     "only at startup.",
    "Error": "High when an error occurred while executing the Modbus read command.",
    # --- dimmer MQTT options ----------------------------------------------
    "OutputDimmer": "Set TRUE to publish the dimmer value as MQTT events.",
    "Qos_Dimm": "MQTT QoS used for the dimmer value events.",
    "Delta_Dimm": "Resolution of the dimmer events: only publish once the value "
                  "has moved by at least this much. The final value is always "
                  "published, so MQTT and the output never drift apart.",
    # --- virtual block parameters -----------------------------------------
    "SetValue.Value": "Value to publish. Only effective in output mode.",
}


# ---------------------------------------------------------------- export model

def type_str(type_el) -> str:
    """Render a PLCopen <type> element as IEC text."""
    if type_el is None:
        return "?"
    child = next((c for c in type_el), None)
    if child is None:
        return "?"
    tag = child.tag.split("}")[-1]
    if tag == "derived":
        return child.get("name", "?")
    if tag == "pointer":
        return "POINTER TO " + type_str(child.find("p:baseType", NS))
    if tag == "array":
        dims = ",".join(
            f"{d.get('lower')}..{d.get('upper')}"
            for d in child.findall("p:dimension", NS))
        return f"ARRAY [{dims}] OF " + type_str(child.find("p:baseType", NS))
    if tag == "string":
        n = child.get("length")
        return f"STRING({n})" if n else "STRING"
    return tag.upper()


def variables(parent, section):
    out = []
    for group in parent.findall(f"p:{section}", NS):
        for v in group.findall("p:variable", NS):
            init = v.find("p:initialValue/p:simpleValue", NS)
            out.append({
                "name": v.get("name"),
                "type": type_str(v.find("p:type", NS)),
                "default": init.get("value") if init is not None else None,
            })
    return out


class Fb:
    def __init__(self, pou):
        self.name = pou.get("name")
        iface = pou.find("p:interface", NS)
        self.inputs = variables(iface, "inputVars") if iface is not None else []
        self.outputs = variables(iface, "outputVars") if iface is not None else []
        self.inouts = variables(iface, "inOutVars") if iface is not None else []
        self.methods = []
        for m in pou.iter():
            if m.tag.split("}")[-1] != "Method":
                continue
            mi = m.find("p:interface", NS)
            params = variables(mi, "inputVars") if mi is not None else []
            if m.get("name") in HIDDEN_METHODS:
                continue
            if m.get("name") == "FB_init":
                params = [p for p in params if p["name"] not in IMPLICIT_FB_INIT]
                if not params:
                    continue          # nothing authored, not worth documenting
            self.methods.append({"name": m.get("name"), "params": params})
        self.methods.sort(key=lambda d: d["name"].lower())

    @property
    def pins(self):
        return self.inputs + self.inouts + self.outputs

    @property
    def has_discovery(self):
        return any(m["name"].startswith("InitMqttDiscovery") for m in self.methods)


def load_export():
    if not EXPORT.exists():
        sys.exit(f"error: {EXPORT} not found. Re-export the project first.")
    root = ET.parse(EXPORT).getroot()
    fbs = {p.get("name"): Fb(p)
           for p in root.findall(".//p:pou", NS)
           if p.get("pouType") == "functionBlock"}
    return fbs, root


# ------------------------------------------------------------------ rendering

def ascii_box(fb) -> str:
    ins = [(p["name"], p["type"]) for p in fb.inputs + fb.inouts]
    outs = [(p["name"], p["type"]) for p in fb.outputs]
    lt = max([len(t) for _, t in ins] + [0])
    rt = max([len(t) for _, t in outs] + [0])
    ln = max([len(n) for n, _ in ins] + [0])
    rn = max([len(n) for n, _ in outs] + [0])
    inner = max(len(fb.name) + 2, ln + rn + 5)
    gap = inner - ln - rn - 2
    # An input stub renders as "<type> ──┤" (lt + 4 chars), so the wall lands on
    # column lt + 3; the header lines must use the same offset.
    pad = " " * (lt + 3)
    lines = [pad + "┌" + "─" * inner + "┐",
             pad + "│" + fb.name.center(inner) + "│",
             pad + "├" + "─" * inner + "┤"]
    for k in range(max(len(ins), len(outs))):
        n_i, t_i = ins[k] if k < len(ins) else ("", "")
        n_o, t_o = outs[k] if k < len(outs) else ("", "")
        lead = (t_i.rjust(lt) + " ──┤") if n_i else (" " * (lt + 3) + "│")
        tail = ("├── " + t_o) if n_o else "│"
        lines.append(
            f"{lead} {n_i.ljust(ln)}{' ' * gap}{n_o.rjust(rn)} {tail}".rstrip())
    lines.append(pad + "└" + "─" * inner + "┘")
    return "\n".join(lines)


def _cell(s: str) -> str:
    """Escape a description for a table cell."""
    return (s or "").replace("|", "\\|").strip()


def _uncell(s: str) -> str:
    """Inverse of _cell. Without this the escape compounds on every run."""
    return (s or "").replace("\\|", "|").strip()


def _wild(key: str) -> str:
    """THERMOSTAT_3 -> THERMOSTAT_*, so one description covers a numbered family."""
    return re.sub(r"\d+$", "*", key)


def resolve(descs, *keys):
    """Page-specific description first, then the shared glossary.

    Each key is also tried with its trailing number replaced by `*`, so a single
    `VALVE_*` row documents VALVE_1 through VALVE_8.
    """
    expanded = []
    for k in keys:
        expanded.append(k)
        w = _wild(k)
        if w != k:
            expanded.append(w)
    for k in expanded:
        if descs.get(k):
            return descs[k]
    for k in expanded:
        if GLOSSARY.get(k):
            return GLOSSARY[k]
    return None


def method_desc(name, descs):
    d = resolve(descs, name)
    if d:
        return d
    # InitMqttDiscoveryAsLight / ...AsSwitch / ... all share one explanation.
    if name.startswith("InitMqttDiscoveryAs"):
        entity = re.sub(r"(?<!^)(?=[A-Z])", " ",
                        name[len("InitMqttDiscoveryAs"):]).lower()
        return (f"Publishes a Home Assistant MQTT discovery config for this block "
                f"as a **{entity}** entity. Call once at startup, after `InitMqtt`.")
    if name.startswith("InitMqttDiscovery"):
        return GLOSSARY["InitMqttDiscovery"]
    return None


def pin_table(pins, descs) -> str:
    rows = ["| Pin | Type | Description |", "|:--|:--|:--|"]
    for p in pins:
        d = resolve(descs, p["name"]) or TODO
        rows.append(f"| `{p['name']}` | {p['type']} | {_cell(d)} |")
    return "\n".join(rows)


def method_block(m, descs) -> str:
    key = m["name"]
    head = f"**`{key}`** — {_cell(method_desc(key, descs) or TODO)}"
    if not m["params"]:
        return head
    rows = ["", "| Parameter | Type | Default | Description |", "|:--|:--|:--|:--|"]
    for p in m["params"]:
        d = resolve(descs, f"{key}.{p['name']}", f"*.{p['name']}", p["name"]) or TODO
        rows.append(f"| `{p['name']}` | {p['type']} | "
                    f"{'`'+p['default']+'`' if p['default'] else ''} | {_cell(d)} |")
    return head + "\n" + "\n".join(rows)


def render_interface(fb, descs) -> str:
    out = []
    # A block with no pins (the discovery devices) would render as an empty box.
    if fb.pins:
        out += ["### **Block diagram**", "", "```text", ascii_box(fb), "```", ""]
    ins = fb.inputs + fb.inouts
    if ins or fb.outputs:
        out += ["### **Interface**", ""]
    if ins:
        out += ["**Inputs**", "", pin_table(ins, descs), ""]
    if fb.outputs:
        out += ["**Outputs**", "", pin_table(fb.outputs, descs), ""]
    if fb.methods:
        out += ["### **Methods**", ""]
        for m in fb.methods:
            out += [method_block(m, descs), ""]
    return "\n".join(out).rstrip()


# ------------------------------------------------- description store / parsing

def descs_from_region(text: str) -> dict:
    """Read descriptions back out of a previously generated region."""
    d = {}
    region = re.search(re.escape(I_START) + r"(.*?)" + re.escape(I_END), text, re.S)
    if not region:
        return d
    body = region.group(1)
    current = None
    for line in body.split("\n"):
        m = re.match(r"\*\*`(\w+)`\*\*\s+—\s+(.*)$", line.strip())
        if m:
            current = m.group(1)
            if m.group(2).strip() != TODO:
                d[current] = _uncell(m.group(2))
            continue
        if line.strip().startswith("### "):
            current = None
        m = re.match(r"\|\s*`(\w+)`\s*\|([^|]*)\|([^|]*)\|(.*)\|\s*$", line)
        if m:                                    # method parameter row
            key, desc = m.group(1), _uncell(m.group(4))
            if desc and desc != TODO:
                d[f"{current}.{key}" if current else key] = desc
            continue
        m = re.match(r"\|\s*`(\w+)`\s*\|([^|]*)\|(.*)\|\s*$", line)
        if m:                                    # pin row
            desc = _uncell(m.group(3))
            if desc and desc != TODO:
                d[m.group(1)] = desc
    return d


# A legacy section runs until the next markdown heading or the next section
# label - NOT until the next non-indented line, which would stop on the first
# "- PIN: ..." bullet and capture nothing.
LEGACY_SECTION = re.compile(
    r"^(INPUT\(S\)|OUTPUT\(S\)|METHOD\(S\)):?[ \t]*$"
    r"(.*?)(?=^#{1,6} |^INPUT\(S\)|^OUTPUT\(S\)|^METHOD\(S\)|\Z)",
    re.S | re.M)


def descs_from_legacy(text: str) -> dict:
    """One-time migration: lift descriptions out of hand-written sections."""
    d = {}
    for sec in LEGACY_SECTION.finditer(text):
        kind, block = sec.group(1), sec.group(2)
        current = None
        for line in block.split("\n"):
            # One tab counts as indentation, so match [ \t]+ rather than {2,}.
            nested = re.match(r"^[ \t]+[-*][ \t]+`?(\w+)`?[ \t]*[:—-][ \t]*(.+)$", line)
            if nested and current:
                d.setdefault(f"{current}.{nested.group(1)}", nested.group(2).strip())
                continue
            top = re.match(r"^[-*][ \t]+`?(\w+)`?[ \t]*[:—-][ \t]*(.+)$", line)
            if top:
                current = top.group(1)
                d.setdefault(current, top.group(2).strip())
                # Under METHOD(S) a flat bullet list may be parameters of the
                # single method on the page rather than methods themselves;
                # record both readings and let the renderer pick what matches.
                if kind == "METHOD(S)":
                    d.setdefault(f"*.{top.group(1)}", top.group(2).strip())
    return d


def normalise_key(k: str) -> str:
    """Legacy docs wrote a numbered family as THERMOSTAT_X; store it as _*."""
    return re.sub(r"_[Xx]$", "_*", k)


def clean_desc(s: str) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"^datatype\s+[*_].*?[*_],\s*", "", s)   # type is its own column
    return s[:1].upper() + s[1:] if s else s


# --------------------------------------------------------------------- splice

LEGACY_SECTIONS = re.compile(
    r"^### \*\*Block diagram\*\*\s*$.*?(?=^### |\Z)"
    r"|^INPUT\(S\):?\s*$.*?(?=^### |^OUTPUT\(S\)|^METHOD\(S\)|\Z)"
    r"|^OUTPUT\(S\):?\s*$.*?(?=^### |^INPUT\(S\)|^METHOD\(S\)|\Z)"
    r"|^METHOD\(S\):?\s*$.*?(?=^### |\Z)",
    re.S | re.M)


def apply(text: str, fb, migrate: bool) -> str:
    descs = descs_from_region(text)
    if migrate:
        legacy = {normalise_key(k): clean_desc(v)
                  for k, v in descs_from_legacy(text).items()}
        legacy.update(descs)          # a generated region always wins
        descs = legacy

    badge = f"{B_START}\n{BADGE}\n{B_END}" if fb.has_discovery else f"{B_START}\n{B_END}"
    region = f"{I_START}\n{render_interface(fb, descs)}\n{I_END}"

    if B_START in text:
        text = re.sub(re.escape(B_START) + r".*?" + re.escape(B_END),
                      lambda _: badge, text, flags=re.S)
    else:
        # place it directly under the H2 title, replacing a hand-written badge
        text = re.sub(r"^(## .+\n)(" + re.escape(BADGE) + r"\n)?",
                      lambda m: m.group(1) + badge + "\n", text, count=1)

    if I_START in text:
        text = re.sub(re.escape(I_START) + r".*?" + re.escape(I_END),
                      lambda _: region, text, flags=re.S)
    elif migrate:
        first = LEGACY_SECTIONS.search(text)
        if not first:
            return text
        text = LEGACY_SECTIONS.sub("", text)
        text = text[:first.start()] + region + "\n\n" + text[first.start():]
    return re.sub(r"\n{3,}", "\n\n", text).rstrip() + "\n"


G_START, G_END = "<!-- gvl:start -->", "<!-- gvl:end -->"
GVL_DOC = REPO / "docs" / "AdditionalFunctionality" / "MQTT_General.md"


def render_gvl(root) -> str:
    """The MqttVariables global variable list, straight from the export."""
    gvl = next((g for g in root.iter()
                if g.tag.split("}")[-1] == "globalVars"
                and g.get("name") == "MqttVariables"), None)
    if gvl is None:
        return None
    lines = ["```ST", "VAR_GLOBAL"]
    for v in gvl.findall("p:variable", NS):
        init = v.find("p:initialValue/p:simpleValue", NS)
        decl = f"    {v.get('name')} : {type_str(v.find('p:type', NS))}"
        if init is not None:
            decl += f" := {init.get('value')}"
        lines.append(decl + ";")
    lines += ["END_VAR", "```"]
    return "\n".join(lines)


def update_gvl_doc(root, check: bool) -> bool:
    """Returns True when the page is (or would be) changed."""
    if not GVL_DOC.exists():
        return False
    block = render_gvl(root)
    if block is None:
        return False
    text = GVL_DOC.read_text(encoding="utf-8")
    region = f"{G_START}\n{block}\n{G_END}"
    if G_START in text:
        new = re.sub(re.escape(G_START) + r".*?" + re.escape(G_END),
                     lambda _: region, text, flags=re.S)
    else:                                   # first run: replace the pasted block
        m = re.search(r"```ST\n.*?```", text, re.S)
        if not m:
            return False
        new = text[:m.start()] + region + text[m.end():]
    if new == text:
        return False
    if not check:
        GVL_DOC.write_text(new, encoding="utf-8")
    return True


SCAFFOLD = """## {name}
{badge}

### **General**

{todo}

{region}

### **Code example**

```
{todo}
```
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--migrate", action="store_true",
                    help="lift descriptions out of legacy hand-written sections")
    ap.add_argument("--new", metavar="FB")
    ap.add_argument("--print", dest="show", metavar="FB")
    args = ap.parse_args()
    fbs, root = load_export()

    if args.show:
        fb = fbs.get(args.show)
        if not fb:
            print(f"!! {args.show}: not in the export")
            return 1
        print(render_interface(fb, {}))
        return 0

    if args.new:
        fb = fbs.get(args.new)
        if not fb:
            print(f"!! {args.new}: not in the export - add the block first")
            return 1
        p = DOCS / f"{args.new}.md"
        if p.exists():
            print(f"!! {p} already exists")
            return 1
        p.write_text(SCAFFOLD.format(
            name=fb.name,
            badge=f"{B_START}\n{BADGE}\n{B_END}" if fb.has_discovery
                  else f"{B_START}\n{B_END}",
            region=f"{I_START}\n{render_interface(fb, {})}\n{I_END}",
            todo=TODO), encoding="utf-8")
        print(f"created {p.relative_to(REPO)}")
        return 0

    stale, wrote, orphaned, todos, yaml_hits = [], [], [], [], []
    for doc in sorted(DOCS.glob("FB_*.md")):
        name = doc.stem
        text = doc.read_text(encoding="utf-8")
        fb = fbs.get(name)
        if fb is None:
            if I_START in text or B_START in text:
                orphaned.append(name)
            continue
        if not fb.pins and not fb.methods:
            continue
        updated = apply(text, fb, args.migrate)
        if updated != text:
            if args.check:
                stale.append(name)
            else:
                doc.write_text(updated, encoding="utf-8")
                wrote.append(name)
        final = updated if not args.check else text
        if TODO in final:
            todos.append(name)
        if fb.has_discovery and "### **Home Assistant YAML**" in final:
            yaml_hits.append(name)

    gvl_changed = update_gvl_doc(root, args.check)
    if gvl_changed:
        (stale if args.check else wrote).append("MQTT_General.md (MqttVariables)")

    for label, items, note in (
        ("ORPHANED - documented but no longer in the export", orphaned,
         "Remove the doc page and its links, or restore the block."),
        ("MISSING DESCRIPTIONS", todos,
         "Fill in the _TODO_ rows; they are carried across regenerations."),
        ("HA YAML on a discovery-capable block", yaml_hits,
         "Discovery covers these; the YAML fallback can be removed."),
    ):
        if items:
            print(f"{label}:")
            for i in items:
                print("  -", i)
            print(f"  {note}\n")

    if args.check:
        if stale:
            print("Out of date with " + str(EXPORT.relative_to(REPO)) + ":")
            for s in stale:
                print("  -", s)
            print("\nRun: python3 " + str(pathlib.Path(__file__).relative_to(REPO)))
        return 1 if (stale or orphaned) else 0

    print(f"updated {len(wrote)} page(s)")
    for w in wrote:
        print("  -", w)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
