#!/usr/bin/env python3

#################################################################################
import time,logging,serial
import RPi.GPIO as GPIO
import binascii

_LOGGER = logging.getLogger(__name__)

class HomeHub(object):
    EOSerial=None

    # GPIO chip reset line (BCM definition)
    NRESET = 16

    @classmethod
    def identify_hardware(self):
        # This should always be a Pi3B, but we tend to test for MiniPro2 (RPiZ),
        # this is the alternate
        return True

    def flush_serial(self):
        _LOGGER.debug("EO COMMS - HomeHub Serial Flush")
        try :
            self.EOSerial.reset_input_buffer()
            self.EOSerial.reset_output_buffer()
        except Exception as e:
            _LOGGER.debug("EO COMMS - Error resetting buffers"+str(e))

    def __init__(self):
        # Setup GPIO
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.NRESET, GPIO.OUT)
        GPIO.output(self.NRESET, GPIO.LOW)
        time.sleep(0.001)
        GPIO.output(self.NRESET, GPIO.HIGH)

        self.EOSerial=serial.Serial(
                baudrate=115200,
                port="/dev/ttyUSB0",
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS,
                timeout=0.4 ) 
        self.flush_serial()
        _LOGGER.debug("EO COMMS - HomeHub initialised")

    def tx(self,command):
        self.flush_serial()
        command += '\r'
        self.EOSerial.write(command.encode("ascii"))
    
    def rx(self, recv_delay=3):
        time.sleep(recv_delay)
        data = self.EOSerial.read(255)
        return bytes(data)
    

    def get_hat_readings(self,address="BE00BE93"):
        """
        Retrieves CT readings. Requires a hardware address.
        """
        
        # Temporary switch of baud and timeout
        self.EOSerial.baudrate = 9600
        self.EOSerial.timeout = 0.1

        address_bytes=binascii.unhexlify(address)

        # List of registers to query. The first one is repeated because we expect it to
        # fail due to the switching of the baud rate
        REGLIST=[b"\x00\x13",b"\x00\x13",b"\x00\x14",b"\x00\x15"]
        ct_readings={}

        for index,reg in enumerate(REGLIST):
            packet = b"UU" + address_bytes + reg + b"\x00\x00\x00\x00" + b"\x00\x00"  
            self.flush_serial()
            self.EOSerial.write(packet)
            response=self.EOSerial.read(14)
            time.sleep(0.01)

            if (index>0):
                # the first reg is expected to fail, so only take action on index 1,2 and 3
                if response == b"" or None:
                    _LOGGER.info("HomeHub CT query is empty")
                    ct_readings[f"p{index}"]=None
                elif len(response)!=14:
                    _LOGGER.info(f"HomeHub CT query response invalid size")
                    ct_readings[f"p{index}"]=None
                else:
                    # decode packet
                    ct_readings[f"p{index}"]= int.from_bytes(response[8:12], "big")/1000
        
        # Switch baud and timeout back to what it was previously
        self.EOSerial.baudrate = 115200
        self.EOSerial.timeout = 0.4

        # return a dict of ct readings
        return(ct_readings)

    def test(self):
        # Just some tests
        def generateChecksum(text):
            checksum = 0
            for byte in text.encode("ascii"):
                checksum += byte
            return "%02X" % (checksum & 0xFF)

        comms=HomeHub()
        comms.tx("+15C")
        result=comms.rx(recv_delay=3)

        if result:
            address=result[1:-3].decode("ascii")
            print("address: "+str(address))

            loop=0
            while loop<5:
                amps_requested=32*(loop%2)
                duty=round(amps_requested*(1/0.06))
                packet="+0"+address+f'{duty:03X}'
                packet=packet+generateChecksum(packet)

                comms.tx(packet) 
                result = comms.rx(0.6)
                
                voltage = round(int(result[13:16], 16) / 3.78580786, 1) # divisor is an estimate, based on voltmeter readings
                amps_set = round(int(result[29:32],16)/(1/0.06))
                
                # Get CT readings. Address is currently hardcoded! - need to understand the discovery procedure
                ct=self.get_hat_readings("BE00BE93")
   
                print(f"Voltage:{voltage:>7}V | Amps Requested: {amps_requested:>2}A | Amps Set: {amps_set:>2}A | p1:{ct['p1']:>5.1f}A | p2:{ct['p2']:>5.1f}A | p3:{ct['p3']:>5.1f}A")
                loop=loop+1
                time.sleep(5)
        else:
                print("No response")
