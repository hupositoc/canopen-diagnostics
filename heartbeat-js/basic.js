import log from "log";

var nodeId = 49;
var timeoutMs = 6000;

var measurementStartTime = 0;
var lastHeartbeatTime = 0;

var heartbeatCount = 0;
var rxCount = 0;
var timeoutCount = 0;
var recoveryCount = 0;

var canErrorCount = 0;
var firstCanErrorTime = 0;
var lastCanErrorTime = 0;

var failed = false;
var lastState = "-";

export function displayName() {
    return "CANopen Heartbeat Monitor";
}

export function description() {
    return "CANopen heartbeat timeout monitor with CAN error frame tracking";
}

export function version() {
    return "1.3.0";
}

export function author() {
    return "Hansol Oriontech";
}

export function defaultConfig() {
    return "{\"nodeId\":49,\"timeoutMs\":6000}";
}

export function onStartMeasurement(config) {
    log("### HEARTBEAT MONITOR START ###", "DEBUG");

    nodeId = 49;
    timeoutMs = 6000;

    try {
        var parsed = JSON.parse(config);

        if (parsed.nodeId !== undefined) {
            nodeId = Number(parsed.nodeId);
        }

        if (parsed.timeoutMs !== undefined) {
            timeoutMs = Number(parsed.timeoutMs);
        }
    } catch (e) {
        log("Config parse failed. Default config used.", "WARNING");
    }

    measurementStartTime = Date.now();
    lastHeartbeatTime = measurementStartTime;

    heartbeatCount = 0;
    rxCount = 0;
    timeoutCount = 0;
    recoveryCount = 0;

    canErrorCount = 0;
    firstCanErrorTime = 0;
    lastCanErrorTime = 0;

    failed = false;
    lastState = "-";

    var heartbeatId = 0x700 + nodeId;

    log("Node ID = " + nodeId, "DEBUG");
    log("Heartbeat ID = 0x" + heartbeatId.toString(16).toUpperCase(), "DEBUG");
    log("Timeout Limit = " + timeoutMs + " ms", "DEBUG");
}

export function onStopMeasurement() {
    var now = Date.now();
    var measurementDuration = now - measurementStartTime;
    var lastHeartbeatGap = now - lastHeartbeatTime;

    var firstCanErrorOffset = "-";
    var lastCanErrorOffset = "-";

    if (firstCanErrorTime > 0) {
        firstCanErrorOffset = String(firstCanErrorTime - measurementStartTime) + " ms";
    }

    if (lastCanErrorTime > 0) {
        lastCanErrorOffset = String(lastCanErrorTime - measurementStartTime) + " ms";
    }

    log(
        "MEASUREMENT SUMMARY: Duration=" +
        measurementDuration +
        " ms, RX Count=" +
        rxCount +
        ", Heartbeat Count=" +
        heartbeatCount +
        ", Timeout Count=" +
        timeoutCount +
        ", Recovery Count=" +
        recoveryCount +
        ", CAN Error Count=" +
        canErrorCount +
        ", First CAN Error Time=" +
        firstCanErrorOffset +
        ", Last CAN Error Time=" +
        lastCanErrorOffset +
        ", Last State=" +
        lastState +
        ", Last Heartbeat Gap=" +
        lastHeartbeatGap +
        " ms, Timeout Limit=" +
        timeoutMs +
        " ms",
        "DEBUG"
    );

    /*
     * RESULT 판단 기준
     *
     * FAIL:
     * - Heartbeat가 한 번도 수신되지 않음
     * - Heartbeat timeout 발생 후 측정 종료 시점까지 회복되지 않음
     *
     * PASS:
     * - Heartbeat timeout 없음
     * - CAN Error Frame 없음
     *
     * WARNING:
     * - Heartbeat timeout은 없지만 CAN Error Frame 발생 이력 있음
     *
     * RECOVERED:
     * - Heartbeat timeout 발생 후 측정 종료 전 회복됨
     *
     * RECOVERED_WITH_CAN_ERROR:
     * - Heartbeat timeout 발생 후 회복됨
     * - 동시에 CAN Error Frame 발생 이력 있음
     */

    if (heartbeatCount === 0) {
        log(
            "RESULT: FAIL | Heartbeat Count=0" +
            " | Timeout Count=" +
            timeoutCount +
            " | Recovery Count=" +
            recoveryCount +
            " | CAN Error Count=" +
            canErrorCount +
            " | First CAN Error Time=" +
            firstCanErrorOffset +
            " | Last CAN Error Time=" +
            lastCanErrorOffset +
            " | Timeout Limit=" +
            timeoutMs +
            " ms",
            "ERROR"
        );
        return;
    }

    if (timeoutCount === 0 && canErrorCount === 0) {
        log(
            "RESULT: PASS | Heartbeat Count=" +
            heartbeatCount +
            " | Timeout Count=0" +
            " | Recovery Count=0" +
            " | CAN Error Count=0" +
            " | Last State=" +
            lastState +
            " | Last Heartbeat Gap=" +
            lastHeartbeatGap +
            " ms | Timeout Limit=" +
            timeoutMs +
            " ms",
            "DEBUG"
        );
        return;
    }

    if (timeoutCount === 0 && canErrorCount > 0) {
        log(
            "RESULT: WARNING | Heartbeat Count=" +
            heartbeatCount +
            " | Timeout Count=0" +
            " | Recovery Count=0" +
            " | CAN Error Count=" +
            canErrorCount +
            " | First CAN Error Time=" +
            firstCanErrorOffset +
            " | Last CAN Error Time=" +
            lastCanErrorOffset +
            " | Last State=" +
            lastState +
            " | Last Heartbeat Gap=" +
            lastHeartbeatGap +
            " ms | Timeout Limit=" +
            timeoutMs +
            " ms",
            "WARNING"
        );
        return;
    }

    if (timeoutCount > 0 && recoveryCount > 0 && lastHeartbeatGap <= timeoutMs && canErrorCount === 0) {
        log(
            "RESULT: RECOVERED | Heartbeat Count=" +
            heartbeatCount +
            " | Timeout Count=" +
            timeoutCount +
            " | Recovery Count=" +
            recoveryCount +
            " | CAN Error Count=0" +
            " | Last State=" +
            lastState +
            " | Last Heartbeat Gap=" +
            lastHeartbeatGap +
            " ms | Timeout Limit=" +
            timeoutMs +
            " ms",
            "DEBUG"
        );
        return;
    }

    if (timeoutCount > 0 && recoveryCount > 0 && lastHeartbeatGap <= timeoutMs && canErrorCount > 0) {
        log(
            "RESULT: RECOVERED_WITH_CAN_ERROR | Heartbeat Count=" +
            heartbeatCount +
            " | Timeout Count=" +
            timeoutCount +
            " | Recovery Count=" +
            recoveryCount +
            " | CAN Error Count=" +
            canErrorCount +
            " | First CAN Error Time=" +
            firstCanErrorOffset +
            " | Last CAN Error Time=" +
            lastCanErrorOffset +
            " | Last State=" +
            lastState +
            " | Last Heartbeat Gap=" +
            lastHeartbeatGap +
            " ms | Timeout Limit=" +
            timeoutMs +
            " ms",
            "WARNING"
        );
        return;
    }

    if (timeoutCount > 0 && lastHeartbeatGap > timeoutMs) {
        log(
            "RESULT: FAIL | Heartbeat Count=" +
            heartbeatCount +
            " | Timeout Count=" +
            timeoutCount +
            " | Recovery Count=" +
            recoveryCount +
            " | CAN Error Count=" +
            canErrorCount +
            " | First CAN Error Time=" +
            firstCanErrorOffset +
            " | Last CAN Error Time=" +
            lastCanErrorOffset +
            " | Last State=" +
            lastState +
            " | Last Heartbeat Gap=" +
            lastHeartbeatGap +
            " ms | Timeout Limit=" +
            timeoutMs +
            " ms",
            "ERROR"
        );
        return;
    }
}

