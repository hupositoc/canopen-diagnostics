# Engineering case study: CANopen Diagnostics

## 1. The task and operating context

Make CANopen traffic and heartbeat state readable while checking normal operation of a marine control and monitoring module through a PC-based test setup.

The author associates these communication checks with Type Approval testing under plans referring to DNV-CG-0339 and LR-TS-01. No product identity, laboratory identity, bus capture or approval certificate is included.

## 2. The problem before the tool

A CAN identifier and a byte string are insufficient for quick interpretation during a test. The engineer needs to distinguish boot-up, operational and stopped states, identify SDO requests or aborts, and notice when an expected heartbeat is no longer arriving.

## 3. The intervention

Provide a Saleae HLA that maps common CANopen identifiers and fields to readable events, plus CanKing host processors that track heartbeat counts, timeout state and recovery. Keep decoding and liveness monitoring separate because a valid message and timely communication are different questions.

### Input → decision → output

1. **Input:** CAN frames.
2. **Processing:** Decode identifiers.
3. **Interpretation:** Track heartbeat state.
4. **Output:** Review event evidence.

This workflow is illustrated in the README and is mapped to actual source entry points in [architecture](architecture.md).

## 4. Work enabled by the implementation

- Read NMT, SYNC, emergency, PDO, SDO and heartbeat events without repeatedly looking up identifier ranges.
- Track heartbeat arrival and timeout transitions during a performance log.
- Relate communication-state observations to periodic status-signal measurements from the wider test setup.

The code provides readable protocol interpretation and state-tracking support for the author’s test workflow. It does not implement the complete CANopen specification or prove that a device passed protocol conformance or Type Approval.

## 5. Technical choices and tradeoffs

### Decode and monitor separately

A heartbeat decoder labels a received message. A monitor also needs a clock and persistent state to detect the absence of a message.

### Keep unknown events visible

Unrecognized frames retain their CAN identifier and bytes. Unknown does not become a false operational state.

### Document implementation differences

JS and C# defaults differ. They are related implementations, not a verified equivalence pair.

## 6. Engineering contribution

Decode CANopen objects and heartbeat/state information into inspectable events. The linked architecture document identifies implementation entry points; validation records distinguish source inspection, executable checks and hardware-dependent behavior.

## 7. Evidence and scope

Decoder fixture tests exercise actual HLA parsing through a minimal frame-interface adapter. They do not simulate hardware sampling, a complete CANopen stack or the CanKing runtime.

- The HLA is a focused decoder and does not cover every CANopen service or malformed-frame condition.
- CanKing API/WASI integration and real-bus timing have not been revalidated here.
- Timeout and node-ID defaults are configuration examples, not certification requirements.

## 8. Next measurable milestone

- [ ] Add timestamped heartbeat integration fixtures.
- [ ] Make node ID and timeout explicit deployment configuration.
- [ ] Compare JS and C# results on the same event stream before claiming parity.

## Before and after the intervention

| Before | Implementation | Work enabled and evidence |
|---|---|---|
| Raw CAN frames required protocol interpretation during communication checks. | Decode CANopen objects and heartbeat/state information into inspectable events. | The code supports interpreting CAN communication in the reported marine-module testing context. |
