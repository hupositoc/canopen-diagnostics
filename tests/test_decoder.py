"""Decoder fixtures only; the adapter does not simulate a Saleae device."""
import importlib.util
from pathlib import Path
import sys
import types
import unittest

adapter=types.ModuleType('saleae.analyzers')
adapter.HighLevelAnalyzer=object
class Frame:
    def __init__(self,type,start_time,end_time,data):
        self.type=type;self.start_time=start_time;self.end_time=end_time;self.data=data
adapter.AnalyzerFrame=Frame
sys.modules.setdefault('saleae',types.ModuleType('saleae'))
sys.modules['saleae.analyzers']=adapter
path=Path(__file__).resolve().parents[1]/'saleae-hla/HighLevelAnalyzer.py'
spec=importlib.util.spec_from_file_location('decoder_under_test',path)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class DecoderTests(unittest.TestCase):
    def setUp(self):self.hla=module.Hla()
    def test_operational_heartbeat(self):
        self.assertEqual(self.hla.decode_canopen(0x731,b'\x05'),'Heartbeat Node 49, Operational')
    def test_empty_heartbeat_is_invalid(self):
        self.assertIn('Invalid Length',self.hla.decode_canopen(0x731,b''))
    def test_nmt_broadcast(self):
        self.assertEqual(self.hla.decode_canopen(0,b'\x01\x00'),'NMT Start Remote Node, All Nodes')
    def test_nmt_short_payload(self):
        self.assertEqual(self.hla.decode_canopen(0,b'\x01'),'NMT Invalid Length')
    def test_sdo_abort_little_endian(self):
        result=self.hla.decode_canopen(0x5b1,bytes([0x80,0x00,0x10,0,0,0,2,6]))
        self.assertIn('0x1000:00',result);self.assertIn('Abort=0x06020000',result)
    def test_pdo_node_and_payload(self):
        self.assertEqual(self.hla.decode_canopen(0x1b1,b'\x12\xab'),'TPDO1 Node 49, Data=12 AB')
    def test_unknown_frame_remains_visible(self):
        self.assertIn('CAN 0x123',self.hla.decode_canopen(0x123,b'\x12'))
    def test_frame_assembly_flushes_once(self):
        self.hla.decode(Frame('identifier_field',0,1,{'identifier':0x731}))
        self.hla.decode(Frame('data_field',1,2,{'data':b'\x05'}))
        result=self.hla.decode(Frame('crc_field',2,3,{}))
        self.assertIn('Operational',result.data['summary'])
        self.assertIsNone(self.hla.decode(Frame('ack_field',3,4,{})))

if __name__=='__main__':unittest.main()
