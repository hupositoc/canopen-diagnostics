# Validation and evidence record

## Evidence vocabulary

| Label | Meaning |
|---|---|
| Source inspected | A mechanism exists in the cited implementation; this alone is not proof of successful execution. |
| Locally executed | A named check was run in the current preparation environment, with its scope stated. |
| Author-reported use | Historical operating context supplied by the author; private reports are not published. |
| Pending | A check has not been reproduced and is not presented as a result. |

## Current record

Decoder fixture tests exercise actual HLA parsing through a minimal frame-interface adapter. They do not simulate hardware sampling, a complete CANopen stack or the CanKing runtime.

**Historical/context statement:** The code provides readable protocol interpretation and state-tracking support for the author’s test workflow. It does not implement the complete CANopen specification or prove that a device passed protocol conformance or Type Approval.

## Integration verification checklist

- [ ] Record exact runtime, dependency versions, input/configuration and date.
- [ ] Run a nominal case with a predictable expected output.
- [ ] Exercise an invalid input or interruption and inspect the failure state.
- [ ] Retain a shareable output and the procedure that produced it.
- [ ] Compare the result with the original task, rather than only checking that the program launched.

## Claims deliberately kept separate

- The HLA is a focused decoder and does not cover every CANopen service or malformed-frame condition.
- CanKing API/WASI integration and real-bus timing have not been revalidated here.
- Timeout and node-ID defaults are configuration examples, not certification requirements.

An expected output, architecture drawing or sample configuration is not a measured result. This document is the place to add test logs when integration work is actually completed.

## Executed decoder fixtures

`python -m unittest discover -s tests -v` passed **8 tests**: operational/empty heartbeat, broadcast/short NMT, little-endian SDO abort, PDO payload, unknown-frame fallback and single frame-assembly flush. A minimal Saleae frame adapter permits execution of the real decoder logic. No Saleae/CanKing device behavior is simulated or claimed.


## SDO + SSI logger helpers

`python -m unittest discover -s tests -v` now runs **14 tests**: the 8 decoder fixtures above plus 6 checks of the logger's protocol helpers (SDO request layout, little-endian abort code, unknown abort, expedited data bytes, short frame, SSI hex formatting). The tkinter GUI, Kvaser bus access and serial port were not exercised here; the tool was used by the author on a bench setup in June 2025 (author-reported use).
