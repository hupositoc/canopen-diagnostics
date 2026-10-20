namespace DataProcessorWorld;

public class DataProcessorWorldImpl : IDataProcessorWorld
{
    // 감시할 Node ID
    // 49 decimal = 0x31
    private static readonly uint NodeId = 49;

    // CANopen Heartbeat ID = 0x700 + Node ID
    private static readonly uint HeartbeatId = 0x700 + NodeId;

    // Heartbeat timeout 기준 [ms]
    private static readonly long TimeoutMs = 3000;

    private static long _lastHeartbeatMs = 0;
    private static bool _failed = false;
    private static long _rxCount = 0;
    private static long _heartbeatCount = 0;

    public static string DisplayName() => "CANopen Heartbeat Monitor";

    public static string Description() =>
        "Monitors CANopen heartbeat and reports FAIL when heartbeat timeout occurs.";

    public static string Version() => "1.0.0";

    public static string Author() => "Hansol Oriontech";

    public static string DefaultConfig() => "{}";

    public static void OnStartMeasurement(string config)
    {
        _lastHeartbeatMs = NowMs();
        _failed = false;
        _rxCount = 0;
        _heartbeatCount = 0;

        exports.DataProcessorWorld.Log(
            $"Heartbeat monitor started. Node ID={NodeId}, Heartbeat ID=0x{HeartbeatId:X3}, Timeout={TimeoutMs} ms",
            IDataProcessorWorld.LogSeverity.INFO
        );
    }

    public static void OnStopMeasurement()
    {
        exports.DataProcessorWorld.Log(
            $"Heartbeat monitor stopped. RX={_rxCount}, Heartbeat={_heartbeatCount}",
            IDataProcessorWorld.LogSeverity.INFO
        );
    }

    public static IDataProcessorWorld.ProcessResult? OnRxFrame(IDataProcessorWorld.Frame frame)
    {
        _rxCount++;

        long now = NowMs();

        // Heartbeat 수신 확인
        if ((uint)frame.id == HeartbeatId)
        {
            _lastHeartbeatMs = now;
            _heartbeatCount++;

            string state = "-";
            if (frame.data.Count > 0)
            {
                state = GetHeartbeatState(frame.data[0]);
            }

            exports.DataProcessorWorld.Log(
                $"Heartbeat OK. ID=0x{frame.id:X3}, State={state}, Count={_heartbeatCount}",
                IDataProcessorWorld.LogSeverity.DEBUG
            );

            return null;
        }

        // Heartbeat timeout 검사
        long elapsed = now - _lastHeartbeatMs;

        if (!_failed && elapsed > TimeoutMs)
        {
            _failed = true;

            exports.DataProcessorWorld.Log(
                $"FAIL: Heartbeat timeout. ID=0x{HeartbeatId:X3}, elapsed={elapsed} ms",
                IDataProcessorWorld.LogSeverity.ERROR
            );
        }

        return null;
    }

    public static IDataProcessorWorld.ProcessResult? OnTxFrame(IDataProcessorWorld.Frame frame)
    {
        return null;
    }

    public static IDataProcessorWorld.ProcessResult? OnErrorFrame(IDataProcessorWorld.Frame frame)
    {
        exports.DataProcessorWorld.Log(
            $"CAN Error frame received. ID=0x{frame.id:X3}",
            IDataProcessorWorld.LogSeverity.WARNING
        );

        return null;
    }

    private static long NowMs()
    {
        return DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
    }

    private static string GetHeartbeatState(byte value)
    {
        return value switch
        {
            0x00 => "Boot-up",
            0x04 => "Stopped",
            0x05 => "Operational",
            0x7F => "Pre-operational",
            _ => $"Unknown(0x{value:X2})"
        };
    }
}