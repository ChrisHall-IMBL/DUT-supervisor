# -*- coding: utf-8 -*-
"""
Created on Mon Aug 19 15:52:18 2024
Open up an EPICS channel.
Connect to the ANSTO Arduino test board through a USB serial port
Monitor the serial output for errors in the DUT.
Monitor power supply current.
Capture monitor strings in a file.
If an error is detected, take action. E.g. close the beamline imaging shutter.

@author: imbl (CJH)
"""

from epics import caget, caput, cainfo
import serial
import signal
import sys
import time

# Shut down gracefully on receiving ^c interupt
def signal_handler(sig, frame):
    print('Stopping capture')
    serArduino.close()
    serKeithley.close()
    outFile.close()
    sys.exit(0)
signal.signal(signal.SIGINT, signal_handler)

""" Function to read the Keithley PSU on serial port: ser and channel: channel
Returns a floating point rendering of the supply current.
"""
def ReadKeithley(channel, ser):
        command=f'INST:NSEL {channel+1}\n'
        ser.write(command.encode())  # Send command
        command='MEAS:VOLT?\n'
        ser.write(command.encode())  # Send command
        voltsS = ser.readline().decode()  # read response
        voltsF=float(voltsS)
        command='MEAS:CURR?\n'
        ser.write(command.encode())  # Send command
        currS = ser.readline().decode()  # read response
        currF=float(currS)
        # print(voltsF,' V ',currF,' A')
        return currF

# Test EPICS CA for connectivity, using the ionisation chamber
IC_PV='SR08ID01DAQ03:Measure'
IC=caget(IC_PV)
print('IMBL ionisation chamber reading: ', IC)
# If it clears this then CA is established

# Read back the IMBL imaging shutter PV
Shutter_PV='SR08ID01IS01:'
SHT='OPEN' if caget(Shutter_PV + 'SHUTTEROPEN_MONITOR') else 'CLOSED'
print('IMBL imaging shutter: ', SHT)

# Record this monitor output to a text file. Append if already exists.
outFile=open('output_file.txt','a')

# Before running this script check the COM ports using the Device Manager...
ArduinoCOM='COM5'
KeithleyCOM='COM3'

# open and init the Arduino serial port, with a 1 second timeout
serArduino = serial.Serial(ArduinoCOM,baudrate=115200, bytesize=8, parity='N', stopbits=1,
                    timeout=1, xonxoff=0, rtscts=0, write_timeout=2)

# Open the serial connection to the power supply
serKeithley = serial.Serial(KeithleyCOM, baudrate=9600, bytesize=8, parity='N', stopbits=1,
                    xonxoff=0, rtscts=0, timeout=1, write_timeout=1)
# Check the Keithley PSU connection with a SCPI request.
try:
    serKeithley.write("*IDN?\n".encode())  # Send ID command to check OK
except:
    print('Caught comms exception')
    raise
response = serKeithley.readline().decode()  # read response (ID string)
print('Instrument is: ',response)

""" This is the main monitor loop. Record data and turn the beam off on error detection.

"""
carryOn=True
while carryOn:
    readBack=serArduino.readline()
    if readBack != b'': # Something has come from the Arduino
        arduinoString=readBack.decode('utf-8')
        # print(arduinoString)
        ''' Depending on the DUT this section might get modified
        The standard digital test output is colon separated i.e.
        :<Error bits>:<error set bits>:<error reset bits>
        No errors would return ':0:0:0'
        '''
        # timeNow=time.ctime(time.time())
        timeNow=time.asctime(time.localtime())
        # print(timeNow)
        arduinoStringClean=arduinoString.strip()
        data=arduinoStringClean.split(':')
        if len(data) == 4 :
            errs=int(data[1]) # Total bits in error
            sets=int(data[2]) # Bits set which should be reset
            resets=int(data[3]) # Bits reset which should be set
            DUTstatus=f'Errs: {errs}, Set: {sets}, Reset: {resets}'
            print(DUTstatus)
            # Record shutter status
            SHT='OPEN' if caget(Shutter_PV + 'SHUTTEROPEN_MONITOR') else 'CLOSED'
            # print('IMBL imaging shutter is: ', SHT)
            outFile.write(timeNow + ': ' + DUTstatus + ', ' )
            curr=ReadKeithley(0,serKeithley)
            currS=f'Current (A): {curr}'
            print(currS + ' shutter is:' + SHT + '\n')
            outFile.write(currS + ' shutter is:' + SHT + '\n')
            if errs != 0 : # Take an action if errors are detected.
                print('Error detected. Closing shutter')
                # caput(Shutter_PV + 'SHUTTEROPEN_CMD 0')
                # SHT=caget(Shutter_PV + 'SHUTTEROPEN_MONITOR')
                # print(SHT)
                # carryOn=False

# Exit program if carryOn gets set false.
print('Stopping supervisor program')
serArduino.close()
serKeithley.close()
outFile.close()
sys.exit(0)
