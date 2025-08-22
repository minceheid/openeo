#!/usr/bin/env python3

#################################################################################
import time,logging,serial
import RPi.GPIO as GPIO

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
                frequency = int(result[22:25], 16)
                amps_set = round(int(result[29:32],16)/(1/0.06))
                print("Voltage: {0}V    Frequency: {1}Hz    Amps Requested: {2}A    Amps Set: {3}A".format(voltage,frequency,amps_requested,amps_set))
                loop=loop+1
                time.sleep(5)
        else:
                print("No response")
