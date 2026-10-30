"""SDO request/response helpers only; no Kvaser or serial hardware is simulated."""
import importlib.util
from pathlib import Path
import unittest

path=Path(__file__).resolve().parents[1]/'sdo-ssi-logger/sdo_ssi_logger.py'
spec=importlib.util.spec_from_file_location('sdo_logger_under_test',path)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class SdoHelperTests(unittest.TestCase):
    def test_upload_request_layout(self):
        self.assertEqual(module.sdo_upload_request(0x01,0x1018,0x02),(0x601,[0x40,0x18,0x10,0x02,0,0,0,0]))
    def test_abort_code_little_endian(self):
        self.assertEqual(module.parse_sdo_response([0x80,0x00,0x10,0,0x00,0x00,0x02,0x06]),('abort',0x06020000,'Object does not exist'))
    def test_unknown_abort_stays_visible(self):
        kind,code,reason=module.parse_sdo_response([0x80,0,0,0,0x78,0x56,0x34,0x12])
        self.assertEqual((kind,code,reason),('abort',0x12345678,'Unknown abort code'))
    def test_expedited_value_bytes(self):
        self.assertEqual(module.parse_sdo_response([0x43,0x00,0x10,0,0x91,0x01,0x0F,0x00]),('data',[0x91,0x01,0x0F,0x00],''))
    def test_short_frame_is_invalid(self):
        self.assertEqual(module.parse_sdo_response([0x43,0x00])[0],'invalid')
    def test_ssi_bytes_hex(self):
        self.assertEqual(module.format_ssi_bytes(b'\x0a\xff'),'0A FF')

if __name__=='__main__':unittest.main()
