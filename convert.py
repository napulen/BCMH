import os
import re

import music21


def _formatKey(key):
    return key.replace("-", "b")


def _formatRN(rn):
    return (
        rn.replace(";", "")  # phrase token
        .replace("[", "")  # start-ties in humdrum
        .replace("]", "")  # end-ties in humdrum
        .replace("%", "ø")  # half-diminished symbol
        .replace("V(64)", "Cad64")  # cadential six-four
        .replace("V(54)", "V")  # suspensions?
    )


def _formatBeatNumber(b):
    if b == 1:
        return ""
    elif b.is_integer():
        return f"b{int(b)} "
    else:
        return f"b{b} "


def _preprocessHumdrum(path):
    with open(path) as fd:
        data = fd.read()
    for line in data.splitlines():
        modified = re.sub(r"\*([A-Ga-g#-]):dor(\t?)", r"*\1:\2", line)
        if modified != line:
            # this simplifies "dorian" keys as just minor mode, otherwise, roman numerals mess up
            data = data.replace(line, modified)
        elif line.startswith("**harm"):
            spines = line.count("**kern")
            staffslist = "*staff1/2/3/4"
            staffs = "\t".join([f"*staff{i}" for i in range(1, spines + 1)])
            modified = line.replace(line, f"{line}\n{staffslist}\t{staffs}")
            # print(modified)
            data = data.replace(line, modified).replace("**harm", "**text")
    # At this point, the .krn file was modified to
    #   - turn the **harm spine into a lyric (**text)
    #   - add the *staff metadata information (otherwise the lyric doesn't attach to any notes)
    # This should make it possible to parse all the annotations with music21
    a = music21.converter.parseData(data)
    return a


def makeRntxtHeader(metadata):
    analyst = "The Bach Chorales Melody-Harmony Corpus. See https://github.com/PeARL-laboratory/BCMH"
    composer = metadata.composer
    title = metadata.title
    header = f"Composer: {composer}\n"
    header += f"Title: {title}\n"
    header += f"Analyst: {analyst}\n"
    header += f"Proofreader: Automated translation by Néstor Nápoles López\n"
    return header


def makeRntxtBody(offs):
    body = ""
    line = ""
    currentMeasure = -1
    for _, mm in offs.items():
        ts = mm["ts"]
        m = mm["measure"]
        b = mm["beat"]
        key = mm["key"]
        rn = mm["rn"]
        if m != currentMeasure:
            currentMeasure = m
            if line:
                body += f"{line[:-1]}\n"
            line = f"m{m} "
        if ts:
            body += f"\nTime Signature: {ts}\n\n"
        beat = _formatBeatNumber(b)
        if key:
            line += f"{beat}{key}: {rn} "
        else:
            line += f"{beat}{rn} "
        # if re.match(r"m(\d)+ $", line):
        #     continue
    if line:
        body += f"{line[:-1]}\n"
    return body


def parseBCMH(a):
    parsed = {}
    offsets = {
        o.offset: (o.measureNumber, o.beat) for o in a.flat.notesAndRests
    }
    tss = {
        ts.offset: ts.ratioString
        for ts in a.flat.getElementsByClass("TimeSignature")
    }
    keys = {
        k.offset: k.tonicPitchNameWithCase
        for k in a.flat.getElementsByClass("Key")
    }
    rns = {n.offset: n.lyric for n in a.flat.notes if n.lyrics}

    for offset in sorted(
        set(list(keys.keys()) + list(tss.keys()) + list(rns.keys()))
    ):
        measure, beat = offsets[offset]
        ts = tss.get(offset, "")
        key = keys.get(offset, "")
        rn = rns.get(offset, "")
        if ":" in rn:
            # this roman numeral has a key change indication in it
            key, rn = rn.split(":", 1)
        key = _formatKey(key)
        rn = _formatRN(rn)

        parsed[offset] = {
            "measure": measure,
            "beat": beat,
            "ts": ts,
            "key": key,
            "rn": rn,
        }
        # print(offset, measure, beat, f"{key}{':' if key else ''}{rn}")
    return parsed


if __name__ == "__main__":
    root_analysis = "BCMH_dataset/annotated"
    root_score = "BCMH_dataset/original_KernScores"
    root_rntxt = "BCMH_dataset/rntxt"
    rns = []
    for f in sorted(os.listdir(root_analysis)):
        print(f)
        if "087" in f:
            print()
        a = _preprocessHumdrum(f"{root_analysis}/{f}")
        parsed = parseBCMH(a)
        rntxt = makeRntxtHeader(a.metadata)
        rntxt += makeRntxtBody(parsed)
        if not os.path.exists(root_rntxt):
            os.makedirs(root_rntxt)
        with open(f"{root_rntxt}/{f.replace('.krn', '.rntxt')}", "w") as fd:
            fd.write(rntxt)
