from saleae.analyzers import HighLevelAnalyzer, AnalyzerFrame


class Hla(HighLevelAnalyzer):

    result_types = {
        "canopen": {
            "format": "{{data.summary}}"
        }
    }

    def __init__(self):
        self.current_id = None
        self.current_start = None
        self.current_data = []

    def decode(self, frame: AnalyzerFrame):

        if frame.type == "identifier_field":
            result = self.flush(frame.start_time)

            self.current_id = frame.data.get("identifier")
            self.current_start = frame.start_time
            self.current_data = []

            return result

        if frame.type == "data_field":
            data = frame.data.get("data")

            if isinstance(data, int):
                self.current_data.append(data)
            elif isinstance(data, bytes):
                self.current_data.extend(data)
            elif isinstance(data, list):
                self.current_data.extend(data)

            return None

        if frame.type in ["crc_field", "ack_field", "can_error"]:
            return self.flush(frame.end_time)

        return None

    def flush(self, end_time):
        if self.current_id is None:
            return None

        cob_id = self.current_id
        data = bytes(self.current_data)

        summary = self.decode_canopen(cob_id, data)

        result = AnalyzerFrame(
            "canopen",
            self.current_start,
            end_time,
            {
                "summary": summary
            }
        )

        self.current_id = None
        self.current_start = None
        self.current_data = []

        return result

    def decode_canopen(self, cob_id, data):

        if cob_id == 0x000:
            return self.decode_nmt(data)

        if cob_id == 0x080:
            return "SYNC"

        if 0x081 <= cob_id <= 0x0FF:
            return f"EMCY Node {cob_id - 0x080}, Data={self.hex_data(data)}"

        pdo = self.decode_pdo(cob_id, data)
        if pdo:
            return pdo

        if 0x580 <= cob_id <= 0x5FF:
            return self.decode_sdo(cob_id - 0x580, data, "Response")

        if 0x600 <= cob_id <= 0x67F:
            return self.decode_sdo(cob_id - 0x600, data, "Request")

        if 0x700 <= cob_id <= 0x77F:
            return self.decode_heartbeat(cob_id - 0x700, data)

        return f"CAN 0x{cob_id:03X}, Data={self.hex_data(data)}"

    def decode_nmt(self, data):
        if len(data) < 2:
            return "NMT Invalid Length"

        command = data[0]
        node_id = data[1]

        commands = {
            0x01: "Start Remote Node",
            0x02: "Stop Remote Node",
            0x80: "Enter Pre-operational",
            0x81: "Reset Node",
            0x82: "Reset Communication"
        }

        cmd_text = commands.get(command, f"Unknown Command 0x{command:02X}")

        if node_id == 0:
            return f"NMT {cmd_text}, All Nodes"

        return f"NMT {cmd_text}, Node {node_id}"

    def decode_heartbeat(self, node_id, data):
        if len(data) < 1:
            return f"Heartbeat Node {node_id}, Invalid Length"

        state = data[0]

        states = {
            0x00: "Boot-up",
            0x04: "Stopped",
            0x05: "Operational",
            0x7F: "Pre-operational"
        }

        state_text = states.get(state, f"Unknown State 0x{state:02X}")

        return f"Heartbeat Node {node_id}, {state_text}"

    def decode_pdo(self, cob_id, data):
        pdo_table = [
            (0x180, 0x1FF, "TPDO1", 0x180),
            (0x200, 0x27F, "RPDO1", 0x200),
            (0x280, 0x2FF, "TPDO2", 0x280),
            (0x300, 0x37F, "RPDO2", 0x300),
            (0x380, 0x3FF, "TPDO3", 0x380),
            (0x400, 0x47F, "RPDO3", 0x400),
            (0x480, 0x4FF, "TPDO4", 0x480),
            (0x500, 0x57F, "RPDO4", 0x500),
        ]

        for start, end, name, base in pdo_table:
            if start <= cob_id <= end:
                node_id = cob_id - base
                return f"{name} Node {node_id}, Data={self.hex_data(data)}"

        return None

    def decode_sdo(self, node_id, data, direction):
        if len(data) < 4:
            return f"SDO {direction} Node {node_id}, Invalid Length"

        cmd = data[0]
        index = data[1] | (data[2] << 8)
        subindex = data[3]
        payload = data[4:]

        cmd_table = {
            0x40: "Upload Request",
            0x43: "Upload Response 4B",
            0x4B: "Upload Response 2B",
            0x4F: "Upload Response 1B",
            0x23: "Download Request 4B",
            0x2B: "Download Request 2B",
            0x2F: "Download Request 1B",
            0x60: "Download Response",
            0x80: "Abort"
        }

        cmd_text = cmd_table.get(cmd, f"CMD 0x{cmd:02X}")

        if cmd == 0x80 and len(data) >= 8:
            abort_code = (
                data[4]
                | (data[5] << 8)
                | (data[6] << 16)
                | (data[7] << 24)
            )

            return (
                f"SDO {direction} Node {node_id}, ABORT, "
                f"0x{index:04X}:{subindex:02X}, "
                f"Abort=0x{abort_code:08X}"
            )

        object_name = self.object_name(index, subindex)

        return (
            f"SDO {direction} Node {node_id}, {cmd_text}, "
            f"0x{index:04X}:{subindex:02X} {object_name}, "
            f"Data={self.hex_data(payload)}"
        )

    def object_name(self, index, subindex):
        od = {
            (0x1000, 0x00): "Device Type",
            (0x1001, 0x00): "Error Register",
            (0x1018, 0x00): "Identity Object - Number of Entries",
            (0x1018, 0x01): "Vendor ID",
            (0x1018, 0x02): "Product Code",
            (0x1018, 0x03): "Revision Number",
            (0x1018, 0x04): "Serial Number",
            (0x6040, 0x00): "Controlword",
            (0x6041, 0x00): "Statusword",
            (0x6060, 0x00): "Modes of Operation",
            (0x6061, 0x00): "Modes of Operation Display",
        }

        name = od.get((index, subindex))
        if name:
            return f"({name})"

        return ""

    def hex_data(self, data):
        if not data:
            return "-"
        return data.hex(" ").upper()