export function onRxFrame(frame) {
    rxCount = rxCount + 1;

    var now = Date.now();
    var heartbeatId = 0x700 + nodeId;

    if (frame.id === heartbeatId) {
        lastHeartbeatTime = now;
        heartbeatCount = heartbeatCount + 1;

        var state = "-";

        if (frame.data && frame.data.length > 0) {
            state = heartbeatState(frame.data[0]);
        }

        lastState = state;

        if (failed) {
            recoveryCount = recoveryCount + 1;
            failed = false;

            log(
                "Heartbeat recovered. ID=0x" +
                frame.id.toString(16).toUpperCase() +
                ", State=" +
                state +
                ", Count=" +
                heartbeatCount +
                ", Recovery Count=" +
                recoveryCount,
                "DEBUG"
            );
        } else {
            log(
                "Heartbeat OK. ID=0x" +
                frame.id.toString(16).toUpperCase() +
                ", State=" +
                state +
                ", Count=" +
                heartbeatCount,
                "DEBUG"
            );
        }

        return {};
    }

    var elapsed = now - lastHeartbeatTime;

    if (!failed && heartbeatCount > 0 && elapsed > timeoutMs) {
        failed = true;
        timeoutCount = timeoutCount + 1;

        log(
            "FAIL: Heartbeat timeout. Expected ID=0x" +
            heartbeatId.toString(16).toUpperCase() +
            ", elapsed=" +
            elapsed +
            " ms, Timeout Count=" +
            timeoutCount,
            "ERROR"
        );
    }

    return {};
}

export function onTxFrame(frame) {
    return {};
}

export function onErrorFrame(frame) {
    var now = Date.now();

    canErrorCount = canErrorCount + 1;

    if (firstCanErrorTime === 0) {
        firstCanErrorTime = now;
    }

    lastCanErrorTime = now;

    log(
        "CAN ERROR FRAME RECEIVED | Error Count=" +
        canErrorCount +
        " | Time From Start=" +
        (now - measurementStartTime) +
        " ms",
        "WARNING"
    );

    return {};
}

function heartbeatState(value) {
    if (value === 0x00) return "Boot-up";
    if (value === 0x04) return "Stopped";
    if (value === 0x05) return "Operational";
    if (value === 0x7F) return "Pre-operational";

    return "Unknown(0x" + value.toString(16).toUpperCase() + ")";
}