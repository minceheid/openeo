import globalState
import threading
import contextlib
import subprocess

# Create mutex lock for protecting transactions
updaterLock=threading.Lock()

def OpenEO_updater(action):
    """
    Interface function to be called from configserver
    """

    if "openeo_upgrade_log" not in globalState.stateDict:
        globalState.stateDict["openeo_upgrade_log"]=""
    
    if action=="openeo" or action=="raspberrypi" or action=="reboot":
        if updaterLock.locked()==False:
            # We have a recognised action, and the Lock has not (yet) been acquired
            # So, clear the log and start a new thread to run the action.
            globalState.stateDict["openeo_upgrade_log"]=""
            x = threading.Thread(target=_upgrade_function,args=(action,))
            x.start()

    status={
        "openeo_upgrade_log": globalState.stateDict["openeo_upgrade_log"],
        "openeo_upgrade_running": updaterLock.locked()
    }

    return status



# Unix, Windows and old Macintosh end-of-line
newlines = ['\n', '\r\n', '\r']
def unbuffered(proc, stream='stdout'):
    """
    Function to help python read unbuffered stdout from a running command
    """
    stream = getattr(proc, stream)
    with contextlib.closing(stream):
        while True:
            out = []
            last = stream.read(1)
            # Don't loop forever
            if last == '' and proc.poll() is not None:
                break
            while last not in newlines:
                # Don't loop forever
                if last == '' and proc.poll() is not None:
                    break
                out.append(last)
                last = stream.read(1)
            out = ''.join(out)
            yield out

def _upgrade_function(action):
    """
    This function is expected to run as a separate thread via threading.Thread()
    It uses a non-blocking lock to to try and prevent more than one command being executed
    simultaneously.
    """

    match action:
        case "openeo":
            command=["/home/pi/openeo/tools/update_openeo.sh"]
            #command=["/home/pi/openeo/tools/update_test.sh"]

        case "raspberrypi":
            command=["/home/pi/openeo/tools/update_raspberrypi.sh"]
            #command=["/home/pi/openeo/tools/update_test.sh"]

        case "reboot":
            command=["/home/pi/openeo/tools/update_reboot.sh"]
            #command=["/home/pi/openeo/tools/update_test.sh"]

        case _:
            # Do nothing if we don't recognise the action
            return
    
    if updaterLock.acquire(blocking=False):
        try:
            proc = subprocess.Popen(
                command, 
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                # Make all end-of-lines '\n'
                universal_newlines=True,  
            )
            for line in unbuffered(proc):
                globalState.stateDict["openeo_upgrade_log"]+=str(line)+"\n"
        except:
                globalState.stateDict["openeo_upgrade_log"]+=f"Error: Unable to execute: {command[0]}\n"

        updaterLock.release()